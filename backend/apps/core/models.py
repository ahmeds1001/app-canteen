"""Shared models: base classes, app settings (singleton) and the audit log."""
from datetime import time
from decimal import Decimal

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CanteenSettings(models.Model):
    """Admin-editable settings (spec §6.1 "Setting"). Exactly one row (pk=1).

    Stored as a typed singleton rather than key/value rows so every value is
    validated by the database. Read it with `CanteenSettings.load()`.
    """

    class BufferMode(models.TextChoices):
        FIXED = "fixed", "Fixed number of plates"
        PERCENTAGE = "percentage", "Percentage of reserved count"

    service_weekdays = models.CharField(
        max_length=20, default="0,1,2,3,4,5",
        help_text="Days the canteen opens (0=Monday … 6=Sunday). Decided: Monday to Saturday.",
    )
    cutoff_time = models.TimeField(default=time(23, 59, 59))
    service_window_start = models.TimeField(default=time(12, 0))
    service_window_end = models.TimeField(default=time(15, 0))
    publish_deadline_days = models.PositiveSmallIntegerField(
        default=2, help_text="Menu for day D must be published before the end of D-N."
    )
    booking_horizon_days = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Empty = no limit (decided)."
    )
    buffer_mode = models.CharField(max_length=10, choices=BufferMode.choices, default=BufferMode.PERCENTAGE)
    buffer_value = models.PositiveIntegerField(default=10, help_text="Plates, or percent (rounded up).")
    kitchen_max_plates = models.PositiveIntegerField(null=True, blank=True, help_text="Empty = no ceiling.")
    no_show_warning_threshold = models.PositiveSmallIntegerField(default=3)
    no_show_grace_until = models.DateField(null=True, blank=True, help_text="No warnings before this date.")
    payment_enabled = models.BooleanField(default=False)
    meal_paid_default = models.BooleanField(default=False)
    meal_price_default = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal("0.000"))
    currency = models.CharField(max_length=3, default="TND")
    default_language = models.CharField(max_length=5, default="fr")
    enabled_languages = models.CharField(max_length=50, default="fr,en")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = verbose_name_plural = "Canteen settings"

    def __str__(self) -> str:
        return "Canteen settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def is_service_day(self, day) -> bool:
        return str(day.weekday()) in {d.strip() for d in self.service_weekdays.split(",")}

    @classmethod
    def load(cls) -> "CanteenSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AuditLog(models.Model):
    """Append-only journal of every sensitive action (spec §5 Security, §6.1)."""

    class Action(models.TextChoices):
        REGISTER = "register"
        OTP_SEND = "otp_send"
        OTP_FAIL = "otp_fail"
        VERIFY_EMAIL = "verify_email"
        PASSWORD_RESET_REQUEST = "password_reset_request"
        PASSWORD_RESET = "password_reset"
        PASSWORD_RESET_BY_STAFF = "password_reset_by_staff"
        APPROVE = "approve"
        REJECT = "reject"
        SUSPEND = "suspend"
        REACTIVATE = "reactivate"
        DEACTIVATE = "deactivate"
        ROSTER_IMPORT = "roster_import"
        DISH_CREATE = "dish_create"
        DISH_EDIT = "dish_edit"
        DISH_ARCHIVE = "dish_archive"
        MENU_CREATE = "menu_create"
        MENU_EDIT = "menu_edit"
        MENU_PUBLISH = "menu_publish"
        PLACEHOLDER_PUBLISH = "placeholder_publish"
        MENU_ANNOUNCE = "menu_announce"
        MENU_LOCK = "menu_lock"
        FINALIZE = "finalize"
        AUTO_FINALIZE = "auto_finalize"
        PAYMENT_CONFIG_CHANGE = "payment_config_change"
        RESERVE = "reserve"
        CANCEL = "cancel"
        SERVE = "serve"
        MANUAL_CHECKIN = "manual_checkin"
        MARK_PAID = "mark_paid"
        NO_SHOW = "no_show"
        NO_SHOW_WARNING = "no_show_warning"
        DATA_EXPORT = "data_export"
        ROLE_CHANGE = "role_change"
        SETTING_CHANGE = "setting_change"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )  # NULL = system (scheduled job)
    action = models.CharField(max_length=40, choices=Action.choices, db_index=True)
    target_type = models.CharField(max_length=50, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    old_value = models.TextField(blank=True, default="")
    new_value = models.TextField(blank=True, default="")
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["target_type", "target_id"])]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.target_type}:{self.target_id}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("AuditLog is append-only.")
        super().save(*args, **kwargs)
