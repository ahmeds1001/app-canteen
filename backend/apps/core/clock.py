"""Injectable clock (NFR "Clock for tests").

All time-dependent business logic (publishing deadline, cutoff, service window,
no-show marking, payment freeze) must call `clock.now()` / `clock.today()`
instead of `timezone.now()` directly, so tests can freeze time:

    with clock.frozen(datetime(2026, 11, 2, 23, 59, tzinfo=TZ)):
        ...
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime

from django.utils import timezone

_frozen: datetime | None = None


def now() -> datetime:
    """Current aware datetime (UTC internally)."""
    return _frozen if _frozen is not None else timezone.now()


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
