"""Notification rules (spec §8). Business code only calls `notify(...)`; pushes go out from the scheduler."""
from __future__ import annotations

from collections.abc import Iterable

from django.db.models import Q

from apps.core import clock

from .models import Notification, PushSubscription

Kind = Notification.Kind

# Roles that eat at the canteen and receive employee messages (the scanner phone and admin do not).
EATING_ROLES = ("employee", "hr", "chef", "management")


def active_users(*roles: str):
    from apps.accounts.models import User  # lazy: accounts imports this module

    return User.objects.filter(role__in=roles, status=User.Status.ACTIVE)


def notify(users: Iterable, kind: str, *, params: dict, link: str = "", dedupe_key: str) -> int:
    """Create one notification per user. Idempotent: an existing (user, kind, dedupe_key) is skipped."""
    users = list({u.pk: u for u in users}.values())
    if not users:
        return 0
    already = set(
        Notification.objects.filter(user__in=users, kind=kind, dedupe_key=dedupe_key).values_list("user_id", flat=True)
    )
    now = clock.now()
    rows = [
        Notification(user=u, kind=kind, params=params, link=link, dedupe_key=dedupe_key, created_at=now)
        for u in users
        if u.pk not in already
    ]
    # ignore_conflicts: a concurrent call that created the same row first wins (unique constraint).
    Notification.objects.bulk_create(rows, ignore_conflicts=True)
    return len(rows)


def for_user(user, limit: int = 50):
    return Notification.objects.filter(user=user)[:limit]


def unread_count(user) -> int:
    return Notification.objects.filter(user=user, read_at__isnull=True).count()


def mark_read(user, notification_id: int) -> None:
    Notification.objects.filter(user=user, pk=notification_id, read_at__isnull=True).update(read_at=clock.now())


def mark_all_read(user) -> int:
    return Notification.objects.filter(user=user, read_at__isnull=True).update(read_at=clock.now())


def set_preferences(user, *, evening_reminder: bool):
    user.evening_reminder = evening_reminder
    user.save(update_fields=["evening_reminder", "updated_at"])
    return user


# --- Push subscriptions (one per phone / browser) -----------------------------------------
def subscribe(user, *, endpoint: str, p256dh: str, auth: str, user_agent: str = "") -> PushSubscription:
    """Idempotent. A browser's endpoint moving to another account (shared phone) follows the new login."""
    sub, _ = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"user": user, "p256dh": p256dh, "auth": auth, "user_agent": user_agent[:300],
                  "revoked_at": None, "created_at": clock.now()},
    )
    return sub


def unsubscribe(user, *, endpoint: str) -> None:
    PushSubscription.objects.filter(user=user, endpoint=endpoint, revoked_at__isnull=True).update(
        revoked_at=clock.now()
    )


def has_active_push(user) -> bool:
    return PushSubscription.objects.filter(Q(user=user) & Q(revoked_at__isnull=True)).exists()
