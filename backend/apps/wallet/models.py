"""Prepaid balance (decided 2026-11-03): every movement of an employee's balance, append-only.

The current balance is kept on `User.balance` for the "enough money?" check; this table is its history
and its proof: every row says how much moved, why, who did it, and the balance right after.
"""
from django.conf import settings
from django.db import models

from apps.core import clock


class BalanceTransaction(models.Model):
    class Kind(models.TextChoices):
        TOPUP = "topup", "Top-up"  # cash given to the canteen, recorded by the scanner or management
        MEAL = "meal", "Meal"  # paid when the meal is reserved (negative)
        REFUND = "refund", "Refund"  # reservation cancelled before the cutoff, or day closed
        CORRECTION = "correction", "Correction"  # management fixes a mistake, with a reason

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="balance_transactions")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=3, help_text="TND; negative when money leaves.")
    balance_after = models.DecimalField(max_digits=10, decimal_places=3)
    reservation = models.ForeignKey(
        "reservations.Reservation", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )  # who recorded it (the employee for meals; NULL = system)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=clock.now)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "created_at"])]

    def __str__(self) -> str:
        return f"{self.kind} {self.amount} for user {self.user_id}"
