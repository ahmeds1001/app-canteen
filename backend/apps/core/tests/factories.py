"""Small helpers to build test data (no extra dependency)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings

from apps.accounts.models import User
from apps.menus.models import Dish, Menu

TZ = ZoneInfo(settings.TIME_ZONE)
_counter = {"n": 0}


def at(y, m, d, hh=0, mm=0, ss=0) -> datetime:
    return datetime(y, m, d, hh, mm, ss, tzinfo=TZ)


def user(role: str = "employee", status: str = User.Status.ACTIVE, **extra) -> User:
    _counter["n"] += 1
    n = _counter["n"]
    return User.objects.create_user(
        work_email=extra.pop("work_email", f"user{n}@example.com"),
        password=extra.pop("password", "Str0ng-pass-123"),
        first_name="Test", last_name=f"User{n}", employee_number=extra.pop("employee_number", f"E{n:04d}"),
        role=role, status=status, **extra,
    )


def dish(chef: User, name: str = "Couscous") -> Dish:
    return Dish.objects.create(name=name, category="main", created_by=chef)


def menu(day, status: str = Menu.Status.PUBLISHED, **extra) -> Menu:
    return Menu.objects.create(date=day, status=status, **extra)
