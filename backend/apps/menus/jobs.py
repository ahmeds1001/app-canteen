"""Scheduled transitions of the menu lifecycle. Each job is idempotent: running it
twice, or late, gives the same result. Called by `manage.py run_scheduler`."""
from datetime import timedelta

from apps.core import audit, clock
from apps.core.models import AuditLog, CanteenSettings
from apps.notifications import events as notification_events

from . import rules, services
from .models import Menu


def publish_placeholders() -> int:
    """FR-38: at the D-2 deadline, open every unpublished day as "Menu to be announced"."""
    cfg = CanteenSettings.load()
    now = clock.now()
    count = 0
    # Every day whose deadline has passed (today and tomorrow with D-2; covers a missed run).
    for delta in range(cfg.publish_deadline_days):
        day = clock.today() + timedelta(days=delta)
        if not cfg.is_service_day(day) or now <= rules.publish_deadline(day, cfg):
            continue
        menu, _ = Menu.objects.get_or_create(date=day, defaults={"created_by": None})
        if menu.status != Menu.Status.DRAFT:
            continue
        menu.status, menu.published_at = Menu.Status.PUBLISHED, now
        menu.is_placeholder = not menu.items.exists()
        menu.save()
        action = AuditLog.Action.PLACEHOLDER_PUBLISH if menu.is_placeholder else AuditLog.Action.MENU_PUBLISH
        audit.record(action, target=menu)
        count += 1
        if menu.is_placeholder:
            notification_events.placeholder_published(menu)
    return count


def lock_menus() -> int:
    """At the cutoff on D-1, Published menus become Locked (menu, price frozen)."""
    count = 0
    for menu in Menu.objects.filter(status=Menu.Status.PUBLISHED, date__lte=clock.today() + timedelta(days=1)):
        if clock.now() > rules.reservation_cutoff(menu.date):
            menu.status = Menu.Status.LOCKED
            menu.save(update_fields=["status", "updated_at"])
            audit.record(AuditLog.Action.MENU_LOCK, target=menu)
            count += 1
            reserved = services.reserved_count(menu)
            if menu.is_placeholder and reserved and not menu.items.exists():
                notification_events.placeholder_empty_at_cutoff(menu, reserved)
    return count


def auto_finalize() -> int:
    """FR-26: at service start, finalize days management did not finalize."""
    count = 0
    for menu in Menu.objects.filter(status=Menu.Status.LOCKED, date__lte=clock.today()):
        if clock.now() >= rules.service_start(menu.date):
            proposal = services.proposed_plate_count(menu)
            services.finalize(menu, final_plate_count=proposal["proposed"], auto=True)
            count += 1
    return count


def close_finished_days() -> int:
    """After the service window, Finalized days become Closed."""
    count = 0
    for menu in Menu.objects.filter(status=Menu.Status.FINALIZED, date__lte=clock.today()):
        if clock.now() >= rules.service_end(menu.date):
            menu.status = Menu.Status.CLOSED
            menu.save(update_fields=["status", "updated_at"])
            count += 1
    return count
