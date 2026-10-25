"""In-app notifications and phone push subscriptions (spec §8). Rows are never deleted (rule 4)."""
from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Kind(models.TextChoices):
        ACCOUNTS_PENDING = "accounts_pending"
        MENU_CHANGED = "menu_changed"
        MENU_ANNOUNCED = "menu_announced"
        PRICE_CHANGED = "price_changed"
        DAY_CLOSED = "day_closed"
        PLACEHOLDER_PUBLISHED = "placeholder_published"
        PLACEHOLDER_EMPTY_AT_CUTOFF = "placeholder_empty_at_cutoff"
        FINALIZATION_REMINDER = "finalization_reminder"
        DAY_FINALIZED = "day_finalized"
        MENU_MISSING = "menu_missing"
        RESERVATION_REMINDER = "reservation_reminder"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="notifications")
    kind = models.CharField(max_length=40, choices=Kind.choices)
    params = models.JSONField(default=dict, blank=True)
    link = models.CharField(max_length=200, blank=True, help_text="Frontend path opened when tapped.")
    # Same (user, kind, dedupe_key) is never created twice: scheduled jobs can run late or twice.
    dedupe_key = models.CharField(max_length=100)
    created_at = models.DateTimeField()
    read_at = models.DateTimeField(null=True, blank=True)
    pushed_at = models.DateTimeField(null=True, blank=True, help_text="Push handled (sent, or no device).")

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "kind", "dedupe_key"], name="one_notification_per_event")
        ]
        indexes = [models.Index(fields=["user", "read_at"]), models.Index(fields=["pushed_at", "created_at"])]

    def __str__(self) -> str:
        return f"{self.kind} → {self.user_id} ({self.dedupe_key})"


class PushSubscription(models.Model):
    """One browser/phone that accepted push notifications (Web Push)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="push_subscriptions")
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True, help_text="Turned off, or refused by the push service.")

    def __str__(self) -> str:
        return f"Push for {self.user_id} ({'revoked' if self.revoked_at else 'active'})"
