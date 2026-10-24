"""Injectable clock (NFR "Clock for tests").

All time-dependent business logic (publishing deadline, cutoff, service window,
no-show marking, payment freeze) must call `clock.now()` / `clock.today()`
instead of `timezone.now()` directly, so tests can freeze time:

    with clock.frozen(datetime(2026, 11, 2, 23, 59, tzinfo=TZ)):
        ...

Development only: `python manage.py dev_clock set 2026-11-02 12:30` shifts the clock of the
API and the scheduler (stored in backend/.dev_clock). Ignored unless DEBUG is on.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from django.conf import settings
from django.utils import timezone

_frozen: datetime | None = None
_dev_cache: dict = {"mtime": None, "offset": timedelta(0)}


def dev_clock_file():
    return settings.BASE_DIR / ".dev_clock"


def dev_offset() -> timedelta:
    """Shift set by `manage.py dev_clock` (re-read when the file changes). Zero outside DEBUG."""
    if not settings.DEBUG:
        return timedelta(0)
    try:
        mtime = dev_clock_file().stat().st_mtime
    except FileNotFoundError:
        _dev_cache.update(mtime=None, offset=timedelta(0))
        return timedelta(0)
    if mtime != _dev_cache["mtime"]:
        try:
            seconds = float(json.loads(dev_clock_file().read_text())["offset_seconds"])
        except (OSError, ValueError, KeyError):
            seconds = 0.0
        _dev_cache.update(mtime=mtime, offset=timedelta(seconds=seconds))
    return _dev_cache["offset"]


def now() -> datetime:
    """Current aware datetime (UTC internally)."""
    return _frozen if _frozen is not None else timezone.now() + dev_offset()


def local_now() -> datetime:
    """Current datetime in the company time zone (settings.TIME_ZONE)."""
    return timezone.localtime(now())


def today() -> date:
    """Today's date in the company time zone."""
    return local_now().date()


@contextmanager
def frozen(at: datetime) -> Iterator[None]:
    global _frozen
    if timezone.is_naive(at):
        at = timezone.make_aware(at)
    previous, _frozen = _frozen, at
    try:
        yield
    finally:
        _frozen = previous
