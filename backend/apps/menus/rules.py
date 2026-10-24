"""Time rules for a service day D, all in the company time zone.

    publish deadline  = end of D-2   (FR-07, FR-38)
    reservation cutoff = end of D-1  (FR-12)
    service window     = 12:00-15:00 on D by default (Settings)
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings

from apps.core.models import CanteenSettings


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.TIME_ZONE)


def _at(day: date, t: time) -> datetime:
    return datetime.combine(day, t, tzinfo=_tz())


def publish_deadline(day: date, cfg: CanteenSettings | None = None) -> datetime:
    cfg = cfg or CanteenSettings.load()
    return _at(day - timedelta(days=cfg.publish_deadline_days), cfg.cutoff_time)


def reservation_cutoff(day: date, cfg: CanteenSettings | None = None) -> datetime:
    cfg = cfg or CanteenSettings.load()
    return _at(day - timedelta(days=1), cfg.cutoff_time)


def service_start(day: date, cfg: CanteenSettings | None = None) -> datetime:
    cfg = cfg or CanteenSettings.load()
    return _at(day, cfg.service_window_start)


def service_end(day: date, cfg: CanteenSettings | None = None) -> datetime:
    cfg = cfg or CanteenSettings.load()
    return _at(day, cfg.service_window_end)


def default_buffer(reserved: int, cfg: CanteenSettings | None = None) -> int:
    """10% rounded up by default; 0 reservations → 0 extra plates."""
    cfg = cfg or CanteenSettings.load()
    if reserved == 0:
        return 0
    if cfg.buffer_mode == CanteenSettings.BufferMode.FIXED:
        return cfg.buffer_value
    return -(-reserved * cfg.buffer_value // 100)  # ceil without floats
