from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts import services
from apps.accounts.models import PasswordResetToken, User
from apps.core.tests import factories as f

PASSWORD = "Str0ng-pass-123"
NEW_PASSWORD = "An0ther-pass-456"


def _login(email, password=PASSWORD) -> dict:
    r = APIClient().post("/api/v1/auth/login/", {"work_email": email, "password": password})
    assert r.status_code == 200, r.json()
    return r.json()


def _refresh(refresh: str):
    return APIClient().post("/api/v1/auth/token/refresh/", {"refresh": refresh})


class RefreshTokenTests(TestCase):
    """Refresh-token blacklist: no new access token for blocked accounts or after a password change (FR-39)."""

    def setUp(self):
        self.user = f.user(work_email="sami@example.com")

    def test_refresh_token_works_once(self):
        tokens = _login("sami@example.com")
        r = _refresh(tokens["refresh"])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(_refresh(tokens["refresh"]).status_code, 401)  # already rotated
        self.assertEqual(_refresh(r.json()["refresh"]).status_code, 200)

    def test_suspended_or_deactivated_account_cannot_refresh(self):
        hr = f.user(role="hr")
        tokens = _login("sami@example.com")
        services.change_status(self.user, "suspend", by=hr)
        self.assertEqual(_refresh(tokens["refresh"]).status_code, 401)

        services.change_status(self.user, "reactivate", by=hr)
        tokens = _login("sami@example.com")
        services.change_status(self.user, "deactivate", by=hr)
        self.assertEqual(_refresh(tokens["refresh"]).status_code, 401)

    def test_password_change_logs_out_other_devices(self):
        phone = _login("sami@example.com")
        laptop = _login("sami@example.com")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {laptop['access']}")
        r = client.post("/api/v1/auth/password/change/", {"new_password": NEW_PASSWORD})
        self.assertEqual(r.status_code, 200)

        self.assertEqual(_refresh(phone["refresh"]).status_code, 401)
        self.assertEqual(_refresh(laptop["refresh"]).status_code, 401)
        self.assertEqual(_refresh(r.json()["refresh"]).status_code, 200)  # this device stays logged in

    def test_password_reset_by_link_or_by_hr_logs_out_every_device(self):
        tokens = _login("sami@example.com")
        PasswordResetToken.objects.create(
            user=self.user, token_hash=services._hash("link-token"), expires_at=f.at(2099, 1, 1)
        )
        services.confirm_password_reset("link-token", NEW_PASSWORD)
        self.assertEqual(_refresh(tokens["refresh"]).status_code, 401)

        tokens = _login("sami@example.com", NEW_PASSWORD)
        services.staff_reset_password(self.user, by=f.user(role="hr"))
        self.assertEqual(_refresh(tokens["refresh"]).status_code, 401)

    def test_end_sessions_is_idempotent(self):
        _login("sami@example.com")
        _login("sami@example.com")
        self.assertEqual(services.end_sessions(self.user), 2)
        self.assertEqual(services.end_sessions(self.user), 0)
        self.assertEqual(User.objects.filter(pk=self.user.pk).count(), 1)
