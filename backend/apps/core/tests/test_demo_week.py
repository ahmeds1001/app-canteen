"""The test week used by docs/guide-test-semaine.md builds on an empty database, with the figures the guide gives,
and a later test week starts in the same state, whatever the earlier tests changed."""
import os
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts import services as accounts
from apps.accounts.models import User
from apps.menus.models import Menu
from apps.reservations.models import Reservation
from apps.wallet import services as wallet
from apps.wallet.models import BalanceTransaction

MONDAY = date(2026, 11, 30)  # the guide's week: Monday 30 Nov to Saturday 5 Dec


def build(monday=None):
    # The command ends by moving the shared dev clock: not in a test.
    with mock.patch("apps.core.management.commands.demo_week.call_command"):
        out = StringIO()
        call_command("demo_week", *(["--monday", monday.isoformat()] if monday else []), stdout=out)
    return out.getvalue()


@override_settings(DEBUG=True)
@mock.patch.dict(os.environ, {"DEV_SEED_PASSWORD": "Str0ng-pass-123"})
class DemoWeekTests(TestCase):
    def _week(self, monday):
        days = [monday + timedelta(days=n) for n in range(6)]
        return [Menu.objects.get(date=d) for d in days]

    def _persona_days(self, monday):
        persona = User.objects.get(work_email="employee@ovagri.test")
        mine = Reservation.objects.filter(user=persona, date__gte=monday).exclude(status="cancelled").order_by("date")
        return [((r.date - monday).days, r.choice, r.status) for r in mine]

    def test_week_of_the_guide(self):
        build()
        mon, tue, wed, thu, fri, sat = self._week(MONDAY)
        self.assertEqual([len(m.choices()) for m in (mon, tue, wed, thu, fri, sat)], [1, 2, 2, 2, 2, 1])
        self.assertEqual([tue.status, wed.status, sat.status], ["closed", "published", "draft"])
        self.assertEqual(fri.price, Decimal("3.500"))

        persona = User.objects.get(work_email="employee@ovagri.test")
        self.assertEqual(persona.balance, Decimal("6.000"))  # 15 at the start − 3 meals at 3.000
        self.assertEqual(self._persona_days(MONDAY), [(0, 1, "no_show"), (1, 2, "served"), (3, 1, "reserved")])
        self.assertEqual(User.objects.filter(status=User.Status.PENDING_HR).count(), 2)
        self.assertEqual(User.objects.get(work_email="riadh.hamdi@ovagri.test").status, User.Status.SUSPENDED)

        # Nobody's balance went below zero; every meal paid (refunded or not) is in the history.
        self.assertFalse(User.objects.filter(balance__lt=0).exists())
        self.assertEqual(BalanceTransaction.objects.filter(kind="meal").count(),
                         Reservation.objects.filter(payment_status__in=["paid", "refunded"]).count())
        self.assertEqual(BalanceTransaction.objects.filter(kind="refund").count(),
                         Reservation.objects.filter(payment_status="refunded").count())

    def test_running_twice_adds_nothing(self):
        build()
        count = Reservation.objects.count()
        self.assertIn("already has menus", build())
        self.assertEqual(Reservation.objects.count(), count)

    def test_next_week_starts_like_the_guide_after_a_test_run(self):
        build()
        # What a tester does while following the guide: top-up, approve, reject, reactivate.
        hr = User.objects.get(work_email="hr@ovagri.test")
        persona = User.objects.get(work_email="employee@ovagri.test")
        wallet.top_up(persona, Decimal("40"), by=User.objects.get(work_email="cashier@ovagri.test"))
        sarra, omar = User.objects.filter(status=User.Status.PENDING_HR).order_by("first_name")[::-1]
        accounts.approve(sarra, by=hr, employee_number="EMP-3011")
        accounts.reject(omar, by=hr, reason="Test")
        accounts.change_status(User.objects.get(work_email="riadh.hamdi@ovagri.test"), "reactivate", by=hr)

        next_monday = MONDAY + timedelta(days=7)
        build(next_monday)
        persona.refresh_from_db()
        self.assertEqual(persona.balance, Decimal("6.000"))  # brought back to 15 before the week, then 3 meals
        self.assertEqual(self._persona_days(next_monday), [(0, 1, "no_show"), (1, 2, "served"), (3, 1, "reserved")])
        pending = User.objects.filter(status=User.Status.PENDING_HR)
        self.assertEqual(sorted(u.full_name for u in pending), ["Omar Tlili", "Sarra Bouzid"])
        self.assertEqual(User.objects.get(work_email="riadh.hamdi@ovagri.test").status, User.Status.SUSPENDED)
