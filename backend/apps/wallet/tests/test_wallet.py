"""Prepaid balance (decided 2026-11-03): top-ups by the cashier, corrections by management, full history."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.exceptions import DomainError, NotAllowed
from apps.core.models import AuditLog, CanteenSettings
from apps.core.tests import factories as f
from apps.notifications.models import Notification
from apps.wallet import services
from apps.wallet.models import BalanceTransaction


class TopUpTests(TestCase):
    def setUp(self):
        self.cashier = f.user(role="cashier")
        self.employee = f.user()

    def test_top_up_credits_records_audits_and_notifies(self):
        entry = services.top_up(self.employee, Decimal("20"), by=self.cashier)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.balance, Decimal("20.000"))
        self.assertEqual((entry.kind, entry.amount, entry.balance_after, entry.by), ("topup", Decimal("20.000"),
                                                                                     Decimal("20.000"), self.cashier))
        self.assertTrue(AuditLog.objects.filter(action="balance_topup", actor=self.cashier).exists())
        self.assertEqual(Notification.objects.get(user=self.employee).kind, "balance_topup")

    def test_amount_must_be_positive_and_reasonable(self):
        for amount in ("0", "-5", "1000.001"):
            with self.assertRaises(DomainError):
                services.top_up(self.employee, Decimal(amount), by=self.cashier)
        self.assertEqual(BalanceTransaction.objects.count(), 0)

    def test_inactive_account_cannot_be_topped_up(self):
        with self.assertRaises(DomainError):
            services.top_up(f.user(status="suspended"), Decimal("10"), by=self.cashier)


class MinimumTopUpTests(TestCase):
    """FR-48 (decided 2026-11-07): no small daily top-ups at the counter. 20 TND by default, set by the admin;
    the cashier must respect it, management may record less for a special case, corrections are not top-ups."""

    def setUp(self):
        self.cashier = f.user(role="cashier")
        self.employee = f.user()

    def test_cashier_below_the_minimum_is_refused(self):
        self.assertEqual(CanteenSettings.load().min_topup_amount, Decimal("20.000"))
        with self.assertRaises(DomainError) as ctx:
            services.top_up(self.employee, Decimal("19.999"), by=self.cashier)
        self.assertEqual(ctx.exception.code, "topup_below_minimum")
        services.top_up(self.employee, Decimal("20"), by=self.cashier)  # exactly the minimum is fine
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.balance, Decimal("20.000"))

    def test_management_may_record_less(self):
        services.top_up(self.employee, Decimal("5"), by=f.user(role="management"))
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.balance, Decimal("5.000"))

    def test_corrections_are_not_concerned(self):
        services.top_up(self.employee, Decimal("20"), by=self.cashier)
        services.correct(self.employee, Decimal("-3"), by=f.user(role="management"), reason="Erreur")
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.balance, Decimal("17.000"))

    def test_admin_sets_or_removes_the_minimum(self):
        client = APIClient()
        admin = f.user(role="admin")
        client.force_authenticate(admin)
        self.assertEqual(client.patch("/api/v1/settings/", {"min_topup_amount": "0"}, format="json").status_code, 200)
        services.top_up(self.employee, Decimal("2"), by=self.cashier)  # 0 = no minimum
        self.assertEqual(client.patch("/api/v1/settings/", {"min_topup_amount": "1000.001"},
                                      format="json").status_code, 400)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.PAYMENT_CONFIG_CHANGE, actor=admin,
                                                meta__field="min_topup_amount").exists())

    def test_the_cashier_screen_knows_the_minimum(self):
        self.assertEqual(APIClient().get("/api/v1/settings/public/").json()["min_topup_amount"], "20.000")


class CorrectionTests(TestCase):
    def setUp(self):
        self.manager = f.user(role="management")
        self.employee = f.user()
        services.top_up(self.employee, Decimal("50"), by=f.user(role="cashier"))  # meant 5

    def test_management_corrects_with_a_reason(self):
        entry = services.correct(self.employee, Decimal("-45"), by=self.manager, reason="Erreur de saisie : 5 TND")
        self.employee.refresh_from_db()
        self.assertEqual((self.employee.balance, entry.note), (Decimal("5.000"), "Erreur de saisie : 5 TND"))
        self.assertEqual(BalanceTransaction.objects.filter(user=self.employee).count(), 2)  # nothing deleted

    def test_reason_required_and_balance_never_negative(self):
        with self.assertRaises(DomainError):
            services.correct(self.employee, Decimal("-5"), by=self.manager, reason=" ")
        with self.assertRaises(DomainError) as ctx:
            services.correct(self.employee, Decimal("-60"), by=self.manager, reason="Trop")
        self.assertEqual(ctx.exception.code, "insufficient_balance")

    def test_cashier_cannot_correct(self):
        with self.assertRaises(NotAllowed):
            services.correct(self.employee, Decimal("-45"), by=f.user(role="cashier"), reason="Erreur")

    def test_only_cashier_and_management_record_cash(self):
        """FR-47 (2026-11-05): the scanner no longer handles money, nor does any other role."""
        for role in ("scanner", "employee", "chef", "hr"):
            with self.assertRaises(NotAllowed):
                services.top_up(self.employee, Decimal("10"), by=f.user(role=role))
        services.top_up(self.employee, Decimal("10"), by=self.manager)


class CashierApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(f.user(role="cashier"))
        self.employee = f.user(last_name="Trabelsi", employee_number="EMP-77")

    def test_search_top_up_and_history(self):
        found = self.client.get("/api/v1/wallet/accounts/?q=trab").json()
        self.assertEqual([a["employee_number"] for a in found], ["EMP-77"])
        r = self.client.post(f"/api/v1/wallet/accounts/{self.employee.pk}/topup/", {"amount": "25.500"}, format="json")
        self.assertEqual(r.json()["account"]["balance"], "25.500")
        history = self.client.get(f"/api/v1/wallet/accounts/{self.employee.pk}/transactions/").json()
        self.assertEqual([t["kind"] for t in history["transactions"]], ["topup"])

    def test_employee_sees_own_balance(self):
        services.top_up(self.employee, Decimal("28"), by=f.user(role="cashier"))
        me = APIClient()
        me.force_authenticate(self.employee)
        body = me.get("/api/v1/wallet/me/").json()
        self.assertEqual((body["balance"], len(body["transactions"])), ("28.000", 1))
