"""Reporting queries (FR-21 to FR-23, FR-36). No models of its own: it reads the others."""
from datetime import date

from django.db.models import Count, Q, Sum

from apps.menus.models import Menu
from apps.reservations.models import Reservation

R = Reservation.Status


def daily_summary(start: date, end: date) -> list[dict]:
    """Reserved vs finalized vs served vs no-show per day, with the buffer actually used."""
    rows = (
        Menu.objects.filter(date__range=(start, end))
        .annotate(
            reserved=Count("reservations", filter=~Q(reservations__status=R.CANCELLED)),
            served=Count("reservations", filter=Q(reservations__status=R.SERVED)),
            no_show=Count("reservations", filter=Q(reservations__status=R.NO_SHOW)),
            unpaid=Count("reservations", filter=Q(reservations__payment_status="unpaid")),
            collected=Sum("reservations__amount_due", filter=Q(reservations__payment_status="paid")),
        )
        .order_by("date")
    )
    return [
        {
            "date": m.date,
            "status": m.status,
            "is_placeholder": m.is_placeholder,
            "reserved": m.reserved,
            "final_plate_count": m.final_plate_count,
            "buffer": m.buffer,
            "auto_finalized": m.auto_finalized,
            "served": m.served,
            "no_show": m.no_show,
            "unpaid": m.unpaid,
            "collected": m.collected or 0,
        }
        for m in rows
    ]


def employee_attendance(start: date, end: date) -> list[dict]:
    """Per employee: reserved, served, no-shows and no-show rate (HR, FR-22)."""
    rows = (
        Reservation.objects.active()
        .filter(date__range=(start, end))
        .values("user_id", "user__first_name", "user__last_name", "user__employee_number", "user__department")
        .annotate(
            reserved=Count("id"),
            served=Count("id", filter=Q(status=R.SERVED)),
            no_show=Count("id", filter=Q(status=R.NO_SHOW)),
        )
        .order_by("user__last_name")
    )
    return [
        {
            "user_id": r["user_id"],
            "name": f'{r["user__first_name"]} {r["user__last_name"]}',
            "employee_number": r["user__employee_number"],
            "department": r["user__department"],
            "reserved": r["reserved"],
            "served": r["served"],
            "no_show": r["no_show"],
            "no_show_rate": round(r["no_show"] / r["reserved"], 3) if r["reserved"] else 0,
        }
        for r in rows
    ]
