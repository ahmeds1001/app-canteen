"""Management dashboard: attendance per employee per month (reserved vs served)."""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.core import clock
from apps.core.models import CanteenSettings
from apps.core.tests import factories as f
from apps.reservations import jobs, services
from apps.wallet import services as wallet


class MonthlyAttendanceTests(TestCase):
    def setUp(self):
        cfg = CanteenSettings.load()
        cfg.payment_enabled = True
        cfg.save()
        self.scanner = f.user(role="scanner")
        self.amel = f.user(last_name="Amel", department="Qualité")
        self.bilel = f.user(last_name="Bilel", department="Production")
        self.idle = f.user(last_name="Zied", department="Production")  # never reserves
        wallet.top_up(self.amel, Decimal("50"), by=self.scanner)
        wallet.top_up(self.bilel, Decimal("50"), by=self.scanner)
        chef = f.user(role="chef")
        mon, tue, wed = date(2026, 11, 2), date(2026, 11, 3), date(2026, 11, 4)
        self.menus = {}
        for d in (mon, tue, wed):
            self.menus[d] = f.menu(d, is_paid=True, price=Decimal("3.000"))
            f.items(self.menus[d], chef, 1, 2)
        with clock.frozen(f.at(2026, 11, 1, 20)):
            self.r_mon = services.reserve(self.amel, self.menus[mon], choice=2)
            services.reserve(self.amel, self.menus[tue])
            services.reserve(self.amel, self.menus[wed])
            services.cancel(services.reserve(self.bilel, self.menus[mon]), by=self.bilel)
            services.reserve(self.bilel, self.menus[tue])
        with clock.frozen(f.at(2026, 11, 2, 12, 30)):
            services.scan(self.r_mon.qr_signed_payload, by=self.scanner)
        with clock.frozen(f.at(2026, 11, 3, 15, 1)):
            jobs.mark_no_shows()  # Tuesday is over: Amel and Bilel absent; Wednesday still to come

    def _get(self, role="management", query="month=2026-11"):
        client = APIClient()
        client.force_authenticate(f.user(role=role))
        return client.get(f"/api/v1/reports/attendance/monthly/?{query}")

    def test_reserved_vs_served_per_employee(self):
        body = self._get().json()
        rows = {r["name"]: r for r in body["rows"]}
        amel = rows["Test Amel"]
        self.assertEqual((amel["reserved"], amel["served"], amel["no_show"], amel["pending"], amel["cancelled"]),
                         (3, 1, 1, 1, 0))
        self.assertEqual((amel["menu_1"], amel["menu_2"], amel["spent"]), (2, 1, "9.000"))
        self.assertEqual(amel["no_show_rate"], 0.5)  # 1 absence out of 2 finished days; Wednesday not counted
        bilel = rows["Test Bilel"]
        self.assertEqual((bilel["reserved"], bilel["cancelled"], bilel["no_show"], bilel["spent"]), (1, 1, 1, "3.000"))
        self.assertEqual(rows["Test Zied"]["reserved"], 0)  # listed even without reservations
        self.assertEqual(body["totals"]["eating"], 2)

    def test_filters_other_month_and_access(self):
        self.assertEqual([r["name"] for r in self._get(query="month=2026-11&department=Qualité").json()["rows"]],
                         ["Test Amel"])
        self.assertEqual(self._get(query="month=2026-10").json()["totals"]["reserved"], 0)
        self.assertEqual(self._get(role="hr").status_code, 200)
        for role in ("employee", "scanner", "chef"):
            self.assertEqual(self._get(role=role).status_code, 403)

    def test_employee_days_and_csv(self):
        client = APIClient()
        client.force_authenticate(f.user(role="management"))
        days = client.get(f"/api/v1/reports/attendance/monthly/{self.amel.pk}/?month=2026-11").json()["rows"]
        self.assertEqual([(d["date"], d["status"]) for d in days],
                         [("2026-11-02", "served"), ("2026-11-03", "no_show"), ("2026-11-04", "reserved")])
        self.assertNotIn("qr_payload", days[0])
        text = self._get(query="month=2026-11&export=csv").content.decode("utf-8-sig")
        self.assertIn("Test Amel;", text)
        self.assertIn("50,0%", text)
