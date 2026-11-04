"""Canteen settings changed by the admin on the Settings screen (FR-46)."""
from datetime import time

from django.db import transaction

from . import audit
from .exceptions import DomainError, NotAllowed
from .models import AuditLog, CanteenSettings

PAYMENT_FIELDS = {"payment_enabled", "meal_paid_default", "meal_price_default"}
EDITABLE_FIELDS = {
    "service_weekdays", "cutoff_days", "cutoff_time", "publish_deadline_days", "publish_deadline_time",
    "finalization_deadline", "service_window_start", "service_window_end",
    "menu_missing_reminder_time", "finalization_reminder_time", "evening_reminder_time",
    "buffer_mode", "buffer_value", "kitchen_max_plates", "booking_horizon_days",
    "no_show_warning_threshold", "no_show_grace_until", *PAYMENT_FIELDS,
}


def _minutes(t: time) -> float:
    return t.hour * 60 + t.minute + t.second / 60


def _offset(days: int, t: time) -> float:
    """Minutes from 00:00 on day D (negative = before D)."""
    return -days * 24 * 60 + _minutes(t)


def check(cfg: CanteenSettings) -> None:
    """Refuse values that would break the day's sequence (FR-46). Raises DomainError with a stable code."""
    if not {d.strip() for d in cfg.service_weekdays.split(",") if d.strip()}:
        raise DomainError("settings_no_service_day", "At least one service day is needed.")
    publish = _offset(cfg.publish_deadline_days, cfg.publish_deadline_time)
    cutoff = _offset(cfg.cutoff_days, cfg.cutoff_time)
    final = _minutes(cfg.finalization_deadline)
    start, end = _minutes(cfg.service_window_start), _minutes(cfg.service_window_end)
    if not publish < cutoff:
        raise DomainError("settings_publish_after_cutoff", "The menu must be published before reservations close.")
    if not cutoff < final:
        raise DomainError("settings_cutoff_after_finalization", "Reservations must close before finalization.")
    if not final <= start:
        raise DomainError("settings_finalization_after_service", "Finalization must be at or before service start.")
    if not start < end:
        raise DomainError("settings_service_end_before_start", "Service must end after it starts.")
    if not _minutes(cfg.finalization_reminder_time) < final:
        raise DomainError("settings_reminder_after_finalization", "The reminder must come before finalization.")
    if cfg.cutoff_days >= 1 and not _minutes(cfg.evening_reminder_time) < _minutes(cfg.cutoff_time):
        raise DomainError("settings_reminder_after_cutoff", "The evening reminder must come before the cutoff.")
    if cfg.buffer_mode == CanteenSettings.BufferMode.PERCENTAGE and cfg.buffer_value > 100:
        raise DomainError("settings_buffer_too_high", "The buffer cannot exceed 100 %.")


def update_settings(*, by, changes: dict) -> CanteenSettings:
    """Admin only. Applies at once; each changed value is audited with its old and new value."""
    if by.role != "admin":
        raise NotAllowed("admin_only", "Only the admin can change the settings.")
    unknown = set(changes) - EDITABLE_FIELDS
    if unknown:
        raise DomainError("settings_unknown_field", f"Not editable: {', '.join(sorted(unknown))}.")
    with transaction.atomic():
        CanteenSettings.load()  # make sure the row exists before locking it
        cfg = CanteenSettings.objects.select_for_update().get(pk=1)
        old = {field: getattr(cfg, field) for field in changes}
        for field, value in changes.items():
            setattr(cfg, field, value)
        check(cfg)
        changed = [f for f in changes if old[f] != getattr(cfg, f)]
        if not changed:
            return cfg
        cfg.save()
        for field in changed:
            action = AuditLog.Action.SETTING_CHANGE
            if field in PAYMENT_FIELDS:
                action = AuditLog.Action.PAYMENT_CONFIG_CHANGE
            audit.record(action, actor=by, target=cfg, old_value=old[field], new_value=getattr(cfg, field),
                         field=field)
    return cfg
