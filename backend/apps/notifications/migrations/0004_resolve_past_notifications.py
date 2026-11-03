"""Mark as handled the notifications created before "handled for everyone" (2026-11-03) whose matter is
already settled, so the history reads the same as if the rule had always existed. Only `read_at` and
`resolved_at` are set; nothing is deleted. The rules mirror apps.notifications.events."""
from datetime import date

from django.db import migrations
from django.utils import timezone


def resolve_settled(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    User = apps.get_model("accounts", "User")
    Menu = apps.get_model("menus", "Menu")
    Reservation = apps.get_model("reservations", "Reservation")
    now = timezone.now()
    menus = {m.date.isoformat(): m for m in Menu.objects.all()}
    has_items = set(Menu.objects.filter(items__isnull=False).values_list("pk", flat=True))
    pending_ids = set(User.objects.filter(status="pending_hr").values_list("pk", flat=True))

    def filled(menu):
        return menu is not None and (menu.status == "closed" or menu.pk in has_items)

    def settled(note) -> bool:
        key, kind = note.dedupe_key, note.kind
        if kind == "accounts_pending":
            return key.startswith("user:") and int(key[5:]) not in pending_ids
        if kind == "finalization_reminder":
            menu = menus.get(key)
            return menu is not None and menu.status in ("finalized", "closed")
        if kind in ("placeholder_published", "placeholder_empty_at_cutoff"):
            return filled(menus.get(key))
        if kind == "reservation_reminder":
            return Reservation.objects.filter(user_id=note.user_id, date=date.fromisoformat(key)).exclude(
                status="cancelled").exists()
        if kind == "menu_missing":
            return all(
                (m := menus.get(d)) is not None and m.status != "draft" and (not m.is_placeholder or filled(m))
                for d in note.params.get("dates", [])
            )
        return False

    kinds = ["accounts_pending", "finalization_reminder", "placeholder_published", "placeholder_empty_at_cutoff",
             "reservation_reminder", "menu_missing"]
    done = [n.pk for n in Notification.objects.filter(kind__in=kinds, resolved_at__isnull=True) if settled(n)]
    Notification.objects.filter(pk__in=done, read_at__isnull=True).update(read_at=now)
    Notification.objects.filter(pk__in=done).update(resolved_at=now)


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0003_notification_resolved_at"),
        ("accounts", "0004_two_menus_and_balance"),
        ("menus", "0002_two_menus_and_balance"),
        ("reservations", "0002_two_menus_and_balance"),
    ]

    operations = [migrations.RunPython(resolve_settled, migrations.RunPython.noop)]
