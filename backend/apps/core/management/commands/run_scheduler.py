"""Run every scheduled job in order. Each job is idempotent, so a tick can run
late or twice safely.

    python manage.py run_scheduler --once     # one tick (cron every minute)
    python manage.py run_scheduler            # loop forever (Docker service)
"""
import logging
import time

from django.core.management.base import BaseCommand

from apps.menus import jobs as menu_jobs
from apps.notifications import jobs as notification_jobs
from apps.reservations import jobs as reservation_jobs

logger = logging.getLogger(__name__)

# Order matters: publish → lock → reminders → finalize → no-shows → close; pushes last (they send what the
# jobs above created).
JOBS = [
    ("publish_placeholders", menu_jobs.publish_placeholders),
    ("lock_menus", menu_jobs.lock_menus),
    ("finalization_reminder", notification_jobs.finalization_reminder),
    ("menu_missing_reminder", notification_jobs.menu_missing_reminder),
    ("evening_reservation_reminder", notification_jobs.evening_reservation_reminder),
    ("auto_finalize", menu_jobs.auto_finalize),
    ("mark_no_shows", reservation_jobs.mark_no_shows),
    ("close_finished_days", menu_jobs.close_finished_days),
    ("send_pending_pushes", notification_jobs.send_pending_pushes),
]


def tick() -> dict[str, int]:
    results = {}
    for name, job in JOBS:
        try:
            results[name] = job()
        except Exception:
            logger.exception("Scheduled job %s failed", name)
            results[name] = -1
    return results


class Command(BaseCommand):
    help = "Run the canteen scheduled jobs."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--interval", type=int, default=60)

    def handle(self, *args, once=False, interval=60, **options):
        while True:
            results = tick()
            if any(results.values()):
                logger.info("Scheduler tick: %s", results)
            if once:
                self.stdout.write(str(results))
                return
            time.sleep(interval)
