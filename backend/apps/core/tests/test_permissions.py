"""Role matrix: every protected API refuses (403) every role that should not use it.

Requests carry empty bodies or a date/id that does not exist, so a role that IS allowed gets past the
permission check and stops at validation (400) or lookup (404): nothing is ever changed.
"""
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.tests import factories as f

ROLES = ["employee", "hr", "chef", "scanner", "management", "admin"]
EVERYONE = set(ROLES)
D = "2099-01-04"  # a Monday with no menu
ID = 999999  # no such user / reservation

# (method, url, roles allowed; admin is always allowed)
MATRIX = [
    ("get", "/api/v1/dishes/", {"chef"}),
    ("post", "/api/v1/dishes/", {"chef"}),
    ("post", f"/api/v1/dishes/{ID}/archive/", {"chef"}),
    ("get", "/api/v1/menus/", EVERYONE),
    ("post", "/api/v1/menus/", {"chef"}),
    ("put", f"/api/v1/menus/{D}/items/", {"chef"}),
    ("post", f"/api/v1/menus/{D}/publish/", {"chef"}),
    ("post", f"/api/v1/menus/{D}/close/", {"chef", "management"}),
    ("get", f"/api/v1/menus/{D}/finalization/", {"management"}),
    ("post", f"/api/v1/menus/{D}/finalize/", {"management"}),
    ("post", f"/api/v1/menus/{D}/payment/", {"management"}),
    ("get", "/api/v1/auth/users/", {"hr"}),
    ("post", f"/api/v1/auth/users/{ID}/approve/", {"hr"}),
    ("post", f"/api/v1/auth/users/{ID}/reject/", {"hr"}),
    ("post", f"/api/v1/auth/users/{ID}/reset-password/", {"hr"}),
    ("post", f"/api/v1/auth/users/{ID}/status/suspend/", {"hr"}),
    ("post", "/api/v1/auth/users/roster/import/", {"hr"}),
    ("get", "/api/v1/reservations/", EVERYONE),
    ("post", "/api/v1/scan/", {"scanner"}),
    ("get", "/api/v1/checkin/?q=zz", {"scanner"}),
    ("post", f"/api/v1/checkin/{ID}/manual/", {"scanner"}),
    ("post", f"/api/v1/checkin/{ID}/mark-paid/", {"scanner"}),
    ("get", "/api/v1/reports/daily/", {"chef", "management"}),
    ("get", "/api/v1/reports/attendance/", {"hr", "management"}),
    ("get", "/api/v1/notifications/", EVERYONE),
]


class RoleMatrixTests(TestCase):
    def setUp(self):
        self.clients = {}
        for role in ROLES:
            client = APIClient()
            client.force_authenticate(f.user(role=role))
            self.clients[role] = client

    def test_each_role_reaches_only_its_own_apis(self):
        wrong = []
        for method, url, allowed in MATRIX:
            for role, client in self.clients.items():
                status = getattr(client, method)(url, {}, format="json").status_code
                should_pass = role in allowed or role == "admin"
                if should_pass and status in (401, 403):
                    wrong.append(f"{role} blocked from {method.upper()} {url} ({status})")
                if not should_pass and status != 403:
                    wrong.append(f"{role} NOT blocked from {method.upper()} {url} ({status})")
        self.assertEqual(wrong, [])

    def test_logged_out_reaches_nothing(self):
        anonymous = APIClient()
        open_doors = [
            f"{method.upper()} {url}" for method, url, _ in MATRIX
            if getattr(anonymous, method)(url, {}, format="json").status_code != 401
        ]
        self.assertEqual(open_doors, [])

    def test_inactive_accounts_are_blocked(self):
        client = APIClient()
        client.force_authenticate(f.user(role="chef", status="suspended"))
        self.assertEqual(client.get("/api/v1/dishes/").status_code, 403)


class SuspendedAccountTests(TestCase):
    """A suspension takes effect at once, even on a phone that was already logged in."""

    def test_cannot_log_in_or_reserve_with_an_old_token(self):
        user = f.user(password="Str0ng-pass-123")
        client = APIClient()
        token = client.post("/api/v1/auth/login/", {"work_email": user.work_email, "password": "Str0ng-pass-123"},
                            format="json").json()["access"]
        user.status = "suspended"
        user.save()

        login = client.post("/api/v1/auth/login/", {"work_email": user.work_email, "password": "Str0ng-pass-123"},
                            format="json")
        self.assertEqual((login.status_code, login.json()["code"]), (403, "suspended"))

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(client.post("/api/v1/reservations/", {"date": "2099-01-04"}, format="json").status_code, 401)
        self.assertEqual(client.get("/api/v1/reservations/").status_code, 401)
