import re

from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts import services
from apps.accounts.models import EmailOTP, User
from apps.core import clock
from apps.core.exceptions import DomainError, NotAllowed
from apps.core.models import AuditLog
from apps.core.tests import factories as f

PASSWORD = "Str0ng-pass-123"


def _register(client, email="amel@example.com"):
    return client.post("/api/v1/auth/register/", {
        "first_name": "Amel", "last_name": "Ben Ali", "work_email": email,
        "department": "IT", "password": PASSWORD,
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
            services.approve(User.objects.get(work_email="amel@example.com"), by=hr, employee_number="E123")
            r = self.client.post("/api/v1/auth/login/", {"work_email": "amel@example.com", "password": PASSWORD})
            self.assertEqual(r.status_code, 200)
            self.assertIn("access", r.json())
            self.assertEqual(r.json()["user"]["employee_number"], "E123")

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

    def test_employee_cannot_choose_their_matricule(self):
        r = self.client.post("/api/v1/auth/register/", {
            "first_name": "Amel", "last_name": "Ben Ali", "work_email": "amel@example.com",
            "employee_number": "E999", "password": PASSWORD,
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(User.objects.get(work_email="amel@example.com").employee_number)

    def test_weak_password_is_refused_with_a_message(self):
        r = self.client.post("/api/v1/auth/register/", {
            "first_name": "Amel", "last_name": "Ben Ali", "work_email": "amel@example.com", "password": "12345678",
        }, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertTrue(r.json()["non_field_errors"])


class ApprovalTests(TestCase):
    """FR-04: HR enters the matricule when approving; it is required and unique."""

    def setUp(self):
        self.hr = f.user(role="hr")
        self.client = APIClient()
        self.client.force_authenticate(self.hr)

    def _pending(self, **extra):
        return f.user(status=User.Status.PENDING_HR, employee_number=None, **extra)

    def _approve(self, user, number):
        return self.client.post(f"/api/v1/auth/users/{user.pk}/approve/", {"employee_number": number}, format="json")

    def test_approve_sets_matricule_and_is_audited(self):
        pending = self._pending()
        r = self._approve(pending, "  M-0042 ")
        self.assertEqual(r.status_code, 200)
        pending.refresh_from_db()
        self.assertEqual((pending.status, pending.employee_number, pending.approved_by), ("active", "M-0042", self.hr))
        log = AuditLog.objects.get(action="approve", target_id=str(pending.pk))
        self.assertEqual(log.meta["employee_number"], "M-0042")
        self.assertEqual(len(mail.outbox), 1)

    def test_matricule_is_required(self):
        pending = self._pending()
        self.assertEqual(self._approve(pending, "   ").status_code, 400)
        self.assertEqual(self.client.post(f"/api/v1/auth/users/{pending.pk}/approve/", {}).status_code, 400)
        with self.assertRaises(DomainError) as ctx:
            services.approve(pending, by=self.hr, employee_number=" ")
        self.assertEqual(ctx.exception.code, "employee_number_required")
        pending.refresh_from_db()
        self.assertEqual(pending.status, User.Status.PENDING_HR)

    def test_matricule_must_be_unique(self):
        f.user(employee_number="M-0042")
        pending = self._pending()
        r = self._approve(pending, "M-0042")
        self.assertEqual((r.status_code, r.json()["code"]), (409, "employee_number_taken"))
        pending.refresh_from_db()
        self.assertEqual(pending.status, User.Status.PENDING_HR)

    def test_double_tap_approves_once(self):
        pending = self._pending()
        self._approve(pending, "M-0042")
        self.assertEqual(self._approve(pending, "M-0042").status_code, 200)
        self.assertEqual(AuditLog.objects.filter(action="approve", target_id=str(pending.pk)).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_many_accounts_can_wait_without_a_matricule(self):
        self._pending()
        self._pending()
        self.assertEqual(User.objects.filter(employee_number__isnull=True).count(), 2)

    def test_hr_can_correct_matricule_later(self):
        employee = f.user(employee_number="M-0001")
        f.user(employee_number="M-0002")
        url = f"/api/v1/auth/users/{employee.pk}/employee-number/"
        self.assertEqual(self.client.post(url, {"employee_number": "M-0002"}).json()["code"], "employee_number_taken")
        self.assertEqual(self.client.post(url, {"employee_number": "M-0003"}).json()["employee_number"], "M-0003")
        log = AuditLog.objects.get(action="employee_number_change")
        self.assertEqual((log.old_value, log.new_value, log.actor), ("M-0001", "M-0003", self.hr))


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
