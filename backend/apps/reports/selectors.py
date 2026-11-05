"""Reporting queries (FR-21 to FR-23, FR-36, FR-45). No models of its own: it reads the others."""
import calendar
from datetime import date
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.core import clock
from apps.core.models import CanteenSettings
from apps.menus.models import Menu
from apps.reservations.models import Reservation
from apps.wallet.models import BalanceTransaction

R = Reservation.Status
P = Reservation.PaymentStatus


def month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def monthly_attendance(year: int, month: int, *, department: str = "", q: str = "") -> dict:
    """Management dashboard (FR-22, FR-23): per employee and for one month, reserved vs served.

    `no_show_rate` = absences / (served + absences): only finished days count, a reservation still to be
    served ("pending") is not an absence. Every active account is listed, even with no reservation, plus
    anyone who reserved that month (a suspended or deactivated account keeps its history).
    """
    start, end = month_bounds(year, month)
    in_month = Q(reservations__date__range=(start, end))
    active = in_month & ~Q(reservations__status=R.CANCELLED)
    ids = set(User.objects.filter(status=User.Status.ACTIVE).values_list("pk", flat=True))
    ids |= set(Reservation.objects.filter(date__range=(start, end)).values_list("user_id", flat=True))
    users = User.objects.filter(pk__in=ids)
    if department:
        users = users.filter(department=department)
    if q:
        users = users.filter(Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(employee_number__icontains=q))
    users = users.annotate(
        reserved=Count("reservations", filter=active),
        served=Count("reservations", filter=in_month & Q(reservations__status=R.SERVED)),
        no_show=Count("reservations", filter=in_month & Q(reservations__status=R.NO_SHOW)),
        pending=Count("reservations", filter=in_month & Q(reservations__status=R.RESERVED)),
        cancelled=Count("reservations", filter=in_month & Q(reservations__status=R.CANCELLED)),
        menu_1=Count("reservations", filter=active & Q(reservations__choice=1)),
        menu_2=Count("reservations", filter=active & Q(reservations__choice=2)),
        spent=Sum("reservations__amount_due", filter=in_month & Q(reservations__payment_status=P.PAID)),
    ).order_by("last_name", "first_name")

    threshold = CanteenSettings.load().no_show_warning_threshold
    rows = [
        {
            "user_id": u.pk,
            "name": u.full_name,
            "employee_number": u.employee_number,
            "department": u.department,
            "status": u.status,
            "reserved": u.reserved,
            "served": u.served,
            "no_show": u.no_show,
            "pending": u.pending,
            "cancelled": u.cancelled,
            "menu_1": u.menu_1,
            "menu_2": u.menu_2,
            "no_show_rate": _rate(u.no_show, u.served + u.no_show),
            "spent": _tnd(u.spent),
            "over_threshold": u.no_show >= threshold,
        }
        for u in users
    ]
    keys = ("reserved", "served", "no_show", "pending", "cancelled", "menu_1", "menu_2")
    totals = {k: sum(r[k] for r in rows) for k in keys}
    totals.update(
        employees=len(rows),
        eating=sum(1 for r in rows if r["reserved"]),
        spent=_tnd(sum((Decimal(r["spent"]) for r in rows), Decimal("0"))),
        no_show_rate=_rate(totals["no_show"], totals["served"] + totals["no_show"]),
        over_threshold=sum(1 for r in rows if r["over_threshold"]),
    )
    # order_by() first: User's default ordering (last name) would make DISTINCT keep one row per employee.
    departments = sorted(
        User.objects.filter(pk__in=ids).exclude(department="").order_by()
        .values_list("department", flat=True).distinct()
    )
    return {"month": f"{year:04d}-{month:02d}", "threshold": threshold, "departments": departments,
            "totals": totals, "rows": rows}


def employee_month(user: User, year: int, month: int):
    """One employee's reservations of the month, day by day (the drill-down of the dashboard)."""
    start, end = month_bounds(year, month)
    return (
        Reservation.objects.filter(user=user, date__range=(start, end))
        .select_related("menu").prefetch_related("menu__items").order_by("date", "-reserved_at")
    )


def _tnd(value: Decimal | None) -> str:
    """"9.000", like every other amount of the API (JSON numbers would lose the 3 decimals)."""
    return f"{value or Decimal('0'):.3f}"


def _rate(part: int, whole: int) -> float:
    return round(part / whole, 3) if whole else 0.0


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


# --- Cash received (FR-45, decided 2026-11-04) ------------------------------------------
def cash_report(viewer: User, day: date | None = None) -> dict:
    """Money received at the canteen on one day (company time zone).

    The cashier sees only her own top-ups of today (FR-47): the amount she hands over at the end of the day.
    Management (and admin) see any day, split per cashier, plus that day's corrections, which count in the
    total: a wrong top-up fixed the same day changes the cash expected. Meals paid from balances are not cash
    and are left out.
    """
    K = BalanceTransaction.Kind
    mine = viewer.role == User.Role.CASHIER
    day = clock.today() if mine or day is None else day
    entries = BalanceTransaction.objects.filter(created_at__date=day).select_related("user", "by")
    entries = entries.filter(kind=K.TOPUP, by=viewer) if mine else entries.filter(kind__in=[K.TOPUP, K.CORRECTION])
    entries = list(entries.order_by("created_at", "id"))

    topups = [e for e in entries if e.kind == K.TOPUP]
    corrections = [e for e in entries if e.kind == K.CORRECTION]
    cashiers: dict[int | None, dict] = {}
    for e in topups:
        row = cashiers.setdefault(e.by_id, {"id": e.by_id, "name": e.by.full_name if e.by else "—",
                                            "count": 0, "total": Decimal("0")})
        row["count"] += 1
        row["total"] += e.amount
    total_topups = sum((e.amount for e in topups), Decimal("0"))
    total_corrections = sum((e.amount for e in corrections), Decimal("0"))
    return {
        "date": day.isoformat(),
        "scope": "mine" if mine else "all",
        "topups": {"count": len(topups), "total": _tnd(total_topups)},
        "corrections": {"count": len(corrections), "total": _tnd(total_corrections)},
        "total": _tnd(total_topups + total_corrections),
        "cashiers": [{**c, "total": _tnd(c["total"])}
                     for c in sorted(cashiers.values(), key=lambda c: (-c["total"], c["name"]))],
        "rows": [
            {
                # Company offset, like the serializers: the app shows the wall-clock part as it is.
                "id": e.pk, "at": timezone.localtime(e.created_at).isoformat(), "kind": e.kind,
                "amount": _tnd(e.amount),
                "employee": e.user.full_name, "employee_number": e.user.employee_number,
                "by": e.by.full_name if e.by else "", "note": e.note,
            }
            for e in entries
        ],
    }
