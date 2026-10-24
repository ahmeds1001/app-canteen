from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.core import clock
from apps.core.exceptions import Conflict, DomainError
from apps.core.models import CanteenSettings
from apps.core.tests import factories as f
from apps.reservations import jobs, services
from apps.reservations.models import Reservation

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


class PaymentTests(TestCase):
    def test_paid_day_unpaid_meal_still_served_then_marked_paid(self):
        cfg = CanteenSettings.load()
        cfg.payment_enabled = True
        cfg.save()
        menu = f.menu(MONDAY, is_paid=True, price=Decimal("2.500"))
        scanner = f.user(role="scanner")
        with clock.frozen(f.at(2026, 11, 1, 20)):
            r = services.reserve(f.user(), menu)
        self.assertEqual(r.payment_status, Reservation.PaymentStatus.UNPAID)
        with clock.frozen(f.at(2026, 11, 2, 12, 30)):
            served = services.scan(r.qr_signed_payload, by=scanner)
            self.assertEqual(served.payment_status, Reservation.PaymentStatus.UNPAID)
            services.mark_paid(served, by=scanner)
            paid = services.mark_paid(served, by=scanner)  # double tap
        self.assertEqual(paid.payment_status, Reservation.PaymentStatus.PAID)
        self.assertEqual(paid.amount_due, Decimal("2.500"))
