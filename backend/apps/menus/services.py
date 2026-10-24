"""Dish library, menu building, publishing and finalization rules."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction

from apps.core import audit, clock
from apps.core.exceptions import Conflict, DomainError
from apps.core.models import AuditLog, CanteenSettings

from . import rules
from .models import Dish, Menu, MenuItem

A = AuditLog.Action


def reserved_count(menu: Menu) -> int:
    from apps.reservations.models import Reservation  # lazy: reservations depends on menus

    return Reservation.objects.active().filter(menu=menu).count()


# --- Dish library (FR-29 to FR-31) ---------------------------------------------------
def create_dish(*, by, **fields) -> Dish:
    dish = Dish.objects.create(created_by=by, **fields)
    audit.record(A.DISH_CREATE, actor=by, target=dish)
    return dish


def update_dish(dish: Dish, *, by, **fields) -> Dish:
    for key, value in fields.items():
        setattr(dish, key, value)
    dish.save()
    audit.record(A.DISH_EDIT, actor=by, target=dish)
    return dish  # existing MenuItems keep their snapshot (FR-30)


def archive_dish(dish: Dish, *, by) -> Dish:
    dish.is_archived = True
    dish.save(update_fields=["is_archived", "updated_at"])
    audit.record(A.DISH_ARCHIVE, actor=by, target=dish)
    return dish


# --- Building a menu (FR-07, FR-09, FR-38) ------------------------------------------
def _editable(menu: Menu, cfg: CanteenSettings) -> bool:
    now = clock.now()
    if menu.status in (Menu.Status.DRAFT, Menu.Status.PUBLISHED):
        return now <= rules.reservation_cutoff(menu.date, cfg)
    # Exception (FR-38): an empty placeholder can still get dishes until service starts.
    if menu.status in (Menu.Status.LOCKED, Menu.Status.FINALIZED) and menu.is_placeholder:
        return menu.menu_announced_at is None and now < rules.service_start(menu.date, cfg)
    return False


@transaction.atomic
def get_or_create_menu(day: date, *, by) -> Menu:
    cfg = CanteenSettings.load()
    menu, created = Menu.objects.get_or_create(
        date=day,
        defaults={"created_by": by, "is_paid": cfg.meal_paid_default and cfg.payment_enabled,
                  "price": cfg.meal_price_default if cfg.meal_paid_default and cfg.payment_enabled else None},
    )
    if created:
        audit.record(A.MENU_CREATE, actor=by, target=menu)
    return menu


@transaction.atomic
def set_items(menu: Menu, dish_ids: list[int], *, by) -> Menu:
    """Replace the menu's dishes, copying each dish's details (snapshot)."""
    menu = Menu.objects.select_for_update().get(pk=menu.pk)
    cfg = CanteenSettings.load()
    if not _editable(menu, cfg):
        raise DomainError("menu_locked", "This menu can no longer be edited.")
    dishes = {d.pk: d for d in Dish.objects.filter(pk__in=dish_ids, is_archived=False)}
    if len(dishes) != len(set(dish_ids)):
        raise DomainError("dish_not_found", "One or more dishes do not exist or are archived.")

    had_items = menu.items.exists()
    menu.items.all().delete()
    MenuItem.objects.bulk_create(
        MenuItem(
            menu=menu, dish=d, name=d.name, description=d.description, category=d.category,
            allergens=d.allergens, photo=d.photo.name if d.photo else "", position=i,
        )
        for i, d in enumerate(dishes[pk] for pk in dish_ids)
    )
    audit.record(A.MENU_EDIT, actor=by, target=menu, dishes=dish_ids)

    if menu.is_placeholder and not had_items and dish_ids and menu.menu_announced_at is None:
        menu.menu_announced_at = clock.now()
        menu.save(update_fields=["menu_announced_at", "updated_at"])
        audit.record(A.MENU_ANNOUNCE, actor=by, target=menu)
        # TODO(notifications): email employees who reserved (spec §8 "Menu announced").
    return menu


def publish(menu: Menu, *, by) -> Menu:
    if menu.status != Menu.Status.DRAFT:
        raise Conflict("not_draft", "Only a draft menu can be published.")
    if not menu.items.exists():
        raise DomainError("menu_empty", "Add at least one dish before publishing.")
    if clock.now() > rules.publish_deadline(menu.date):
        raise DomainError("publish_deadline_passed", "The publishing deadline (D-2) has passed.")
    menu.status, menu.published_at = Menu.Status.PUBLISHED, clock.now()
    menu.save(update_fields=["status", "published_at", "updated_at"])
    audit.record(A.MENU_PUBLISH, actor=by, target=menu)
    return menu


@transaction.atomic
def close_day(menu: Menu, *, by, reason: str = "") -> Menu:
    """FR-10: the day is closed and its reservations are cancelled."""
    from apps.reservations.models import Reservation  # lazy: reservations depends on menus

    menu = Menu.objects.select_for_update().get(pk=menu.pk)
    if menu.status == Menu.Status.CLOSED:
        return menu  # idempotent
    if menu.status not in (Menu.Status.DRAFT, Menu.Status.PUBLISHED):
        raise Conflict("cannot_close", "Only a draft or published day can be closed.")
    menu.status, menu.closed_reason = Menu.Status.CLOSED, reason
    menu.save(update_fields=["status", "closed_reason", "updated_at"])
    audit.record(A.MENU_EDIT, actor=by, target=menu, closed=reason)

    now = clock.now()
    for reservation in Reservation.objects.filter(menu=menu, status=Reservation.Status.RESERVED):
        updated = Reservation.objects.filter(pk=reservation.pk, status=Reservation.Status.RESERVED).update(
            status=Reservation.Status.CANCELLED, cancelled_at=now
        )
        if updated:
            audit.record(A.CANCEL, actor=by, target=reservation, reason="day_closed")
    # TODO(notifications): tell the employees whose reservation was cancelled (spec §8).
    return menu


def set_payment(menu: Menu, *, is_paid: bool, price: Decimal | None, by) -> Menu:
    """FR-32: paid flag and price can change until the cutoff, then they are frozen."""
    if clock.now() > rules.reservation_cutoff(menu.date):
        raise DomainError("payment_frozen", "Price is frozen after the reservation cutoff.")
    if is_paid and (price is None or price <= 0):
        raise DomainError("price_required", "A price is required for a paid day.")
    old = (menu.is_paid, menu.price)
    menu.is_paid, menu.price = is_paid, price if is_paid else None
    menu.save(update_fields=["is_paid", "price", "updated_at"])
    audit.record(A.PAYMENT_CONFIG_CHANGE, actor=by, target=menu, old_value=old, new_value=(is_paid, price))
    # TODO(notifications): tell employees who already reserved (spec §8).
    return menu


# --- Finalization (FR-24 to FR-27) --------------------------------------------------
def proposed_plate_count(menu: Menu) -> dict:
    reserved = reserved_count(menu)
    buffer = rules.default_buffer(reserved)
    return {"reserved": reserved, "buffer": buffer, "proposed": reserved + buffer}


@transaction.atomic
def finalize(menu: Menu, *, final_plate_count: int, by=None, auto: bool = False) -> Menu:
    menu = Menu.objects.select_for_update().get(pk=menu.pk)
    cfg = CanteenSettings.load()
    if menu.status not in (Menu.Status.LOCKED, Menu.Status.FINALIZED):
        raise Conflict("not_locked", "A day can be finalized only after the reservation cutoff.")
    if not auto and clock.now() >= rules.service_start(menu.date, cfg):
        raise DomainError("finalization_closed", "The final count is locked once service starts.")
    reserved = reserved_count(menu)
    if final_plate_count < reserved:
        raise DomainError("below_reserved", f"Final count cannot be below the {reserved} reservations.")
    if cfg.kitchen_max_plates and final_plate_count > cfg.kitchen_max_plates:
        raise DomainError("above_kitchen_max", f"Kitchen maximum is {cfg.kitchen_max_plates} plates.")

    menu.status = Menu.Status.FINALIZED
    menu.final_plate_count = final_plate_count
    menu.reserved_count_at_finalization = reserved
    menu.buffer = final_plate_count - reserved
    menu.finalized_by, menu.finalized_at, menu.auto_finalized = by, clock.now(), auto
    menu.save()
    audit.record(A.AUTO_FINALIZE if auto else A.FINALIZE, actor=by, target=menu, plates=final_plate_count)
    # TODO(notifications): send the final count to the chef (FR-28).
    return menu
