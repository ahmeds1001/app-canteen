import re

from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts import services
from apps.accounts.models import EmailOTP, User
from apps.core import clock
from apps.core.exceptions import DomainError, NotAllowed
from apps.core.tests import factories as f

PASSWORD = "Str0ng-pass-123"


def _register(client, email="amel@example.com"):
    return client.post("/api/v1/auth/register/", {
        "first_name": "Amel", "last_name": "Ben Ali", "work_email": email,
        "employee_number": "E123", "department": "IT", "password": PASSWORD,
    }, format="json")


def _code_from_last_email() -> str:
    return re.search(r"\b(\d{6})\b", mail.outbox[-1].subject).group(1)


class RegistrationFlowTests(TestCase):
    """FR-01 → FR-05: register, verify the OTP, wait for HR, then log in."""

    def setUp(self):
        self.client = APIClient()

    def test_full_flow(self):
        with clock.frozen(f.at(2026, 11, 2, 9)):
            self.assertEqual(_register(self.client).status_code, 201)
            code = _code_from_last_email()

            # Login refused before verification (sent back to the code screen).
            r = self.client.post("/api/v1/auth/login/", {"work_email": "amel@example.com", "password": PASSWORD})
            self.assertEqual(r.json()["code"], "email_not_verified")

            r = self.client.post("/api/v1/auth/otp/verify/", {"work_email": "amel@example.com", "code": code})
            self.assertEqual(r.json()["status"], User.Status.PENDING_HR)

            r = self.client.post("/api/v1/auth/login/", {"work_email": "amel@example.com", "password": PASSWORD})
            self.assertEqual(r.json()["code"], "pending_hr")

            hr = f.user(role="hr")
            services.approve(User.objects.get(work_email="amel@example.com"), by=hr)
            r = self.client.post("/api/v1/auth/login/", {"work_email": "amel@example.com", "password": PASSWORD})
            self.assertEqual(r.status_code, 200)
            self.assertIn("access", r.json())

    def test_otp_expires_after_10_minutes(self):
        with clock.frozen(f.at(2026, 11, 2, 9)):
            _register(self.client)
            code = _code_from_last_email()
        user = User.objects.get(work_email="amel@example.com")
        with clock.frozen(f.at(2026, 11, 2, 9, 10, 1)):
            with self.assertRaisesMessage(DomainError, "expired"):
                services.verify_otp(user, code)

    def test_otp_invalidated_after_5_wrong_attempts(self):
        with clock.frozen(f.at(2026, 11, 2, 9)):
            _register(self.client)
            code = _code_from_last_email()
            user = User.objects.get(work_email="amel@example.com")
            for _ in range(5):
                with self.assertRaises(DomainError):
                    services.verify_otp(user, "000000" if code != "000000" else "111111")
            with self.assertRaises(DomainError) as ctx:
                services.verify_otp(user, code)
            self.assertEqual(ctx.exception.code, "otp_expired")

    def test_resend_waits_60_seconds_and_cancels_previous_code(self):
        with clock.frozen(f.at(2026, 11, 2, 9)):
            _register(self.client)
            user = User.objects.get(work_email="amel@example.com")
            with self.assertRaises(DomainError):
                services.issue_otp(user)
        with clock.frozen(f.at(2026, 11, 2, 9, 1, 1)):
            services.issue_otp(user)
        self.assertEqual(EmailOTP.objects.filter(user=user, invalidated_at__isnull=True).count(), 1)

    def test_reject_requires_reason(self):
        pending = f.user(status=User.Status.PENDING_HR)
        with self.assertRaises(DomainError):
            services.reject(pending, by=f.user(role="hr"), reason="  ")


class PasswordTests(TestCase):
    def test_temporary_password_expires_after_72h(self):
        hr = f.user(role="hr")
        employee = f.user(work_email="sami@example.com")
        with clock.frozen(f.at(2026, 11, 2, 9)):
            temp = services.staff_reset_password(employee, by=hr)
        with clock.frozen(f.at(2026, 11, 4, 8)):
            self.assertTrue(services.login("sami@example.com", temp).must_change_password)
        with clock.frozen(f.at(2026, 11, 5, 9, 1)):
            with self.assertRaises(NotAllowed):
                services.login("sami@example.com", temp)

    def test_forgot_password_never_reveals_unknown_email(self):
        r = APIClient().post("/api/v1/auth/password/forgot/", {"work_email": "nobody@example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
