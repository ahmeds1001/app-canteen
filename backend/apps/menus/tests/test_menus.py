from datetime import date

from django.test import TestCase

from apps.core import clock
from apps.core.exceptions import DomainError
from apps.core.tests import factories as f
from apps.menus import jobs, rules, services
from apps.menus.models import Menu
from apps.reservations import services as reservation_services

MONDAY = date(2026, 11, 2)


class BufferTests(TestCase):
    def test_default_buffer_is_10_percent_rounded_up(self):
        self.assertEqual(rules.default_buffer(47), 5)
        self.assertEqual(rules.default_buffer(50), 5)
        self.assertEqual(rules.default_buffer(1), 1)
        self.assertEqual(rules.default_buffer(0), 0)


class PublishingTests(TestCase):
    def setUp(self):
        self.chef = f.user(role="chef")

    def test_cannot_publish_after_d_minus_2(self):
        menu = f.menu(MONDAY, status=Menu.Status.DRAFT)
        services.set_items(menu, [f.dish(self.chef).pk], by=self.chef)
        with clock.frozen(f.at(2026, 11, 1, 0, 0, 1)):  # Sunday = D-1
            with self.assertRaises(DomainError):
                services.publish(menu, by=self.chef)

    def test_placeholder_published_at_deadline(self):
        """FR-38: no menu for Monday at the end of Saturday → "Menu to be announced"."""
        with clock.frozen(f.at(2026, 11, 1, 0, 5)):  # Sunday 00:05
            jobs.publish_placeholders()
        menu = Menu.objects.get(date=MONDAY)
        self.assertEqual(menu.status, Menu.Status.PUBLISHED)
        self.assertTrue(menu.is_placeholder)

    def test_no_placeholder_on_closed_weekdays(self):
        with clock.frozen(f.at(2026, 10, 31, 0, 5)):  # Saturday → would target Sunday
            jobs.publish_placeholders()
        self.assertFalse(Menu.objects.filter(date=date(2026, 11, 1)).exists())

    def test_saturday_is_a_service_day(self):
        """The company works Saturdays: Saturday gets a placeholder at its D-2 deadline."""
        with clock.frozen(f.at(2026, 10, 30, 0, 5)):  # Friday → targets Saturday 31
            jobs.publish_placeholders()
        self.assertTrue(Menu.objects.get(date=date(2026, 10, 31)).is_placeholder)

    def test_empty_placeholder_editable_until_service_start(self):
        menu = f.menu(MONDAY, status=Menu.Status.LOCKED, is_placeholder=True)
        with clock.frozen(f.at(2026, 11, 2, 11, 0)):
            services.set_items(menu, [f.dish(self.chef).pk], by=self.chef)
        menu.refresh_from_db()
        self.assertIsNotNone(menu.menu_announced_at)

    def test_dish_edit_does_not_change_published_menu(self):
        dish = f.dish(self.chef, "Lablabi")
        menu = f.menu(MONDAY, status=Menu.Status.DRAFT)
        with clock.frozen(f.at(2026, 10, 29, 10)):
            services.set_items(menu, [dish.pk], by=self.chef)
        services.update_dish(dish, by=self.chef, name="Lablabi spécial")
        self.assertEqual(menu.items.get().name, "Lablabi")


class CloseDayTests(TestCase):
    def test_close_day_cancels_reservations(self):
        """FR-10: closing a published day cancels its active reservations."""
        chef = f.user(role="chef")
        menu = f.menu(MONDAY)
        with clock.frozen(f.at(2026, 10, 30, 10)):
            reservation = reservation_services.reserve(f.user(), menu)
            services.close_day(menu, by=chef, reason="Jour férié")
            services.close_day(menu, by=chef, reason="Jour férié")  # idempotent
        menu.refresh_from_db()
        reservation.refresh_from_db()
        self.assertEqual(menu.status, Menu.Status.CLOSED)
        self.assertEqual(reservation.status, "cancelled")


class FinalizationTests(TestCase):
    def setUp(self):
        self.manager = f.user(role="management")
        self.menu = f.menu(MONDAY)
        with clock.frozen(f.at(2026, 10, 30, 10)):
            for _ in range(20):
                reservation_services.reserve(f.user(), self.menu)
        self.menu.status = Menu.Status.LOCKED
        self.menu.save()

    def test_proposal_and_manual_finalize(self):
        self.assertEqual(services.proposed_plate_count(self.menu), {"reserved": 20, "buffer": 2, "proposed": 22})
        with clock.frozen(f.at(2026, 11, 2, 9)):
            menu = services.finalize(self.menu, final_plate_count=25, by=self.manager)
        self.assertEqual((menu.status, menu.buffer), (Menu.Status.FINALIZED, 5))

    def test_cannot_finalize_below_reserved(self):
        with clock.frozen(f.at(2026, 11, 2, 9)):
            with self.assertRaises(DomainError):
                services.finalize(self.menu, final_plate_count=19, by=self.manager)

    def test_locked_at_the_finalization_deadline(self):
        """FR-27: the count locks at 10:00 by default (decided 2026-10-26), before service at 12:00."""
        with clock.frozen(f.at(2026, 11, 2, 9, 59)):
            services.finalize(self.menu, final_plate_count=22, by=self.manager)
        with clock.frozen(f.at(2026, 11, 2, 10, 0)):
            with self.assertRaises(DomainError):
                services.finalize(self.menu, final_plate_count=23, by=self.manager)

    def test_no_auto_finalize_before_the_deadline(self):
        with clock.frozen(f.at(2026, 11, 2, 9, 59)):
            jobs.auto_finalize()
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.status, Menu.Status.LOCKED)

    def test_auto_finalize_at_the_deadline(self):
        with clock.frozen(f.at(2026, 11, 2, 10, 0, 30)):
            jobs.auto_finalize()
        self.menu.refresh_from_db()
        self.assertTrue(self.menu.auto_finalized)
        self.assertEqual(self.menu.final_plate_count, 22)
