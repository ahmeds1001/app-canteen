"""One function per message of spec §8: who receives it, with which content. Called by the domain services
and jobs (menus, accounts); they never build notifications themselves."""
from __future__ import annotations

from apps.core import clock

from . import services
from .services import Kind, active_users


def _reserved_users(menu):
    """Users holding a still-open reservation for this menu."""
    from apps.accounts.models import User  # lazy: avoid import cycles at startup

    return User.objects.filter(reservations__menu=menu, reservations__status="reserved").distinct()


def _dishes(menu) -> list[str]:
    return list(menu.items.values_list("name", flat=True))


def account_pending(user) -> None:
    services.notify(
        active_users("hr"), Kind.ACCOUNTS_PENDING,
        params={"name": user.full_name, "email": user.work_email},
        link="/hr/accounts", dedupe_key=f"user:{user.pk}",
    )


def menu_announced(menu) -> None:
    services.notify(
        _reserved_users(menu), Kind.MENU_ANNOUNCED,
        params={"date": menu.date.isoformat(), "dishes": _dishes(menu)}, link="/",
        dedupe_key=menu.date.isoformat(),
    )


def menu_changed(menu) -> None:
    services.notify(
        _reserved_users(menu), Kind.MENU_CHANGED,
        params={"date": menu.date.isoformat(), "dishes": _dishes(menu)}, link="/",
        dedupe_key=f"{menu.date.isoformat()}@{clock.now().isoformat()}",
    )


def price_changed(menu) -> None:
    services.notify(
        _reserved_users(menu), Kind.PRICE_CHANGED,
        params={"date": menu.date.isoformat(), "is_paid": menu.is_paid, "price": str(menu.price or "")},
        link="/", dedupe_key=f"{menu.date.isoformat()}@{clock.now().isoformat()}",
    )


def day_closed(menu, users) -> None:
    services.notify(
        users, Kind.DAY_CLOSED, params={"date": menu.date.isoformat(), "reason": menu.closed_reason},
        link="/", dedupe_key=menu.date.isoformat(),
    )


def placeholder_published(menu) -> None:
    params = {"date": menu.date.isoformat()}
    key = menu.date.isoformat()
    services.notify(active_users("chef"), Kind.PLACEHOLDER_PUBLISHED, params=params, link="/chef/planner",
                    dedupe_key=key)
    services.notify(active_users("management"), Kind.PLACEHOLDER_PUBLISHED, params=params,
                    link="/management/finalize", dedupe_key=key)


def placeholder_empty_at_cutoff(menu, reserved: int) -> None:
    params = {"date": menu.date.isoformat(), "reserved": reserved}
    key = menu.date.isoformat()
    services.notify(active_users("chef"), Kind.PLACEHOLDER_EMPTY_AT_CUTOFF, params=params, link="/chef/planner",
                    dedupe_key=key)
    services.notify(active_users("management"), Kind.PLACEHOLDER_EMPTY_AT_CUTOFF, params=params,
                    link="/management/finalize", dedupe_key=key)


def day_finalized(menu) -> None:
    """FR-28: the chef gets the final plate count (a changed count is sent again)."""
    services.notify(
        active_users("chef"), Kind.DAY_FINALIZED,
        params={"date": menu.date.isoformat(), "plates": menu.final_plate_count,
                "reserved": menu.reserved_count_at_finalization, "buffer": menu.buffer},
        link="/chef/planner", dedupe_key=f"{menu.date.isoformat()}:{menu.finalized_at.isoformat()}",
    )
