"""Prepaid balance rules (decided 2026-11-03).

- Employees give cash to the canteen; the cashier or management records it as a top-up (FR-47).
- A meal is paid from the balance when it is reserved; without enough money the reservation is refused.
- Cancelling before the cutoff (midnight the day before) pays the meal back; a no-show keeps it paid.
- The balance never goes below zero: every debit is a conditional update `balance >= amount`.
- Mistakes are fixed by management with a correction and a reason; nothing is ever deleted.
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import F

from apps.accounts.models import User
from apps.core import audit, clock
from apps.core.exceptions import DomainError, NotAllowed
from apps.core.models import CanteenSettings
from apps.notifications.services import Kind, notify

from .models import BalanceTransaction

MAX_TOPUP = Decimal("1000.000")  # a typing mistake (an extra zero) must not credit thousands


def _apply(user: User, amount: Decimal, kind: str, *, by=None, reservation=None, note: str = "") -> BalanceTransaction:
    """Move `amount` (signed) on the balance and record it, in one transaction. Refuses to go below zero."""
    with transaction.atomic():
        rows = User.objects.filter(pk=user.pk)
        if amount < 0:
            rows = rows.filter(balance__gte=-amount)
        if not rows.update(balance=F("balance") + amount):
            raise DomainError("insufficient_balance", "Not enough money on the balance.")
        balance = User.objects.values_list("balance", flat=True).get(pk=user.pk)
        entry = BalanceTransaction.objects.create(
            user=user, kind=kind, amount=amount, balance_after=balance, reservation=reservation,
            by=by if getattr(by, "pk", None) else None, note=note, created_at=clock.now(),
        )
    user.balance = balance
    return entry


def _amount(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.001"))


def top_up(user: User, amount, *, by) -> BalanceTransaction:
    """Cash received at the canteen. Cashier or management only (FR-47; the API checks it too)."""
    if by.role not in (User.Role.CASHIER, User.Role.MANAGEMENT, User.Role.ADMIN):
        raise NotAllowed("cashier_only", "Only the cashier or management can record cash.")
    amount = _amount(amount)
    if amount <= 0:
        raise DomainError("amount_positive", "The amount must be greater than zero.")
    # FR-48: no small daily top-ups at the counter. Management may still record less for a special case.
    minimum = CanteenSettings.load().min_topup_amount
    if by.role == User.Role.CASHIER and amount < minimum:
        raise DomainError("topup_below_minimum", f"The minimum top-up is {minimum} TND.")
    if amount > MAX_TOPUP:
        raise DomainError("amount_too_large", f"A top-up cannot exceed {MAX_TOPUP} TND.")
    if not user.is_active_account:
        raise DomainError("account_not_active", "This account is not active.")
    entry = _apply(user, amount, BalanceTransaction.Kind.TOPUP, by=by)
    audit.record(audit.AuditLog.Action.BALANCE_TOPUP, actor=by, target=user, amount=amount,
                 balance=entry.balance_after)
    notify([user], Kind.BALANCE_TOPUP, params={"amount": str(amount), "balance": str(entry.balance_after)},
           link="/balance", dedupe_key=f"topup:{entry.pk}")
    return entry


def correct(user: User, amount, *, by, reason: str) -> BalanceTransaction:
    """Fix a mistake (wrong top-up amount, wrong person…). Management or admin only, with a reason."""
    if by.role not in (User.Role.MANAGEMENT, User.Role.ADMIN):
        raise NotAllowed("management_only", "Only management can correct a balance.")
    amount = _amount(amount)
    if amount == 0:
        raise DomainError("amount_zero", "The correction cannot be zero.")
    if not reason.strip():
        raise DomainError("reason_required", "A reason is required.")
    entry = _apply(user, amount, BalanceTransaction.Kind.CORRECTION, by=by, note=reason.strip()[:200])
    audit.record(audit.AuditLog.Action.BALANCE_CORRECTION, actor=by, target=user, amount=amount,
                 balance=entry.balance_after, reason=reason.strip())
    notify([user], Kind.BALANCE_CORRECTED,
           params={"amount": f"{amount:+}", "balance": str(entry.balance_after), "reason": reason.strip()},
           link="/balance", dedupe_key=f"correction:{entry.pk}")
    return entry


def pay_meal(reservation, price: Decimal) -> BalanceTransaction:
    """Called inside the reservation's transaction: a refusal rolls the reservation back too."""
    return _apply(reservation.user, -price, BalanceTransaction.Kind.MEAL, by=reservation.user,
                  reservation=reservation)


def refund_meal(reservation, *, by) -> BalanceTransaction | None:
    """Pay back a cancelled meal that was paid from the balance. Idempotent: a meal is refunded once."""
    from apps.reservations.models import Reservation  # lazy: reservations calls this module

    P = Reservation.PaymentStatus
    if not reservation.amount_due:
        return None
    with transaction.atomic():
        claimed = Reservation.objects.filter(pk=reservation.pk, payment_status=P.PAID).update(
            payment_status=P.REFUNDED
        )
        if not claimed:
            return None
        entry = _apply(reservation.user, reservation.amount_due, BalanceTransaction.Kind.REFUND, by=by,
                       reservation=reservation)
    reservation.payment_status = P.REFUNDED
    return entry
