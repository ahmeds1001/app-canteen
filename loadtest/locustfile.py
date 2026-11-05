"""Load test of the canteen API (loadtest/README.md). Two scenarios, one per class:

    LoginRush         launch day: every account logs in once, all within about a minute
    ReservationRush   the last minutes before the cutoff: log in, then look at menus, reserve, switch, cancel

Accounts user001…userNNN@loadtest.ovagri.test come from `manage.py loadtest_accounts` (password LOADTEST_PASSWORD).
The run fails (exit code 1) when more than 1 % of requests fail or the 95th percentile is above 1 second.
"""
import itertools
import os
import random

from locust import HttpUser, between, events, task
from locust.exception import StopUser

PASSWORD = os.environ.get("LOADTEST_PASSWORD", "")
DOMAIN = "loadtest.ovagri.test"
ACCOUNTS = int(os.environ.get("LOADTEST_ACCOUNTS", "200"))
_numbers = itertools.cycle(range(1, ACCOUNTS + 1))  # each simulated person takes the next account


def login(user: HttpUser) -> bool:
    email = f"user{next(_numbers):03d}@{DOMAIN}"
    with user.client.post("/api/v1/auth/login/", json={"work_email": email, "password": PASSWORD},
                          name="login", catch_response=True) as response:
        if response.status_code != 200:
            response.failure(f"{email}: {response.status_code} {response.text[:120]}")
            return False
        user.client.headers["Authorization"] = f"Bearer {response.json()['access']}"
        return True


class LoginRush(HttpUser):
    """Launch day: everybody opens the app and logs in once."""

    wait_time = between(0, 1)

    @task
    def log_in_once(self):
        login(self)
        raise StopUser()


class ReservationRush(HttpUser):
    """The evening rush: everybody reserves (or changes their mind) for the open day."""

    wait_time = between(1, 5)

    def on_start(self):
        if not login(self):
            raise StopUser()
        menus = self.client.get("/api/v1/menus/", name="menus").json()
        open_days = [m for m in menus if m.get("is_open_for_reservation")]
        if not open_days:
            raise StopUser()
        self.day = os.environ.get("LOADTEST_DATE") or open_days[0]["date"]
        self.reservation_id = None

    @task(3)
    def look_at_menus(self):
        self.client.get("/api/v1/menus/", name="menus")

    @task(5)
    def reserve_or_switch(self):
        r = self.client.post("/api/v1/reservations/", json={"date": self.day, "choice": random.choice([1, 2])},
                             name="reserve")
        if r.status_code in (200, 201):
            self.reservation_id = r.json()["id"]

    @task(2)
    def my_reservations(self):
        self.client.get("/api/v1/reservations/?upcoming=1", name="my reservations")

    @task(1)
    def my_balance(self):
        self.client.get("/api/v1/wallet/me/", name="balance")

    @task(1)
    def cancel_then_reserve_again(self):
        if self.reservation_id is None:
            return
        self.client.post(f"/api/v1/reservations/{self.reservation_id}/cancel/", name="cancel")
        self.reservation_id = None
        self.reserve_or_switch()


LIMITS_MS = {"login": 5000}  # a login checks the password with Argon2 on purpose: a few seconds in a rush is fine
OTHER_LIMIT_MS = 1000  # everything else should feel instant


@events.quitting.add_listener
def verdict(environment, **_kwargs):
    total = environment.stats.total
    failed = total.fail_ratio > 0.01
    lines = []
    for entry in environment.stats.entries.values():
        p95 = entry.get_response_time_percentile(0.95) or 0
        limit = LIMITS_MS.get(entry.name, OTHER_LIMIT_MS)
        too_slow = p95 > limit
        failed |= too_slow
        lines.append(f"  {entry.name:<16} {entry.num_requests:>6} req  p95 {p95:>5.0f} ms (limit {limit})"
                     f"{'  TOO SLOW' if too_slow else ''}")
    print(f"\nVERDICT: {total.num_requests} requests, {total.fail_ratio:.1%} failed, {total.total_rps:.1f} req/s"
          f" -> {'FAILED' if failed else 'OK'}\n" + "\n".join(sorted(lines)))
    if failed:
        environment.process_exit_code = 1
