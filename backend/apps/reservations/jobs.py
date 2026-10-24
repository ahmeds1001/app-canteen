"""Scheduled jobs for reservations (idempotent)."""
from apps.core import audit, clock
from apps.core.models import AuditLog
from apps.menus import rules

from .models import Reservation


def mark_no_shows() -> int:
    """After the service window, unscanned reservations become No-show."""
    now = clock.now()
    count = 0
    dates = (
        Reservation.objects.filter(status=Reservation.Status.RESERVED, date__lte=clock.today())
        .values_list("date", flat=True)
        .distinct()
    )
    for day in dates:
        if now < rules.service_end(day):
            continue
        for reservation in Reservation.objects.filter(status=Reservation.Status.RESERVED, date=day):
            updated = Reservation.objects.filter(pk=reservation.pk, status=Reservation.Status.RESERVED).update(
                status=Reservation.Status.NO_SHOW, no_show_marked_at=now
            )
            if updated:
                audit.record(AuditLog.Action.NO_SHOW, target=reservation)
                count += 1
    return count
