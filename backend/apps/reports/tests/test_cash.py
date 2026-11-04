"""Cash received per day (FR-45): what the scanner hands over, what management expects."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core import clock
from apps.core.models import AuditLog
from apps.core.tests import factories as f
from apps.reservations import services as reservations
from apps.wallet import services as wallet


class CashReportTests(TestCase):
    def setUp(self):
        self.scanner = f.user(role="scanner", last_name="Caisse")
        self.manager = f.user(role="management", last_name="Direction")
        self.amel = f.user(last_name="Amel")
        self.bilel = f.user(last_name="Bilel")
        with clock.frozen(f.at(2026, 11, 3, 23, 50)):  # the day before: not counted
            wallet.top_up(self.amel, Decimal("100"), by=self.scanner)
        with clock.frozen(f.at(2026, 11, 4, 0, 10)):  # just after midnight, company time
            wallet.top_up(self.amel, Decimal("20"), by=self.scanner)
        with clock.frozen(f.at(2026, 11, 4, 9)):
            wallet.top_up(self.bilel, Decimal("50"), by=self.scanner)
            wallet.top_up(self.bilel, Decimal("10"), by=self.manager)
            # Typed 50 instead of 30: management takes 20 back.
            wallet.correct(self.bilel, Decimal("-20"), by=self.manager, reason="Erreur de saisie")

    def _get(self, user, query=""):
        client = APIClient()
        client.force_authenticate(user)
        return client.get(f"/api/v1/reports/cash/{query}")

    def test_management_sees_the_day_per_cashier_with_corrections(self):
        with clock.frozen(f.at(2026, 11, 5, 8)):
            data = self._get(self.manager, "?date=2026-11-04").json()
        self.assertEqual(data["date"], "2026-11-04")
        self.assertEqual(data["scope"], "all")
        self.assertEqual(data["topups"], {"count": 3, "total": "80.000"})
        self.assertEqual(data["corrections"], {"count": 1, "total": "-20.000"})
        self.assertEqual(data["total"], "60.000")
        self.assertEqual(
            [(c["name"], c["count"], c["total"]) for c in data["cashiers"]],
            [(self.scanner.full_name, 2, "70.000"), (self.manager.full_name, 1, "10.000")],
        )
        self.assertEqual([r["kind"] for r in data["rows"]], ["topup", "topup", "topup", "correction"])
        self.assertEqual(data["rows"][-1]["note"], "Erreur de saisie")
        self.assertEqual(data["rows"][0]["at"][11:], "00:10:00+01:00")  # company time, as the app shows it

    def test_meals_are_not_cash(self):
        with clock.frozen(f.at(2026, 11, 4, 9, 30)):
            menu = f.menu(clock.today().replace(day=6), is_paid=True, price=Decimal("3.000"))
            f.items(menu, f.user(role="chef"), 1)
            reservations.reserve(self.amel, menu)  # 3 TND taken from the balance, no cash
            data = self._get(self.manager).json()
        self.assertEqual(data["total"], "60.000")

    def test_scanner_sees_only_her_own_top_ups_of_today(self):
        with clock.frozen(f.at(2026, 11, 4, 18)):
            data = self._get(self.scanner, "?date=2026-11-03").json()  # the date is ignored
        self.assertEqual((data["date"], data["scope"]), ("2026-11-04", "mine"))
        self.assertEqual(data["topups"], {"count": 2, "total": "70.000"})
        self.assertEqual(data["total"], "70.000")
        self.assertEqual(data["corrections"]["count"], 0)
        self.assertEqual({r["employee"] for r in data["rows"]}, {self.amel.full_name, self.bilel.full_name})

    def test_empty_day(self):
        data = self._get(self.manager, "?date=2026-11-10").json()
        self.assertEqual((data["total"], data["rows"], data["cashiers"]), ("0.000", [], []))

    def test_employee_and_chef_cannot_see_it(self):
        self.assertEqual(self._get(self.amel).status_code, 403)
        self.assertEqual(self._get(f.user(role="chef")).status_code, 403)

    def test_csv_export_is_audited(self):
        r = self._get(self.manager, "?date=2026-11-04&export=csv")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode("utf-8-sig")
        self.assertIn("montant_tnd", body)
        self.assertIn("-20,000", body)
        self.assertIn("00:10", body)
        self.assertTrue(AuditLog.objects.filter(action="data_export", meta__report="caisse_2026-11-04.csv").exists())
