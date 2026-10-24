"""Reservation: the centre of the model (QR token, outcome, payment) — spec §6.1."""
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel
from apps.menus.models import Menu


class ReservationQuerySet(models.QuerySet):
    def active(self):
        """Everything except cancelled reservations (they count as plates)."""
        return self.exclude(status=Reservation.Status.CANCELLED)


class Reservation(TimeStampedModel):
    class Status(models.TextChoices):
        RESERVED = "reserved", "Reserved"
        CANCELLED = "cancelled", "Cancelled"
        SERVED = "served", "Served"
        NO_SHOW = "no_show", "No-show"

    class ScanMethod(models.TextChoices):
        QR = "qr", "QR"
        MANUAL = "manual", "Manual"

    class PaymentStatus(models.TextChoices):
        NOT_REQUIRED = "not_required", "Not required"
        UNPAID = "unpaid", "Unpaid"
        PAID = "paid", "Paid"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reservations")
    menu = models.ForeignKey(Menu, on_delete=models.PROTECT, related_name="reservations")
    date = models.DateField(db_index=True, help_text="Copy of menu.date, used by the unique rule.")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RESERVED, db_index=True)

    qr_token = models.CharField(max_length=64, unique=True)
    qr_signed_payload = models.CharField(max_length=200)

    reserved_at = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)
    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    scan_method = models.CharField(max_length=6, choices=ScanMethod.choices, blank=True)
    no_show_marked_at = models.DateTimeField(null=True, blank=True)

    payment_status = models.CharField(
        max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.NOT_REQUIRED, db_index=True
    )
    amount_due = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    objects = ReservationQuerySet.as_manager()

    class Meta:
        ordering = ["-date"]
        constraints = [
            # One active plate per employee per day (filtered unique index on SQL Server).
            models.UniqueConstraint(
                fields=["user", "date"],
                condition=~Q(status="cancelled"),
                name="one_active_reservation_per_user_per_day",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user} – {self.date} ({self.status})"
