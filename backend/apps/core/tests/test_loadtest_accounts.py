"""The load-test preparation never runs on the real database and gives every account money and an open day."""
import os
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.menus.models import Menu


@mock.patch.dict(os.environ, {"LOADTEST_PASSWORD": "Str0ng-pass-123"})
class LoadtestAccountsTests(TestCase):
    def test_refused_on_a_real_database(self):
        with self.assertRaises(CommandError):  # DEBUG off and the test database is not named "loadtest"
            call_command("loadtest_accounts", "--count", "3", stdout=StringIO())
        self.assertFalse(User.objects.filter(work_email__endswith="loadtest.ovagri.test").exists())

    @override_settings(DEBUG=True)
    def test_accounts_with_money_and_an_open_two_menu_day(self):
        call_command("loadtest_accounts", "--count", "3", stdout=StringIO())
        users = User.objects.filter(work_email__startswith="user", work_email__endswith="loadtest.ovagri.test")
        self.assertEqual(sorted(u.balance for u in users), [Decimal("100.000")] * 3)
        menu = Menu.objects.get(status=Menu.Status.PUBLISHED)
        self.assertEqual(menu.choices(), [1, 2])

        call_command("loadtest_accounts", "--count", "3", stdout=StringIO())  # again: nothing new
        self.assertEqual(User.objects.filter(work_email__endswith="loadtest.ovagri.test").count(), 5)
        self.assertEqual(Menu.objects.count(), 1)
