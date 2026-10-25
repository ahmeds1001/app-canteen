"""Accounts business logic (the "controller" layer's brain).

Views stay thin: they validate input with serializers, call one function here,
and serialize the result. Every rule from spec §3.1 lives in this module.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import F

from apps.core import audit, clock, notifications
from apps.core.exceptions import DomainError, NotAllowed
from apps.notifications import events as notification_events

from .models import EmailOTP, PasswordResetToken, User

OTP_TTL = timedelta(minutes=10)
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_DELAY = timedelta(seconds=60)
OTP_MAX_PER_HOUR = 5
RESET_LINK_TTL = timedelta(minutes=30)
RESET_MAX_PER_HOUR = 3
TEMP_PASSWORD_TTL = timedelta(hours=72)


def _hash(value: str) -> str:
    return hmac.new(settings.CANTEEN_SIGNING_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


# --- Registration and email OTP (FR-01, FR-02) ---------------------------------------
@transaction.atomic
def register(*, first_name, last_name, work_email, employee_number, department, password) -> User:
    user = User.objects.create_user(
        work_email=work_email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        employee_number=employee_number,
        department=department,
    )
    audit.record(audit.AuditLog.Action.REGISTER, actor=user, target=user)
    issue_otp(user)
    return user


def issue_otp(user: User) -> None:
    """Send a new 6-digit code; cancels any previous live code."""
    if user.status != User.Status.REGISTERED:
        raise DomainError("already_verified", "This email is already verified.")
    now = clock.now()
    recent = EmailOTP.objects.filter(user=user, created_at__gte=now - timedelta(hours=1))
    last = recent.first()
    if last and now - last.created_at < OTP_RESEND_DELAY:
        raise DomainError("otp_resend_too_soon", "Wait 60 seconds before requesting a new code.")
    if recent.count() >= OTP_MAX_PER_HOUR:
        raise DomainError("otp_too_many", "Too many codes requested. Try again in an hour.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    with transaction.atomic():
        EmailOTP.objects.filter(user=user, consumed_at__isnull=True, invalidated_at__isnull=True).update(
            invalidated_at=now
        )
        EmailOTP.objects.create(user=user, code_hash=_hash(code), expires_at=now + OTP_TTL)
    audit.record(audit.AuditLog.Action.OTP_SEND, actor=user, target=user)
    notifications.otp_code(user, code)


def verify_otp(user: User, code: str) -> User:
    now = clock.now()
    otp = EmailOTP.objects.filter(user=user, consumed_at__isnull=True, invalidated_at__isnull=True).first()
    if otp is None or otp.expires_at <= now:
        raise DomainError("otp_expired", "The code has expired. Request a new one.")
    if not hmac.compare_digest(otp.code_hash, _hash(code.strip())):
        EmailOTP.objects.filter(pk=otp.pk).update(attempts=F("attempts") + 1)
        otp.refresh_from_db()
        if otp.attempts >= OTP_MAX_ATTEMPTS:
            EmailOTP.objects.filter(pk=otp.pk).update(invalidated_at=now)
        audit.record(audit.AuditLog.Action.OTP_FAIL, actor=user, target=user, attempts=otp.attempts)
        raise DomainError("otp_invalid", "Incorrect code.")

    # Atomic consume: only one concurrent submission can succeed.
    consumed = EmailOTP.objects.filter(pk=otp.pk, consumed_at__isnull=True).update(consumed_at=now)
    if not consumed:
        raise DomainError("otp_expired", "The code has already been used.")
    User.objects.filter(pk=user.pk).update(
        status=User.Status.PENDING_HR, email_verified_at=now
    )
    user.refresh_from_db()
    audit.record(audit.AuditLog.Action.VERIFY_EMAIL, actor=user, target=user)
    notification_events.account_pending(user)  # HR: an account is waiting (spec §8)
    return user


# --- Login (FR-03) ---------------------------------------------------------------------
LOGIN_BLOCKED = {
    User.Status.REGISTERED: ("email_not_verified", "Enter the code we sent to your email."),
    User.Status.PENDING_HR: ("pending_hr", "Your account is waiting for HR approval."),
    User.Status.REJECTED: ("rejected", "Your registration was rejected."),
    User.Status.SUSPENDED: ("suspended", "Your account is suspended. Contact HR."),
    User.Status.DEACTIVATED: ("deactivated", "Your account is deactivated."),
}


def login(work_email: str, password: str) -> User:
    user = authenticate(username=work_email.lower(), password=password)
    if user is None:
        raise NotAllowed("invalid_credentials", "Incorrect email or password.")
    if user.status in LOGIN_BLOCKED:
        code, message = LOGIN_BLOCKED[user.status]
        raise NotAllowed(code, message)
    # Temporary password from an HR reset (FR-40): valid 72 h, then refused.
    if user.must_change_password and user.temp_password_expires_at and user.temp_password_expires_at <= clock.now():
        raise NotAllowed("temp_password_expired", "Your temporary password has expired. Contact HR.")
    return user


# --- HR approval (FR-04 to FR-06) -----------------------------------------------------
def approve(user: User, *, by: User) -> User:
    if user.status != User.Status.PENDING_HR:
        raise DomainError("not_pending", "Only pending accounts can be approved.")
    user.status, user.approved_by, user.approved_at = User.Status.ACTIVE, by, clock.now()
    user.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    audit.record(audit.AuditLog.Action.APPROVE, actor=by, target=user)
    notifications.account_approved(user)
    return user


def reject(user: User, *, by: User, reason: str) -> User:
    if user.status != User.Status.PENDING_HR:
        raise DomainError("not_pending", "Only pending accounts can be rejected.")
    if not reason.strip():
        raise DomainError("reason_required", "A rejection reason is required.")
    user.status, user.rejection_reason = User.Status.REJECTED, reason.strip()
    user.save(update_fields=["status", "rejection_reason", "updated_at"])
    audit.record(audit.AuditLog.Action.REJECT, actor=by, target=user, reason=reason)
    notifications.account_rejected(user)
    return user


_STATUS_TRANSITIONS = {
    "suspend": ({User.Status.ACTIVE}, User.Status.SUSPENDED, audit.AuditLog.Action.SUSPEND),
    "reactivate": ({User.Status.SUSPENDED}, User.Status.ACTIVE, audit.AuditLog.Action.REACTIVATE),
    "deactivate": (
        {User.Status.ACTIVE, User.Status.SUSPENDED},
        User.Status.DEACTIVATED,
        audit.AuditLog.Action.DEACTIVATE,
    ),
}


def change_status(user: User, transition: str, *, by: User) -> User:
    allowed_from, new_status, action = _STATUS_TRANSITIONS[transition]
    if user.status not in allowed_from:
        raise DomainError("invalid_transition", f"Cannot {transition} an account in status {user.status}.")
    old = user.status
    user.status = new_status
    user.save(update_fields=["status", "updated_at"])
    audit.record(action, actor=by, target=user, old_value=old, new_value=new_status)
    return user


# --- Role assignment in the app (FR-41) ------------------------------------------------
@transaction.atomic
def change_role(user: User, role: str, *, by: User) -> User:
    """Admin only. The admin role also opens/closes the Django admin site (is_staff/is_superuser)."""
    if by.role != User.Role.ADMIN:
        raise NotAllowed("admin_only", "Only an admin can change roles.")
    if user.pk == by.pk:
        raise DomainError("cannot_change_own_role", "You cannot change your own role.")
    if role not in User.Role.values:
        raise DomainError("invalid_role", "Unknown role.")
    user = User.objects.select_for_update().get(pk=user.pk)
    if user.role == role:
        return user  # idempotent
    if user.role == User.Role.ADMIN:
        other_admins = User.objects.filter(role=User.Role.ADMIN, status=User.Status.ACTIVE).exclude(pk=user.pk)
        if not other_admins.exists():
            raise DomainError("last_admin", "The last active admin cannot lose the role.")
    before = access_snapshot(user)
    is_admin = role == User.Role.ADMIN
    user.role, user.is_staff, user.is_superuser = role, is_admin, is_admin
    user.save(update_fields=["role", "is_staff", "is_superuser", "updated_at"])
    audit.record(
        audit.AuditLog.Action.ROLE_CHANGE, actor=by, target=user,
        old_value=before["role"], new_value=role, source="app",
    )
    return user


# --- Changes made by an admin in the Django admin (spec §5: role changes are audited) -----
ACCESS_FIELDS = ("role", "status", "is_staff", "is_superuser")


def _status_action(old: str, new: str) -> str:
    A = audit.AuditLog.Action
    if new == User.Status.ACTIVE:
        return A.REACTIVATE if old == User.Status.SUSPENDED else A.APPROVE
    return {
        User.Status.SUSPENDED: A.SUSPEND,
        User.Status.DEACTIVATED: A.DEACTIVATE,
        User.Status.REJECTED: A.REJECT,
    }.get(new, A.STATUS_CHANGE)


def access_snapshot(user: User) -> dict:
    return {field: getattr(user, field) for field in ACCESS_FIELDS}


def record_admin_access_change(user: User, before: dict | None, *, by: User) -> None:
    """Audit role / admin rights and status after the Django admin saved `user`.
    `before` is `access_snapshot()` taken before the save, None for a new account."""
    after = access_snapshot(user)
    before = before or {"role": "", "status": "", "is_staff": False, "is_superuser": False}

    rights = ("role", "is_staff", "is_superuser")
    if any(before[f] != after[f] for f in rights):
        audit.record(
            audit.AuditLog.Action.ROLE_CHANGE, actor=by, target=user,
            old_value=before["role"], new_value=after["role"], source="django_admin",
            **{f: f"{before[f]} -> {after[f]}" for f in ("is_staff", "is_superuser") if before[f] != after[f]},
        )
    if before["status"] != after["status"]:
        audit.record(
            _status_action(before["status"], after["status"]), actor=by, target=user,
            old_value=before["status"], new_value=after["status"], source="django_admin",
        )


# --- Forgotten password (FR-39 self-service, FR-40 by HR/admin) ------------------------
def request_password_reset(work_email: str) -> None:
    """Always succeeds silently so the API never reveals which emails exist."""
    user = User.objects.filter(work_email=work_email.lower(), status=User.Status.ACTIVE).first()
    if user is None:
        return
    now = clock.now()
    if PasswordResetToken.objects.filter(user=user, created_at__gte=now - timedelta(hours=1)).count() >= (
        RESET_MAX_PER_HOUR
    ):
        return
    token = secrets.token_urlsafe(32)
    with transaction.atomic():
        PasswordResetToken.objects.filter(user=user, used_at__isnull=True, invalidated_at__isnull=True).update(
            invalidated_at=now
        )
        PasswordResetToken.objects.create(user=user, token_hash=_hash(token), expires_at=now + RESET_LINK_TTL)
    audit.record(audit.AuditLog.Action.PASSWORD_RESET_REQUEST, actor=user, target=user)
    notifications.password_reset_link(user, token)


def confirm_password_reset(token: str, new_password: str) -> User:
    now = clock.now()
    reset = PasswordResetToken.objects.select_related("user").filter(token_hash=_hash(token)).first()
    if reset is None or reset.used_at or reset.invalidated_at or reset.expires_at <= now:
        raise DomainError("reset_link_invalid", "This link is invalid or has expired.")
    if not PasswordResetToken.objects.filter(pk=reset.pk, used_at__isnull=True).update(used_at=now):
        raise DomainError("reset_link_invalid", "This link has already been used.")
    user = reset.user
    _set_password(user, new_password)
    audit.record(audit.AuditLog.Action.PASSWORD_RESET, actor=user, target=user)
    notifications.password_changed(user)
    return user


def staff_reset_password(user: User, *, by: User) -> str:
    """Return a temporary password to hand over in person (never emailed)."""
    temp = secrets.token_urlsafe(9)
    user.set_password(temp)
    user.must_change_password = True
    user.temp_password_expires_at = clock.now() + TEMP_PASSWORD_TTL
    user.save(update_fields=["password", "must_change_password", "temp_password_expires_at", "updated_at"])
    audit.record(audit.AuditLog.Action.PASSWORD_RESET_BY_STAFF, actor=by, target=user)
    notifications.password_changed(user)
    return temp


def change_password(user: User, new_password: str) -> User:
    _set_password(user, new_password)
    return user


def _set_password(user: User, new_password: str) -> None:
    from django.contrib.auth.password_validation import validate_password

    validate_password(new_password, user)
    user.set_password(new_password)
    user.must_change_password = False
    user.temp_password_expires_at = None
    user.save(update_fields=["password", "must_change_password", "temp_password_expires_at", "updated_at"])
    # Ending other sessions: refresh tokens are invalidated by the blacklist app (see backlog).
