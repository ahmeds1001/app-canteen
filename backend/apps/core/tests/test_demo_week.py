"""The test week used by docs/guide-test-semaine.md builds on an empty database, with the figures the guide gives."""
import os
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.menus.models import Menu
from apps.reservations.models import Reservation
from apps.wallet.models import BalanceTransaction


@override_settings(DEBUG=True)
@mock.patch.dict(os.environ, {"DEV_SEED_PASSWORD": "Str0ng-pass-123"})
class DemoWeekTests(TestCase):
    def test_week_of_the_guide(self):
        # The command ends by moving the shared dev clock: not in a test.
        with mock.patch("apps.core.management.commands.demo_week.call_command"):
            call_command("demo_week", stdout=StringIO())

        menus = {m.date.day: m for m in Menu.objects.filter(date__month=11, date__day__range=(9, 14))}
        self.assertEqual([len(menus[d].choices()) for d in (9, 10, 11, 12, 13, 14)], [1, 2, 2, 2, 2, 1])
        self.assertEqual([menus[d].status for d in (10, 11, 14)], ["closed", "published", "draft"])
        self.assertEqual(menus[13].price, Decimal("3.500"))

        persona = User.objects.get(work_email="employee@ovagri.test")
        self.assertEqual(persona.balance, Decimal("6.000"))  # 15 topped up − 3 meals at 3.000
        mine = Reservation.objects.filter(user=persona).exclude(status="cancelled").order_by("date")
        self.assertEqual([(r.date.day, r.choice, r.status) for r in mine],
                         [(9, 1, "no_show"), (10, 2, "served"), (12, 1, "reserved")])

        # Nobody's balance went below zero; every meal paid (refunded or not) is in the history.
        self.assertFalse(User.objects.filter(balance__lt=0).exists())
        self.assertEqual(BalanceTransaction.objects.filter(kind="meal").count(),
                         Reservation.objects.filter(payment_status__in=["paid", "refunded"]).count())
        self.assertEqual(BalanceTransaction.objects.filter(kind="refund").count(),
                         Reservation.objects.filter(payment_status="refunded").count())

    def test_running_twice_adds_nothing(self):
        with mock.patch("apps.core.management.commands.demo_week.call_command"):
            call_command("demo_week", stdout=StringIO())
            count = Reservation.objects.count()
            out = StringIO()
            call_command("demo_week", stdout=out)
        self.assertEqual(Reservation.objects.count(), count)
        self.assertIn("already has menus", out.getvalue())
