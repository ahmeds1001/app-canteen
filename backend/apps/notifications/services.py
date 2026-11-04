"""Notification rules (spec §8). Business code only calls `notify(...)`; pushes go out from the scheduler."""
from __future__ import annotations

from collections.abc import Iterable

from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.core import clock

from .models import Notification, PushSubscription

Kind = Notification.Kind

# Everyone may eat at the canteen (decided 2026-10-26), so every role gets the employee messages.
EATING_ROLES = ("employee", "hr", "chef", "management", "scanner", "admin")


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
    # A concurrent call may create the same row first (unique constraint): it wins. Not
    # bulk_create(ignore_conflicts=True), which SQL Server does not support: one insert in a savepoint,
    # then row by row only if that collides.
    try:
        with transaction.atomic():
            Notification.objects.bulk_create(rows)
        return len(rows)
    except IntegrityError:
        created = 0
        for row in rows:
            try:
                with transaction.atomic():
                    row.save(force_insert=True)
                created += 1
            except IntegrityError:
                pass
        return created


def resolve(kind: str, *, dedupe_key: str, users: Iterable | None = None) -> int:
    """The matter behind these notifications was dealt with: mark them handled — and read — for every
    recipient (or only `users`). Rows are kept; idempotent."""
    now = clock.now()
    rows = Notification.objects.filter(kind=kind, dedupe_key=dedupe_key, resolved_at__isnull=True)
    if users is not None:
        rows = rows.filter(user__in=list(users))
    rows.filter(read_at__isnull=True).update(read_at=now)  # first: `rows` still selects them (not resolved yet)
    return rows.update(resolved_at=now)


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
