"""Accounts domain (spec §3.1, §6.1): User, employee roster, OTP codes, reset tokens."""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models import Q

from apps.core import clock
from apps.core.models import TimeStampedModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, work_email: str, password: str | None = None, **extra):
        if not work_email:
            raise ValueError("work_email is required")
        user = self.model(work_email=self.normalize_email(work_email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, work_email: str, password: str, **extra):
        extra.update(is_staff=True, is_superuser=True, role=User.Role.ADMIN, status=User.Status.ACTIVE)
        extra.setdefault("employee_number", f"ADMIN-{work_email}")
        return self.create_user(work_email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    class Role(models.TextChoices):
        EMPLOYEE = "employee", "Employee"
        HR = "hr", "HR"
        CHEF = "chef", "Chef"
        SCANNER = "scanner", "Scanner / cashier"
        MANAGEMENT = "management", "Management"
        ADMIN = "admin", "Admin"

    class Status(models.TextChoices):
        REGISTERED = "registered", "Registered"
        EMAIL_VERIFIED = "email_verified", "Email verified"  # transient, moves to PENDING_HR
        PENDING_HR = "pending_hr", "Pending HR"
        ACTIVE = "active", "Active"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"
        DEACTIVATED = "deactivated", "Deactivated"

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    work_email = models.EmailField(unique=True)
    # Entered by HR when approving the account, never by the employee (FR-01, FR-04). Empty until then.
    # NULL (not "") so the unique constraint below ignores accounts still waiting for one.
    employee_number = models.CharField(max_length=40, null=True, blank=True)  # noqa: DJ001
    department = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REGISTERED, db_index=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    preferred_language = models.CharField(max_length=5, blank=True)
    approved_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    evening_reminder = models.BooleanField(default=True, help_text="20:00 reminder when tomorrow is not reserved.")
    must_change_password = models.BooleanField(default=False)
    temp_password_expires_at = models.DateTimeField(null=True, blank=True)

    # Django internals (admin site). Business access is governed by `status`.
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "work_email"
    EMAIL_FIELD = "work_email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        ordering = ["last_name", "first_name"]
        constraints = [
            # Unique once filled; many accounts may still be waiting for one (filtered index on SQL Server).
            models.UniqueConstraint(
                fields=["employee_number"], condition=Q(employee_number__isnull=False),
                name="unique_employee_number",
            )
        ]

    @property
    def is_active_account(self) -> bool:
        return self.status == self.Status.ACTIVE

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self) -> str:
        return f"{self.full_name} ({self.employee_number or self.work_email})"


class EmployeeRoster(models.Model):
    """List of employee numbers once imported by HR. No longer used since 2026-10-26 (HR types the
    matricule at approval); kept because data is never deleted."""

    employee_number = models.CharField(max_length=40, primary_key=True)
    full_name = models.CharField(max_length=160)
    department = models.CharField(max_length=100, blank=True)
    imported_at = models.DateTimeField(auto_now=True)
    imported_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="+")

    def __str__(self) -> str:
        return f"{self.employee_number} {self.full_name}"


class EmailOTP(models.Model):
    """6-digit code used ONLY to verify the email at registration (FR-02)."""

    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "verify_email"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps")
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.VERIFY_EMAIL)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=clock.now)  # injectable clock, used by rate limits

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            # At most one live code per user and purpose (expiry is checked in the service).
            models.UniqueConstraint(
                fields=["user", "purpose"],
                condition=Q(consumed_at__isnull=True, invalidated_at__isnull=True),
                name="one_live_otp_per_user_purpose",
            )
        ]

    def __str__(self) -> str:
        return f"OTP {self.purpose} for user {self.user_id}"


class PasswordResetToken(models.Model):
    """Self-service reset link (FR-39): 30 min, single use."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reset_tokens")
    token_hash = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    invalidated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=clock.now)  # injectable clock, used by rate limits

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Reset token for user {self.user_id}"
