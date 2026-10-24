"""Development only: move the app's clock to test time rules (cutoff, finalization, service window).

    python manage.py dev_clock                       # show the current app time
    python manage.py dev_clock set 2026-10-26 11:00  # company time zone; the clock then runs on from there
    python manage.py dev_clock reset                 # back to real time

The API and the scheduler both read backend/.dev_clock, so no restart is needed. After `set`
and `reset`, one scheduler tick runs immediately so menus lock / finalize without waiting.
"""
import json
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core import clock
from apps.core.management.commands.run_scheduler import tick


class Command(BaseCommand):
    help = "Shift the app clock in development (DEBUG only)."

    def add_arguments(self, parser):
        parser.add_argument("action", nargs="?", choices=["show", "set", "reset"], default="show")
        parser.add_argument("when", nargs="*", help='"YYYY-MM-DD HH:MM" in the company time zone')

    def handle(self, *args, action="show", when=(), **options):
        if not settings.DEBUG:
            raise CommandError("dev_clock is only available when DEBUG is on.")
        path = clock.dev_clock_file()

        if action == "set":
            try:
                target = datetime.fromisoformat(" ".join(when).replace("T", " "))
            except ValueError as exc:
                raise CommandError('Give a date and time, e.g. dev_clock set 2026-10-26 11:00') from exc
            if timezone.is_naive(target):
                target = timezone.make_aware(target)
            offset = (target - timezone.now()).total_seconds()
            path.write_text(json.dumps({"offset_seconds": offset, "target": target.isoformat()}))
            self.stdout.write(f"Scheduler tick: {tick()}")
        elif action == "reset":
            path.unlink(missing_ok=True)
            self.stdout.write(f"Scheduler tick: {tick()}")

        shifted = "shifted" if clock.dev_offset() else "real time"
        self.stdout.write(f"App time: {clock.local_now():%A %Y-%m-%d %H:%M} ({shifted})")
