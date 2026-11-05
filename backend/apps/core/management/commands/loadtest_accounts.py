"""Prepare a load test (loadtest/README.md): N employee accounts with money, and an open two-menu day to reserve.

    python manage.py loadtest_accounts --count 200

Only on a test database: the company decided data is never deleted, so the 200 accounts and their reservations
would stay forever in the real one. The command refuses unless DEBUG is on or the database name contains "loadtest"
(for example DB_NAME=canteen_loadtest on the company SQL Server). Running it again adds nothing new.
Password of every account: the LOADTEST_PASSWORD environment variable.
"""
import os
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.accounts.models import User
from apps.core import clock
from apps.core.models import CanteenSettings
from apps.menus import rules
from apps.menus import services as menus
from apps.menus.models import Dish, Menu
from apps.wallet import services as wallet

DOMAIN = "loadtest.ovagri.test"
BALANCE = Decimal("100.000")  # enough for a month of meals: the test never runs out of money
DISHES = [("Salade (test de charge)", "starter"), ("Couscous (test de charge)", "main"),
          ("Poisson (test de charge)", "main"), ("Fruit (test de charge)", "dessert")]


class Command(BaseCommand):
    help = "Create load-test accounts and an open day (test databases only)."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=200)

    def handle(self, *args, count: int, **options):
        name = str(connection.settings_dict["NAME"])
        if not settings.DEBUG and "loadtest" not in name:
            raise CommandError(f"Refused on database '{name}': use a separate database whose name contains "
                               "'loadtest' (e.g. DB_NAME=canteen_loadtest). Nothing is ever deleted from the real one.")
        password = os.environ.get("LOADTEST_PASSWORD")
        if not password:
            raise CommandError("Set LOADTEST_PASSWORD: it becomes the password of the load-test accounts.")

        staff = {role: self._user(f"{role}@{DOMAIN}", "Test charge", role.capitalize(), role, password)
                 for role in (User.Role.CHEF, User.Role.CASHIER)}
        created = 0
        for n in range(1, count + 1):
            user = self._user(f"user{n:03d}@{DOMAIN}", f"Charge{n:03d}", "Test", User.Role.EMPLOYEE, password,
                              employee_number=f"LT-{n:04d}")
            if user.balance < BALANCE:
                wallet.top_up(user, BALANCE - user.balance, by=staff[User.Role.CASHIER])
                created += 1
        day = self._open_day(staff[User.Role.CHEF])
        self.stdout.write(f"{count} accounts user001…user{count:03d}@{DOMAIN} ready ({created} topped up to "
                          f"{BALANCE} TND). Day to reserve: {day:%Y-%m-%d}, open until "
                          f"{rules.reservation_cutoff(day):%Y-%m-%d %H:%M}.")

    def _user(self, email, first, last, role, password, **fields) -> User:
        user = User.objects.filter(work_email=email).first()
        if user is None:
            user = User.objects.create_user(email, password, first_name=first, last_name=last, role=role,
                                            status=User.Status.ACTIVE, department="Test de charge", **fields)
        return user

    def _open_day(self, chef) -> date:
        """The first service day that can still be published: two menus, paid 3 TND, open for reservations."""
        cfg = CanteenSettings.load()
        cfg.payment_enabled, cfg.meal_paid_default, cfg.meal_price_default = True, True, Decimal("3.000")
        cfg.save()
        dishes = []
        for dish_name, category in DISHES:
            dish = Dish.objects.filter(name=dish_name, is_archived=False).first()
            dishes.append(dish or menus.create_dish(by=chef, name=dish_name, category=category))
        day = clock.today() + timedelta(days=1)
        while True:
            menu = Menu.objects.filter(date=day).first()
            if menu and menu.status == Menu.Status.PUBLISHED and clock.now() <= rules.reservation_cutoff(day, cfg):
                return day  # already prepared by an earlier run
            if cfg.is_service_day(day) and menu is None and clock.now() <= rules.publish_deadline(day, cfg):
                break
            day += timedelta(days=1)
        menu = menus.get_or_create_menu(day, by=chef)
        menus.set_items(menu, [dishes[0].pk, dishes[1].pk, dishes[3].pk], by=chef,
                        dish_ids_2=[dishes[0].pk, dishes[2].pk, dishes[3].pk])
        menus.publish(menu, by=chef)
        return day
