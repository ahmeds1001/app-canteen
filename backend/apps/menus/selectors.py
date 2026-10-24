"""Read-only queries for menus and dishes (kept out of views and services)."""
from datetime import date

from django.db.models import Count, Max, Q, QuerySet

from .models import Dish, Menu

VISIBLE_TO_EMPLOYEES = [Menu.Status.PUBLISHED, Menu.Status.LOCKED, Menu.Status.FINALIZED, Menu.Status.CLOSED]


def dishes(*, q: str = "", category: str = "", include_archived: bool = False) -> QuerySet[Dish]:
    qs = Dish.objects.annotate(last_served_on=Max("menu_items__menu__date"))
    if not include_archived:
        qs = qs.filter(is_archived=False)
    if q:
        qs = qs.filter(name__icontains=q)
    if category:
        qs = qs.filter(category=category)
    return qs


def menus(*, start: date | None, end: date | None, staff: bool) -> QuerySet[Menu]:
    qs = Menu.objects.prefetch_related("items")
    if not staff:
        qs = qs.filter(status__in=VISIBLE_TO_EMPLOYEES)
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)
    if staff:
        qs = qs.annotate(
            reserved_count=Count("reservations", filter=~Q(reservations__status="cancelled"))
        )
    return qs
