"""Settings screen (FR-46): the admin changes every deadline; the day's steps keep their order; all audited."""
from datetime import date, time

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core import clock
from apps.core.models import AuditLog, CanteenSettings
from apps.core.tests import factories as f
from apps.menus import jobs, rules
from apps.menus.models import Menu
from apps.notifications import jobs as notification_jobs
from apps.notifications import messages
from apps.notifications.models import Notification

URL = "/api/v1/settings/"
THURSDAY = date(2026, 11, 12)


class SettingsScreenTests(TestCase):
    def setUp(self):
        self.admin = f.user(role="admin")

    def _patch(self, user, data):
        client = APIClient()
        client.force_authenticate(user)
        return client.patch(URL, data, format="json")

    def test_only_the_admin(self):
        for role in ("management", "hr", "chef", "scanner", "employee"):
            self.assertEqual(self._patch(f.user(role=role), {"buffer_value": 20}).status_code, 403, role)
        client = APIClient()
        client.force_authenticate(f.user(role="management"))
        self.assertEqual(client.get(URL).status_code, 403)
        self.assertEqual(CanteenSettings.load().buffer_value, 10)

    def test_admin_changes_every_deadline_and_each_change_is_audited(self):
        resp = self._patch(self.admin, {
            "cutoff_days": 2, "cutoff_time": "18:00", "evening_reminder_time": "17:00",
            "publish_deadline_days": 4, "publish_deadline_time": "12:00",
            "finalization_deadline": "09:30", "buffer_value": 15, "payment_enabled": True,
        })
        self.assertEqual(resp.status_code, 200, resp.content)
        cfg = CanteenSettings.load()
        self.assertEqual((cfg.cutoff_days, cfg.cutoff_time), (2, time(18, 0)))
        self.assertEqual(rules.reservation_cutoff(THURSDAY), f.at(2026, 11, 10, 18))
        self.assertEqual(rules.publish_deadline(THURSDAY), f.at(2026, 11, 8, 12))
        self.assertEqual(rules.finalization_deadline(THURSDAY), f.at(2026, 11, 12, 9, 30))
        self.assertEqual(rules.default_buffer(20), 3)
        rows = AuditLog.objects.filter(actor=self.admin)
        self.assertEqual(rows.filter(action=AuditLog.Action.SETTING_CHANGE).count(), 7)
        row = rows.get(action=AuditLog.Action.SETTING_CHANGE, meta__field="cutoff_time")
        self.assertEqual((row.old_value, row.new_value), ("23:59:59", "18:00:00"))
        payment = rows.filter(action=AuditLog.Action.PAYMENT_CONFIG_CHANGE, meta__field="payment_enabled")
        self.assertTrue(payment.exists())

    def test_same_value_is_not_audited(self):
        self._patch(self.admin, {"buffer_value": 10})
        self.assertFalse(AuditLog.objects.filter(action=AuditLog.Action.SETTING_CHANGE).exists())

    def test_incoherent_values_are_refused_and_nothing_changes(self):
        cases = {
            "settings_publish_after_cutoff": {"publish_deadline_days": 1, "publish_deadline_time": "23:59:59"},
            "settings_cutoff_after_finalization": {"cutoff_days": 0, "cutoff_time": "11:00"},
            "settings_finalization_after_service": {"finalization_deadline": "12:30"},
            "settings_service_end_before_start": {"service_window_end": "11:00"},
            "settings_reminder_after_finalization": {"finalization_reminder_time": "10:30"},
            "settings_reminder_after_cutoff": {"cutoff_time": "19:00"},
            "settings_no_service_day": {"service_weekdays": ""},
            "settings_buffer_too_high": {"buffer_value": 150},
        }
        for code, data in cases.items():
            resp = self._patch(self.admin, data)
            self.assertEqual(resp.status_code, 400, code)
            self.assertEqual(resp.json().get("code"), code)
        self.assertEqual(self._patch(self.admin, {"cutoff_days": 9}).status_code, 400)  # out of range
        self.assertEqual(self._patch(self.admin, {"currency": "EUR"}).json()["currency"], "TND")  # read-only
        self.assertFalse(AuditLog.objects.filter(action=AuditLog.Action.SETTING_CHANGE).exists())

    def test_same_day_cutoff(self):
        self.assertEqual(
            self._patch(self.admin, {"cutoff_days": 0, "cutoff_time": "09:00"}).status_code, 200
        )
        menu = f.menu(THURSDAY)
        with clock.frozen(f.at(2026, 11, 12, 8, 59)):
            jobs.lock_menus()
        menu.refresh_from_db()
        self.assertEqual(menu.status, Menu.Status.PUBLISHED)  # still open that morning
        with clock.frozen(f.at(2026, 11, 12, 9, 0, 1)):
            jobs.lock_menus()
        menu.refresh_from_db()
        self.assertEqual(menu.status, Menu.Status.LOCKED)

    def test_cutoff_two_days_before_locks_in_time(self):
        resp = self._patch(self.admin, {"cutoff_days": 2, "cutoff_time": "22:00", "publish_deadline_days": 3})
        self.assertEqual(resp.status_code, 200, resp.content)
        menu = f.menu(THURSDAY)
        with clock.frozen(f.at(2026, 11, 10, 22, 0, 1)):
            jobs.lock_menus()
        menu.refresh_from_db()
        self.assertEqual(menu.status, Menu.Status.LOCKED)

    def test_placeholder_published_at_a_deadline_before_midnight(self):
        self._patch(self.admin, {"publish_deadline_days": 2, "publish_deadline_time": "18:00"})
        with clock.frozen(f.at(2026, 11, 10, 18, 0, 1)):  # Tuesday 18:00 → Thursday's deadline passed
            jobs.publish_placeholders()
        menu = Menu.objects.get(date=THURSDAY)
        self.assertEqual(menu.status, Menu.Status.PUBLISHED)
        self.assertTrue(menu.is_placeholder)

    def test_evening_reminder_targets_the_day_that_closes_next(self):
        # Publishing must stay before the cutoff: the default D-2 23:59:59 would now be too late.
        self.assertEqual(self._patch(self.admin, {"cutoff_days": 2, "cutoff_time": "23:00"}).status_code, 400)
        resp = self._patch(self.admin, {"cutoff_days": 2, "cutoff_time": "23:00", "publish_deadline_days": 3})
        self.assertEqual(resp.status_code, 200, resp.content)
        f.menu(THURSDAY)
        forgot = f.user()
        with clock.frozen(f.at(2026, 11, 10, 20, 0)):  # Tuesday evening: Thursday closes tonight at 23:00
            notification_jobs.evening_reservation_reminder()
        note = Notification.objects.get(user=forgot)
        self.assertEqual(note.params["date"], "2026-11-12")
        _, body = messages.render(note.kind, note.params, "fr")
        self.assertIn("mardi 10 novembre à 23:00", body)

    def test_old_reminders_still_render(self):
        _, body = messages.render(Notification.Kind.RESERVATION_REMINDER,
                                  {"date": "2026-11-12", "dishes": []}, "fr")
        self.assertIn("minuit la veille", body)
