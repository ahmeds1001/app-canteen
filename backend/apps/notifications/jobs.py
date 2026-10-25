"""Scheduled notification jobs (idempotent: daily messages use the date as dedupe key)."""
from datetime import timedelta

from apps.core import clock
from apps.core.models import CanteenSettings
from apps.menus import rules
from apps.menus.models import Menu

from . import messages, push, services
from .models import Notification, PushSubscription
from .services import EATING_ROLES, Kind, active_users

PUSH_MAX_AGE = timedelta(days=1)
PUSH_BATCH = 500


def _due(at) -> bool:
    return clock.local_now().time() >= at


def finalization_reminder() -> int:
    """Management, at `finalization_reminder_time` on day D, while today is locked and not finalized."""
    cfg = CanteenSettings.load()
    today = clock.today()
    if not _due(cfg.finalization_reminder_time) or clock.now() >= rules.service_start(today, cfg):
        return 0
    menu = Menu.objects.filter(date=today, status=Menu.Status.LOCKED).first()
    if menu is None:
        return 0
    from apps.menus.services import reserved_count

    return services.notify(
        active_users("management"), Kind.FINALIZATION_REMINDER,
        params={"date": today.isoformat(), "reserved": reserved_count(menu),
                "time": cfg.service_window_start.strftime("%H:%M")},
        link="/management/finalize", dedupe_key=today.isoformat(),
    )


def menu_missing_reminder() -> int:
    """Chef, every morning: next service days (one week) with no published menu or an empty placeholder."""
    cfg = CanteenSettings.load()
    if not _due(cfg.menu_missing_reminder_time):
        return 0
    today = clock.today()
    days = [today + timedelta(days=n) for n in range(1, 8)]
    menus = {m.date: m for m in Menu.objects.filter(date__in=days).prefetch_related("items")}
    missing = []
    for day in days:
        if not cfg.is_service_day(day):
            continue
        menu = menus.get(day)
        if menu is None or menu.status == Menu.Status.DRAFT:
            missing.append(day)
        elif menu.is_placeholder and menu.status != Menu.Status.CLOSED and not menu.items.all():
            missing.append(day)
    if not missing:
        return 0
    return services.notify(
        active_users("chef"), Kind.MENU_MISSING, params={"dates": [d.isoformat() for d in missing]},
        link="/chef/planner", dedupe_key=today.isoformat(),
    )


def evening_reservation_reminder() -> int:
    """Employees with no reservation for tomorrow, at `evening_reminder_time`, while tomorrow is still open."""
    from apps.reservations.models import Reservation

    cfg = CanteenSettings.load()
    if not _due(cfg.evening_reminder_time):
        return 0
    tomorrow = clock.today() + timedelta(days=1)
    menu = Menu.objects.filter(date=tomorrow, status=Menu.Status.PUBLISHED).first()
    if menu is None or clock.now() > rules.reservation_cutoff(tomorrow, cfg):
        return 0
    reserved = Reservation.objects.active().filter(date=tomorrow).values("user_id")
    users = active_users(*EATING_ROLES).filter(evening_reminder=True).exclude(pk__in=reserved)
    return services.notify(
        users, Kind.RESERVATION_REMINDER,
        params={"date": tomorrow.isoformat(), "dishes": list(menu.items.values_list("name", flat=True))},
        link="/", dedupe_key=tomorrow.isoformat(),
    )


def send_pending_pushes() -> int:
    """Send each new notification to the user's phones. Requests never wait for the push service."""
    now = clock.now()
    pending = Notification.objects.filter(pushed_at__isnull=True)
    # Too old to be useful on a lock screen (or push was off): keep in-app only.
    pending.filter(created_at__lt=now - PUSH_MAX_AGE).update(pushed_at=now)
    if not push.enabled():
        pending.update(pushed_at=now)
        return 0

    sent = 0
    for note in pending.select_related("user").order_by("created_at")[:PUSH_BATCH]:
        # Claim first, so two scheduler processes never send the same push twice.
        if not Notification.objects.filter(pk=note.pk, pushed_at__isnull=True).update(pushed_at=now):
            continue
        subs = list(PushSubscription.objects.filter(user=note.user, revoked_at__isnull=True))
        if not subs:
            continue
        title, body = messages.render(note.kind, note.params, note.user.preferred_language)
        payload = {"title": title, "body": body, "url": note.link or "/", "tag": f"{note.kind}-{note.pk}"}
        for sub in subs:
            if push.send(sub, payload):
                sent += 1
            else:
                PushSubscription.objects.filter(pk=sub.pk, revoked_at__isnull=True).update(revoked_at=now)
    return sent
