"""Reservation, QR check-in and payment rules (spec §3.3, §3.5, §3.6)."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core import audit, clock
from apps.core.exceptions import Conflict, DomainError
from apps.core.models import AuditLog, CanteenSettings
from apps.menus import rules
from apps.menus.models import Menu

from .models import Reservation

A = AuditLog.Action
_signer = signing.Signer(key=settings.CANTEEN_SIGNING_KEY, salt="canteen.qr")
CLOCK_SKEW = timedelta(minutes=2)


def _new_qr() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, _signer.sign(token)


# --- Reserve / cancel (FR-11 to FR-13) ------------------------------------------------
def reserve(user, menu: Menu) -> Reservation:
    """Idempotent: reserving twice returns the existing reservation."""
    cfg = CanteenSettings.load()
    now = clock.now()
    if menu.status != Menu.Status.PUBLISHED or now > rules.reservation_cutoff(menu.date, cfg):
        raise DomainError("reservation_closed", "Reservations for this day are closed.")
    if cfg.booking_horizon_days and (menu.date - clock.today()).days > cfg.booking_horizon_days:
        raise DomainError("beyond_horizon", "This day is not open for booking yet.")

    existing = Reservation.objects.active().filter(user=user, date=menu.date).first()
    if existing:
        return existing

    paid = cfg.payment_enabled and menu.is_paid
    token, payload = _new_qr()
    try:
        with transaction.atomic():
            reservation = Reservation.objects.create(
                user=user, menu=menu, date=menu.date, reserved_at=now,
                qr_token=token, qr_signed_payload=payload,
                payment_status=Reservation.PaymentStatus.UNPAID if paid else Reservation.PaymentStatus.NOT_REQUIRED,
                amount_due=menu.price if paid else None,
            )
    except IntegrityError:  # double tap raced past the check: return the winner
        return Reservation.objects.active().get(user=user, date=menu.date)
    audit.record(A.RESERVE, actor=user, target=reservation)
    return reservation


def cancel(reservation: Reservation, *, by) -> Reservation:
    if reservation.status == Reservation.Status.CANCELLED:
        return reservation  # idempotent
    if reservation.status != Reservation.Status.RESERVED:
        raise Conflict("cannot_cancel", "This meal can no longer be cancelled.")
    if clock.now() > rules.reservation_cutoff(reservation.date):
        raise DomainError("reservation_closed", "The cancellation deadline has passed.")
    updated = Reservation.objects.filter(pk=reservation.pk, status=Reservation.Status.RESERVED).update(
        status=Reservation.Status.CANCELLED, cancelled_at=clock.now()
    )
    reservation.refresh_from_db()
    if updated:
        audit.record(A.CANCEL, actor=by, target=reservation)
    return reservation


# --- Check-in (FR-16 to FR-20) -------------------------------------------------------
def _check_window(reservation: Reservation, at: datetime) -> None:
    cfg = CanteenSettings.load()
    if at > clock.now() + CLOCK_SKEW:
        raise DomainError("scan_in_future", "Scan time is in the future; check the phone clock.")
    if not (rules.service_start(reservation.date, cfg) <= at <= rules.service_end(reservation.date, cfg)):
        raise DomainError("outside_service_window", "Scans are accepted only during service hours.")


def _claim(reservation: Reservation, *, by, at: datetime, method: str) -> Reservation:
    """Atomic claim: exactly one concurrent scan can move Reserved → Served."""
    if not reservation.user.is_active_account:
        raise DomainError("account_not_active", "This account is not active.")
    _check_window(reservation, at)
    claimed = Reservation.objects.filter(pk=reservation.pk, status=Reservation.Status.RESERVED).update(
        status=Reservation.Status.SERVED, served_at=at, scanned_by=by, scan_method=method
    )
    reservation.refresh_from_db()
    if not claimed:
        code = {
            Reservation.Status.SERVED: "already_served",
            Reservation.Status.CANCELLED: "reservation_cancelled",
        }.get(reservation.status, "not_reservable")
        raise Conflict(code, f"Reservation is {reservation.get_status_display().lower()}.")
    action = A.SERVE if method == Reservation.ScanMethod.QR else A.MANUAL_CHECKIN
    audit.record(action, actor=by, target=reservation, scanned_at=at.isoformat())
    return reservation


def scan(payload: str, *, by, scanned_at: datetime | None = None) -> Reservation:
    """Validate a QR code. `scanned_at` is sent by the phone for offline scans (rule "Offline scan sync")."""
    try:
        token = _signer.unsign(payload.strip())
    except signing.BadSignature as exc:
        raise DomainError("invalid_qr", "This QR code is not valid.") from exc
    reservation = Reservation.objects.select_related("user").filter(qr_token=token).first()
    if reservation is None:
        raise DomainError("invalid_qr", "This QR code is not valid.")
    if reservation.date != timezone.localtime(scanned_at or clock.now()).date():
        raise DomainError("wrong_date", f"This code is for {reservation.date:%d/%m/%Y}.")
    return _claim(reservation, by=by, at=scanned_at or clock.now(), method=Reservation.ScanMethod.QR)


def manual_checkin(reservation: Reservation, *, by) -> Reservation:
    return _claim(reservation, by=by, at=clock.now(), method=Reservation.ScanMethod.MANUAL)


# --- Payment (FR-34, FR-35) -----------------------------------------------------------
def mark_paid(reservation: Reservation, *, by) -> Reservation:
    if reservation.payment_status == Reservation.PaymentStatus.PAID:
        return reservation  # idempotent: a double tap records one payment
    if reservation.payment_status != Reservation.PaymentStatus.UNPAID:
        raise DomainError("payment_not_required", "This meal is free.")
    updated = Reservation.objects.filter(
        pk=reservation.pk, payment_status=Reservation.PaymentStatus.UNPAID
    ).update(payment_status=Reservation.PaymentStatus.PAID, paid_at=clock.now(), paid_marked_by=by)
    reservation.refresh_from_db()
    if updated:
        audit.record(A.MARK_PAID, actor=by, target=reservation, amount=reservation.amount_due)
    return reservation
