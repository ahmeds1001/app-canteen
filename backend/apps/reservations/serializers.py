from rest_framework import serializers

from .models import Reservation


class ReservationSerializer(serializers.ModelSerializer):
    """What an employee sees in "My reservations"."""

    qr_payload = serializers.SerializerMethodField()
    menu_items = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            "id", "date", "status", "reserved_at", "served_at",
            "payment_status", "amount_due", "paid_at", "qr_payload", "menu_items",
        ]

    def get_qr_payload(self, obj: Reservation) -> str | None:
        # The QR is only shown while it can still be used.
        return obj.qr_signed_payload if obj.status == Reservation.Status.RESERVED else None

    def get_menu_items(self, obj: Reservation) -> list[str]:
        return [item.name for item in obj.menu.items.all()]


class ReserveSerializer(serializers.Serializer):
    date = serializers.DateField()


class ScanSerializer(serializers.Serializer):
    payload = serializers.CharField(max_length=200)
    scanned_at = serializers.DateTimeField(required=False, allow_null=True)


class ScanResultSerializer(serializers.ModelSerializer):
    """What the canteen phone shows after a scan: who it is and whether to collect money."""

    full_name = serializers.CharField(source="user.full_name")
    employee_number = serializers.CharField(source="user.employee_number")

    class Meta:
        model = Reservation
        fields = ["id", "date", "status", "full_name", "employee_number", "payment_status", "amount_due",
                  "served_at", "scan_method"]
