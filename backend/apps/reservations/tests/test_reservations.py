from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core import clock
from apps.core.exceptions import Conflict, DomainError
from apps.core.models import CanteenSettings
from apps.core.tests import factories as f
from apps.menus import services as menu_services
from apps.reservations import jobs, services
from apps.reservations.models import Reservation
from apps.wallet import services as wallet

MONDAY = date(2026, 11, 2)


class ReservationTests(TestCase):
    def setUp(self):
        self.employee = f.user()
        self.menu = f.menu(MONDAY)

    def test_reserve_is_idempotent(self):
        with clock.frozen(f.at(2026, 11, 1, 20)):
            first = services.reserve(self.employee, self.menu)
            second = services.reserve(self.employee, self.menu)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_cutoff_is_midnight_the_day_before(self):
        with clock.frozen(f.at(2026, 11, 1, 23, 59, 59)):
            services.reserve(self.employee, self.menu)
        with clock.frozen(f.at(2026, 11, 2, 0, 0, 0)):
            with self.assertRaises(DomainError):
                services.reserve(f.user(), self.menu)

    def test_can_reserve_again_after_cancelling(self):
        with clock.frozen(f.at(2026, 11, 1, 20)):
            r = services.reserve(self.employee, self.menu)
            services.cancel(r, by=self.employee)
            again = services.reserve(self.employee, self.menu)
        self.assertNotEqual(r.pk, again.pk)
        self.assertNotEqual(r.qr_token, again.qr_token)

    def test_no_booking_horizon_by_default(self):
        far = f.menu(date(2027, 3, 1))
        with clock.frozen(f.at(2026, 11, 1, 20)):
            services.reserve(self.employee, far)


class ScanTests(TestCase):
    def setUp(self):
        self.scanner = f.user(role="scanner")
        self.menu = f.menu(MONDAY)
        with clock.frozen(f.at(2026, 11, 1, 20)):
            self.reservation = services.reserve(f.user(), self.menu)

    def test_valid_scan_then_second_scan_refused(self):
        with clock.frozen(f.at(2026, 11, 2, 12, 30)):
            served = services.scan(self.reservation.qr_signed_payload, by=self.scanner)
            self.assertEqual(served.status, Reservation.Status.SERVED)
            with self.assertRaises(Conflict) as ctx:
                services.scan(self.reservation.qr_signed_payload, by=self.scanner)
        self.assertEqual(ctx.exception.code, "already_served")

    def test_forged_code_refused(self):
        with clock.frozen(f.at(2026, 11, 2, 12, 30)):
            with self.assertRaises(DomainError):
                services.scan(self.reservation.qr_token + ":fake", by=self.scanner)

    def test_wrong_day_refused(self):
        with clock.frozen(f.at(2026, 11, 3, 12, 30)):
            with self.assertRaises(DomainError) as ctx:
                services.scan(self.reservation.qr_signed_payload, by=self.scanner)
        self.assertEqual(ctx.exception.code, "wrong_date")

    def test_outside_service_window_refused(self):
        with clock.frozen(f.at(2026, 11, 2, 11, 59)):
            with self.assertRaises(DomainError):
                services.scan(self.reservation.qr_signed_payload, by=self.scanner)

    def test_offline_scan_synced_after_window_is_accepted(self):
        with clock.frozen(f.at(2026, 11, 2, 15, 20)):
            served = services.scan(
                self.reservation.qr_signed_payload, by=self.scanner, scanned_at=f.at(2026, 11, 2, 14, 55)
            )
        self.assertEqual(served.served_at, f.at(2026, 11, 2, 14, 55))

    def test_unscanned_becomes_no_show_after_15h(self):
        with clock.frozen(f.at(2026, 11, 2, 15, 0, 1)):
            jobs.mark_no_shows()
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.NO_SHOW)

    def test_nobody_is_absent_while_the_day_is_not_over(self):
        """Reports count a no-show only once the service has ended: until then the person can still come."""
        for moment in (f.at(2026, 11, 1, 23), f.at(2026, 11, 2, 9), f.at(2026, 11, 2, 14, 59, 59)):
            with clock.frozen(moment):
                jobs.mark_no_shows()
        self.reservation.refresh_from_db()
        self.assertEqual(self.reservation.status, Reservation.Status.RESERVED)
        with clock.frozen(f.at(2026, 11, 2, 14, 59, 59)):  # and can still be served
            self.assertEqual(services.scan(self.reservation.qr_signed_payload, by=self.scanner).status, "served")


class ChoiceTests(TestCase):
    """Two menus a day (decided 2026-11-03): the employee picks one and can switch until the cutoff."""

    def setUp(self):
        self.chef = f.user(role="chef")
        self.employee = f.user()
        self.menu = f.menu(MONDAY)
        f.items(self.menu, self.chef, 1, 2)

    def test_reserve_menu_2_then_switch_to_menu_1(self):
        with clock.frozen(f.at(2026, 11, 1, 20)):
            r = services.reserve(self.employee, self.menu, choice=2)
            switched = services.reserve(self.employee, self.menu, choice=1)
        self.assertEqual((switched.pk, switched.choice), (r.pk, 1))
        self.assertEqual(Reservation.objects.count(), 1)

    def test_menu_not_offered_is_refused(self):
        one_menu = f.menu(date(2026, 11, 3))
        f.items(one_menu, self.chef, 1)
        with clock.frozen(f.at(2026, 11, 1, 20)):
            with self.assertRaises(DomainError) as ctx:
                services.reserve(self.employee, one_menu, choice=2)
        self.assertEqual(ctx.exception.code, "invalid_choice")

    def test_scan_tells_which_menu_to_serve(self):
        scanner = f.user(role="scanner")
        with clock.frozen(f.at(2026, 11, 1, 20)):
            r = services.reserve(self.employee, self.menu, choice=2)
        client = APIClient()
        client.force_authenticate(scanner)
        with clock.frozen(f.at(2026, 11, 2, 12, 30)):
            body = client.post("/api/v1/scan/", {"payload": r.qr_signed_payload}, format="json").json()
        self.assertEqual((body["choice"], body["menu_items"]), (2, ["Plat 2"]))


class PrepaidBalanceTests(TestCase):
    """Decided 2026-11-03: a meal is paid from the balance when reserved, paid back if cancelled
    before midnight the day before, and kept if the employee does not come."""

    def setUp(self):
        cfg = CanteenSettings.load()
        cfg.payment_enabled = True
        cfg.save()
        self.cashier = f.user(role="cashier")
        self.employee = f.user()
        self.menu = f.menu(MONDAY, is_paid=True, price=Decimal("3.500"))

    def _top_up(self, amount):
        wallet.top_up(self.employee, Decimal(amount), by=self.cashier)
        self.employee.refresh_from_db()

    def test_reservation_refused_without_enough_money(self):
        self._top_up("3.000")
        with clock.frozen(f.at(2026, 11, 1, 20)):
            with self.assertRaises(DomainError) as ctx:
                services.reserve(self.employee, self.menu)
        self.assertEqual(ctx.exception.code, "insufficient_balance")
        self.assertEqual(Reservation.objects.count(), 0)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.balance, Decimal("3.000"))

    def test_meal_paid_when_reserved_once_even_on_double_tap(self):
        self._top_up("10.000")
        with clock.frozen(f.at(2026, 11, 1, 20)):
            r = services.reserve(self.employee, self.menu)
            services.reserve(self.employee, self.menu)
        self.employee.refresh_from_db()
        self.assertEqual((r.payment_status, r.amount_due), (Reservation.PaymentStatus.PAID, Decimal("3.500")))
        self.assertEqual(self.employee.balance, Decimal("6.500"))

    def test_switching_menu_costs_nothing(self):
        f.items(self.menu, f.user(role="chef"), 1, 2)
        self._top_up("3.500")
        with clock.frozen(f.at(2026, 11, 1, 20)):
            services.reserve(self.employee, self.menu, choice=1)
            services.reserve(self.employee, self.menu, choice=2)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.balance, Decimal("0.000"))

    def test_cancel_before_cutoff_pays_back_once(self):
        self._top_up("3.500")
        with clock.frozen(f.at(2026, 11, 1, 20)):
            r = services.reserve(self.employee, self.menu)
            services.cancel(r, by=self.employee)
            services.cancel(r, by=self.employee)  # double tap
        self.employee.refresh_from_db()
        r.refresh_from_db()
        self.assertEqual(self.employee.balance, Decimal("3.500"))
        self.assertEqual(r.payment_status, Reservation.PaymentStatus.REFUNDED)

    def test_no_cancel_and_no_refund_after_cutoff(self):
        self._top_up("3.500")
        with clock.frozen(f.at(2026, 11, 1, 20)):
            r = services.reserve(self.employee, self.menu)
        with clock.frozen(f.at(2026, 11, 2, 0, 0, 1)):
            with self.assertRaises(DomainError):
                services.cancel(r, by=self.employee)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.balance, Decimal("0.000"))

    def test_no_show_keeps_the_meal_paid(self):
        self._top_up("3.500")
        with clock.frozen(f.at(2026, 11, 1, 20)):
            r = services.reserve(self.employee, self.menu)
        with clock.frozen(f.at(2026, 11, 2, 15, 0, 1)):
            jobs.mark_no_shows()
        r.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual((r.status, r.payment_status), (Reservation.Status.NO_SHOW, Reservation.PaymentStatus.PAID))
        self.assertEqual(self.employee.balance, Decimal("0.000"))

    def test_closed_day_pays_everyone_back(self):
        self._top_up("3.500")
        with clock.frozen(f.at(2026, 10, 31, 10)):
            services.reserve(self.employee, self.menu)
            menu_services.close_day(self.menu, by=f.user(role="chef"), reason="Jour férié")
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.balance, Decimal("3.500"))

    def test_free_day_costs_nothing(self):
        free = f.menu(date(2026, 11, 3))
        with clock.frozen(f.at(2026, 11, 1, 20)):
            r = services.reserve(self.employee, free)
        self.assertEqual((r.payment_status, r.amount_due), (Reservation.PaymentStatus.NOT_REQUIRED, None))

    def test_new_price_applies_to_new_reservations_only(self):
        self._top_up("10.000")
        late = f.user()
        wallet.top_up(late, Decimal("10.000"), by=self.cashier)
        with clock.frozen(f.at(2026, 10, 30, 10)):
            first = services.reserve(self.employee, self.menu)
            menu_services.set_payment(self.menu, is_paid=True, price=Decimal("4.000"), by=f.user(role="management"))
            second = services.reserve(late, self.menu)
        self.assertEqual((first.amount_due, second.amount_due), (Decimal("3.500"), Decimal("4.000")))


class DayListTests(TestCase):
    """Decided 2026-11-03: scanner and management see each day's reservations, any day."""

    def setUp(self):
        self.menu = f.menu(MONDAY)
        f.items(self.menu, f.user(role="chef"), 1, 2)
        self.ali = f.user(last_name="Ben Ali", employee_number="M-1")
        with clock.frozen(f.at(2026, 11, 1, 20)):
            services.reserve(self.ali, self.menu, choice=2)
            services.cancel(services.reserve(f.user(last_name="Zarrouk"), self.menu), by=self.ali)

    def _get(self, role, query=""):
        client = APIClient()
        client.force_authenticate(f.user(role=role))
        return client.get(f"/api/v1/reservations/day/?date=2026-11-02{query}")

    def test_scanner_and_management_see_the_list(self):
        for role in ("scanner", "management"):
            body = self._get(role).json()
            self.assertEqual([r["full_name"] for r in body["rows"]], ["Test Ben Ali", "Test Zarrouk"])
            self.assertEqual(body["counts"]["total"], 1)
            self.assertEqual(body["counts"]["cancelled"], 1)
            self.assertEqual([c["reserved"] for c in body["menu"]["choices"]], [0, 1])
        self.assertEqual(self._get("employee").status_code, 403)

    def test_filters_and_csv(self):
        self.assertEqual(len(self._get("scanner", "&status=reserved").json()["rows"]), 1)
        self.assertEqual(len(self._get("scanner", "&q=M-1").json()["rows"]), 1)
        csv_text = self._get("management", "&export=csv").content.decode("utf-8-sig")
        self.assertIn("Test Ben Ali;M-1", csv_text)
        # In French like the other exports: words, not status codes.
        self.assertIn(";réservé;", csv_text)
        self.assertIn(";annulé;", csv_text)
        self.assertNotIn("cancelled", csv_text)
