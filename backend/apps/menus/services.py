"""Dish library, menu building, publishing and finalization rules."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Count

from apps.core import audit, clock
from apps.core.exceptions import Conflict, DomainError
from apps.core.models import AuditLog, CanteenSettings
from apps.notifications import events as notification_events

from . import images, rules
from .models import Dish, Menu, MenuItem

A = AuditLog.Action


def reserved_count(menu: Menu) -> int:
    from apps.reservations.models import Reservation  # lazy: reservations depends on menus

    return Reservation.objects.active().filter(menu=menu).count()


def reserved_by_choice(menu: Menu) -> dict[int, int]:
    """Active reservations per menu of the day, every offered menu included (0 when nobody chose it)."""
    from apps.reservations.models import Reservation

    counts = dict(
        Reservation.objects.active().filter(menu=menu).order_by().values_list("choice").annotate(n=Count("id"))
    )
    return {choice: counts.get(choice, 0) for choice in sorted(set(menu.choices()) | set(counts))}


# --- Dish library (FR-29 to FR-31) ---------------------------------------------------
def _with_prepared_photo(fields: dict) -> dict:
    if fields.get("photo"):
        fields["photo"] = images.prepare_dish_photo(fields["photo"])
    return fields


def create_dish(*, by, **fields) -> Dish:
    dish = Dish.objects.create(created_by=by, **_with_prepared_photo(fields))
    audit.record(A.DISH_CREATE, actor=by, target=dish)
    return dish


def update_dish(dish: Dish, *, by, **fields) -> Dish:
    for key, value in _with_prepared_photo(fields).items():
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
def set_items(menu: Menu, dish_ids: list[int], *, by, dish_ids_2: list[int] | None = None) -> Menu:
    """Replace the day's dishes, copying each dish's details (snapshot). `dish_ids` is menu 1;
    `dish_ids_2`, when not empty, is a second menu employees can choose instead (decided 2026-11-03)."""
    from apps.reservations.models import Reservation

    dish_ids_2 = dish_ids_2 or []
    menu = Menu.objects.select_for_update().get(pk=menu.pk)
    cfg = CanteenSettings.load()
    if not _editable(menu, cfg):
        raise DomainError("menu_locked", "This menu can no longer be edited.")
    if not dish_ids:
        raise DomainError("menu_empty", "Menu 1 needs at least one dish.")
    wanted = set(dish_ids) | set(dish_ids_2)
    dishes = {d.pk: d for d in Dish.objects.filter(pk__in=wanted, is_archived=False)}
    if len(dishes) != len(wanted):
        raise DomainError("dish_not_found", "One or more dishes do not exist or are archived.")
    if not dish_ids_2 and Reservation.objects.active().filter(menu=menu, choice=2).exists():
        raise Conflict("choice_has_reservations", "Employees reserved menu 2: it cannot be removed.")

    had_items = menu.items.exists()
    menu.items.all().delete()
    MenuItem.objects.bulk_create(
        MenuItem(
            menu=menu, choice=choice, dish=d, name=d.name, description=d.description, category=d.category,
            allergens=d.allergens, photo=d.photo.name if d.photo else "", position=i,
        )
        for choice, ids in ((1, dish_ids), (2, dish_ids_2))
        for i, d in enumerate(dishes[pk] for pk in ids)
    )
    audit.record(A.MENU_EDIT, actor=by, target=menu, dishes=dish_ids, dishes_2=dish_ids_2)

    if menu.is_placeholder and not had_items and dish_ids and menu.menu_announced_at is None:
        menu.menu_announced_at = clock.now()
        menu.save(update_fields=["menu_announced_at", "updated_at"])
        audit.record(A.MENU_ANNOUNCE, actor=by, target=menu)
        notification_events.menu_announced(menu)
        notification_events.menu_filled(menu)
    elif had_items and menu.status == Menu.Status.PUBLISHED:
        notification_events.menu_changed(menu)  # only reaches employees who already reserved
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
    notification_events.menus_published()
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

    from apps.wallet import services as wallet  # lazy: wallet depends on reservations

    now = clock.now()
    cancelled_for = []
    for reservation in Reservation.objects.filter(menu=menu, status=Reservation.Status.RESERVED).select_related("user"):
        updated = Reservation.objects.filter(pk=reservation.pk, status=Reservation.Status.RESERVED).update(
            status=Reservation.Status.CANCELLED, cancelled_at=now
        )
        if updated:
            audit.record(A.CANCEL, actor=by, target=reservation, reason="day_closed")
            wallet.refund_meal(reservation, by=by)  # the canteen closed: the meal is paid back
            cancelled_for.append(reservation.user)
    notification_events.day_closed(menu, cancelled_for)
    notification_events.menu_filled(menu)  # nothing left to publish or fill for a closed day
    return menu


def set_payment(menu: Menu, *, is_paid: bool, price: Decimal | None, by) -> Menu:
    """FR-32: one price per day, the same for both menus; it can change until the cutoff, then it is frozen.
    Since the prepaid balance (2026-11-03) a meal is paid when reserved: a new price applies to new
    reservations only, so nobody who already reserved is notified."""
    if clock.now() > rules.reservation_cutoff(menu.date):
        raise DomainError("payment_frozen", "Price is frozen after the reservation cutoff.")
    if is_paid and (price is None or price <= 0):
        raise DomainError("price_required", "A price is required for a paid day.")
    old = (menu.is_paid, menu.price)
    menu.is_paid, menu.price = is_paid, price if is_paid else None
    menu.save(update_fields=["is_paid", "price", "updated_at"])
    audit.record(A.PAYMENT_CONFIG_CHANGE, actor=by, target=menu, old_value=old, new_value=(is_paid, price))
    return menu


# --- Finalization (FR-24 to FR-27), one plate count per menu of the day ---------------
def proposed_plate_count(menu: Menu) -> dict:
    """Reservations + buffer, per menu and in total (10 % per menu, rounded up)."""
    choices = []
    for choice, reserved in reserved_by_choice(menu).items():
        buffer = rules.default_buffer(reserved)
        choices.append({"choice": choice, "reserved": reserved, "buffer": buffer, "proposed": reserved + buffer})
    return {
        "reserved": sum(c["reserved"] for c in choices),
        "buffer": sum(c["buffer"] for c in choices),
        "proposed": sum(c["proposed"] for c in choices),
        "choices": choices,
    }


@transaction.atomic
def finalize(menu: Menu, *, plates: dict[int, int], by=None, auto: bool = False) -> Menu:
    """`plates` gives the number of plates per menu, e.g. {1: 25, 2: 12}."""
    menu = Menu.objects.select_for_update().get(pk=menu.pk)
    cfg = CanteenSettings.load()
    if menu.status not in (Menu.Status.LOCKED, Menu.Status.FINALIZED):
        raise Conflict("not_locked", "A day can be finalized only after the reservation cutoff.")
    if not auto and clock.now() >= rules.finalization_deadline(menu.date, cfg):
        raise DomainError("finalization_closed", "The final count is locked after the finalization deadline.")
    reserved = reserved_by_choice(menu)
    plates = {int(choice): count for choice, count in plates.items()}
    if set(plates) != set(reserved):
        raise DomainError("plates_per_menu_required", "Give the number of plates for each menu of the day.")
    for choice, count in plates.items():
        if count < reserved[choice]:
            raise DomainError("below_reserved", f"Menu {choice}: cannot be below its {reserved[choice]} reservations.")
    total, total_reserved = sum(plates.values()), sum(reserved.values())
    if cfg.kitchen_max_plates and total > cfg.kitchen_max_plates:
        raise DomainError("above_kitchen_max", f"Kitchen maximum is {cfg.kitchen_max_plates} plates.")

    menu.status = Menu.Status.FINALIZED
    menu.final_plate_count, menu.reserved_count_at_finalization = total, total_reserved
    menu.buffer = total - total_reserved
    menu.final_plates_by_choice = {str(c): n for c, n in sorted(plates.items())}
    menu.reserved_by_choice_at_finalization = {str(c): n for c, n in sorted(reserved.items())}
    menu.finalized_by, menu.finalized_at, menu.auto_finalized = by, clock.now(), auto
    menu.save()
    audit.record(A.AUTO_FINALIZE if auto else A.FINALIZE, actor=by, target=menu, plates=menu.final_plates_by_choice)
    notification_events.day_finalized(menu)  # FR-28
    return menu
