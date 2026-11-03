"""Read-only queries for reservations."""
from datetime import date

from django.db.models import Q, QuerySet

from apps.menus.models import Menu

from .models import Reservation

R = Reservation.Status


def day_list(day: date, *, status: str = "", q: str = "") -> QuerySet[Reservation]:
    """Everyone who reserved that day (scanner and management, decided 2026-11-03), cancelled included."""
    qs = (
        Reservation.objects.filter(date=day)
        .select_related("user", "menu")
        .prefetch_related("menu__items")
        .order_by("user__last_name", "user__first_name", "-reserved_at")
    )
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(user__last_name__icontains=q) | Q(user__first_name__icontains=q)
            | Q(user__employee_number__icontains=q) | Q(user__department__icontains=q)
        )
    return qs


def day_summary(day: date) -> dict:
    """Totals of the day, per status and per menu, plus the day's menu (dishes per menu, price)."""
    menu = Menu.objects.filter(date=day).prefetch_related("items").first()
    rows = Reservation.objects.filter(date=day)
    counts = {status: rows.filter(status=status).count() for status in R.values}
    active = rows.exclude(status=R.CANCELLED)
    return {
        "date": day,
        "menu": None if menu is None else {
            "status": menu.status,
            "is_placeholder": menu.is_placeholder,
            "price": str(menu.price) if menu.is_paid and menu.price else None,  # "3.000", like the other APIs
            "final_plate_count": menu.final_plate_count,
            "final_plates_by_choice": menu.final_plates_by_choice,
            "choices": [
                {"choice": c, "dishes": [i.name for i in menu.items.all() if i.choice == c],
                 "reserved": active.filter(choice=c).count()}
                for c in menu.choices()
            ],
        },
        "counts": {**counts, "total": active.count()},
    }
