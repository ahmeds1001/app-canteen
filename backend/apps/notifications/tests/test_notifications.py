"""Notifications (spec §8): who gets what, once; daily jobs; push sending; API."""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts import services as account_services
from apps.accounts.models import EmailOTP, User
from apps.core import clock
from apps.core.tests import factories as f
from apps.menus import jobs as menu_jobs
from apps.menus import services as menu_services
from apps.menus.models import Menu
from apps.notifications import jobs, messages
from apps.notifications.models import Notification, PushSubscription
from apps.reservations import services as reservation_services

K = Notification.Kind
MONDAY = date(2026, 11, 2)


def kinds_for(user) -> list[str]:
    return list(Notification.objects.filter(user=user).values_list("kind", flat=True))


class TriggerTests(TestCase):
    def setUp(self):
        self.chef = f.user(role="chef")
        self.manager = f.user(role="management")
        self.hr = f.user(role="hr")
        self.eater = f.user()
        self.other = f.user()

    def test_day_finalized_goes_to_the_chef_only(self):
        menu = f.menu(MONDAY, status=Menu.Status.LOCKED)
        with clock.frozen(f.at(2026, 11, 2, 9)):
            menu_services.finalize(menu, final_plate_count=3, by=self.manager)
        self.assertEqual(kinds_for(self.chef), [K.DAY_FINALIZED])
        self.assertEqual(kinds_for(self.manager), [])
        note = Notification.objects.get(user=self.chef)
        self.assertEqual(note.params["plates"], 3)

    def test_close_day_notifies_only_cancelled_reservations(self):
        menu = f.menu(MONDAY)
        with clock.frozen(f.at(2026, 10, 30, 10)):
            reservation_services.reserve(self.eater, menu)
            menu_services.close_day(menu, by=self.chef, reason="Jour férié")
        self.assertEqual(kinds_for(self.eater), [K.DAY_CLOSED])
        self.assertEqual(kinds_for(self.other), [])

    def test_placeholder_dishes_announce_the_menu(self):
        menu = f.menu(MONDAY, is_placeholder=True)
        with clock.frozen(f.at(2026, 10, 31, 10)):
            reservation_services.reserve(self.eater, menu)
            menu_services.set_items(menu, [f.dish(self.chef).pk], by=self.chef)
        self.assertEqual(kinds_for(self.eater), [K.MENU_ANNOUNCED])
        self.assertEqual(kinds_for(self.other), [])

    def test_changing_a_published_menu_tells_who_reserved(self):
        menu = f.menu(MONDAY)
        with clock.frozen(f.at(2026, 10, 30, 10)):
            menu_services.set_items(menu, [f.dish(self.chef, "Couscous").pk], by=self.chef)
            self.assertEqual(Notification.objects.count(), 0)  # nobody reserved yet
            reservation_services.reserve(self.eater, menu)
            menu_services.set_items(menu, [f.dish(self.chef, "Lablabi").pk], by=self.chef)
        self.assertEqual(kinds_for(self.eater), [K.MENU_CHANGED])

    def test_price_change_tells_who_reserved(self):
        menu = f.menu(MONDAY)
        with clock.frozen(f.at(2026, 10, 30, 10)):
            reservation_services.reserve(self.eater, menu)
            menu_services.set_payment(menu, is_paid=True, price=Decimal("3.500"), by=self.manager)
            menu_services.set_payment(menu, is_paid=True, price=Decimal("3.500"), by=self.manager)  # no change
        self.assertEqual(kinds_for(self.eater), [K.PRICE_CHANGED])

    def test_verified_email_tells_hr(self):
        user = f.user(status=User.Status.REGISTERED)
        EmailOTP.objects.create(user=user, code_hash=account_services._hash("123456"), expires_at=f.at(2099, 1, 1))
        account_services.verify_otp(user, "123456")
        self.assertEqual(kinds_for(self.hr), [K.ACCOUNTS_PENDING])
        self.assertEqual(kinds_for(self.chef), [])

    def test_placeholder_published_and_still_empty_at_cutoff(self):
        with clock.frozen(f.at(2026, 11, 1, 0, 5)):  # Sunday: Monday's D-2 deadline has passed
            menu_jobs.publish_placeholders()
            menu_jobs.publish_placeholders()  # idempotent
        menu = Menu.objects.get(date=MONDAY)
        self.assertEqual(kinds_for(self.chef), [K.PLACEHOLDER_PUBLISHED])
        self.assertEqual(kinds_for(self.manager), [K.PLACEHOLDER_PUBLISHED])
        with clock.frozen(f.at(2026, 11, 1, 10)):
            reservation_services.reserve(self.eater, menu)
        with clock.frozen(f.at(2026, 11, 2, 0, 5)):
            menu_jobs.lock_menus()
        self.assertIn(K.PLACEHOLDER_EMPTY_AT_CUTOFF, kinds_for(self.chef))
        self.assertIn(K.PLACEHOLDER_EMPTY_AT_CUTOFF, kinds_for(self.manager))


class DailyJobTests(TestCase):
    def setUp(self):
        self.chef = f.user(role="chef")
        self.manager = f.user(role="management")

    def test_finalization_reminder_at_08_00_once(self):
        f.menu(MONDAY, status=Menu.Status.LOCKED)
        with clock.frozen(f.at(2026, 11, 2, 7, 59)):
            self.assertEqual(jobs.finalization_reminder(), 0)
        with clock.frozen(f.at(2026, 11, 2, 8, 0)):
            jobs.finalization_reminder()
            jobs.finalization_reminder()
        self.assertEqual(kinds_for(self.manager), [K.FINALIZATION_REMINDER])

    def test_menu_missing_lists_days_without_a_menu(self):
        f.menu(date(2026, 11, 3))  # Tuesday published; Wednesday… have nothing
        with clock.frozen(f.at(2026, 11, 2, 8, 0)):
            jobs.menu_missing_reminder()
            jobs.menu_missing_reminder()
        note = Notification.objects.get(user=self.chef, kind=K.MENU_MISSING)
        self.assertNotIn("2026-11-03", note.params["dates"])
        self.assertIn("2026-11-04", note.params["dates"])
        self.assertNotIn("2026-11-08", note.params["dates"])  # Sunday: no service

    def test_evening_reminder_only_for_those_without_a_reservation(self):
        menu = f.menu(MONDAY)
        reserved = f.user()
        forgot = f.user()
        opted_out = f.user(evening_reminder=False)
        scanner = f.user(role="scanner")
        with clock.frozen(f.at(2026, 10, 31, 10)):
            reservation_services.reserve(reserved, menu)
        with clock.frozen(f.at(2026, 11, 1, 19, 59)):
            self.assertEqual(jobs.evening_reservation_reminder(), 0)
        with clock.frozen(f.at(2026, 11, 1, 20, 0)):
            jobs.evening_reservation_reminder()
            jobs.evening_reservation_reminder()
        self.assertEqual(kinds_for(forgot), [K.RESERVATION_REMINDER])
        self.assertEqual(kinds_for(self.chef), [K.RESERVATION_REMINDER])  # staff eat too
        for user in (reserved, opted_out, scanner):
            self.assertEqual(kinds_for(user), [])

    def test_no_evening_reminder_when_tomorrow_is_closed(self):
        f.menu(MONDAY, status=Menu.Status.CLOSED)
        f.user()
        with clock.frozen(f.at(2026, 11, 1, 20, 0)):
            self.assertEqual(jobs.evening_reservation_reminder(), 0)


@override_settings(VAPID_PUBLIC_KEY="pub", VAPID_PRIVATE_KEY="priv")
class PushTests(TestCase):
    def setUp(self):
        self.chef = f.user(role="chef")
        self.sub = PushSubscription.objects.create(
            user=self.chef, endpoint="https://push.example/abc", p256dh="k", auth="a", created_at=f.at(2026, 11, 1)
        )
        menu = f.menu(MONDAY, status=Menu.Status.LOCKED)
        with clock.frozen(f.at(2026, 11, 2, 9)):
            menu_services.finalize(menu, final_plate_count=0, by=None, auto=True)

    def test_push_sent_once_with_the_text(self):
        with mock.patch("apps.notifications.push.send", return_value=True) as send:
            with clock.frozen(f.at(2026, 11, 2, 9, 1)):
                self.assertEqual(jobs.send_pending_pushes(), 1)
                self.assertEqual(jobs.send_pending_pushes(), 0)
        payload = send.call_args.args[1]
        self.assertEqual(payload["title"], "Nombre d'assiettes")
        self.assertEqual(payload["url"], "/chef/planner")
        self.assertIsNotNone(Notification.objects.get(user=self.chef).pushed_at)

    def test_gone_subscription_is_revoked(self):
        with mock.patch("apps.notifications.push.send", return_value=False):
            with clock.frozen(f.at(2026, 11, 2, 9, 1)):
                jobs.send_pending_pushes()
        self.sub.refresh_from_db()
        self.assertIsNotNone(self.sub.revoked_at)


class ApiTests(TestCase):
    def setUp(self):
        self.user = f.user()
        self.other = f.user()
        for u in (self.user, self.other):
            Notification.objects.create(user=u, kind=K.DAY_CLOSED, params={"date": "2026-11-02", "reason": ""},
                                        dedupe_key="x", created_at=f.at(2026, 11, 1))
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_list_read_and_preferences(self):
        data = self.client.get("/api/v1/notifications/", HTTP_ACCEPT_LANGUAGE="fr").json()
        self.assertEqual((data["unread"], len(data["results"])), (1, 1))  # own notification only
        self.assertEqual(data["results"][0]["body"],
                         "La cantine est fermée le lundi 2 novembre. Votre réservation est annulée.")
        note_id = data["results"][0]["id"]
        self.assertEqual(self.client.post(f"/api/v1/notifications/{note_id}/read/").json()["unread"], 0)
        response = self.client.patch("/api/v1/notifications/preferences/", {"evening_reminder": False}, format="json")
        self.assertFalse(response.json()["evening_reminder"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.evening_reminder)

    def test_subscribe_is_idempotent(self):
        url = "/api/v1/notifications/push/subscribe/"
        body = {"endpoint": "https://push.example/xyz", "keys": {"p256dh": "k", "auth": "a"}}
        self.assertEqual(self.client.post(url, body, format="json").status_code, 204)
        self.client.post(url, body, format="json")
        self.assertEqual(PushSubscription.objects.filter(user=self.user).count(), 1)


class MessageTests(TestCase):
    def test_english_dates(self):
        title, body = messages.render(K.MENU_MISSING, {"dates": ["2026-11-02"]}, "en")
        self.assertEqual(body, "No menu published yet for: Monday, November 2.")
