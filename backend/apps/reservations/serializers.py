from rest_framework import serializers

from .models import Reservation


def chosen_dishes(obj: Reservation) -> list[str]:
    """The dishes of the menu this person chose (menu 1 or 2 of the day)."""
    return [item.name for item in obj.menu.items.all() if item.choice == obj.choice]


class ReservationSerializer(serializers.ModelSerializer):
    """What an employee sees in "My reservations"."""

    qr_payload = serializers.SerializerMethodField()
    menu_items = serializers.SerializerMethodField()
    menu_choices = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = [
            "id", "date", "choice", "menu_choices", "status", "reserved_at", "served_at",
            "payment_status", "amount_due", "paid_at", "qr_payload", "menu_items",
        ]

    def get_qr_payload(self, obj: Reservation) -> str | None:
        # The QR is only shown while it can still be used.
        return obj.qr_signed_payload if obj.status == Reservation.Status.RESERVED else None

    def get_menu_items(self, obj: Reservation) -> list[str]:
        return chosen_dishes(obj)

    def get_menu_choices(self, obj: Reservation) -> int:
        """How many menus the day offers: the menu number is only worth showing when there are two."""
        return len(obj.menu.choices())


class ReserveSerializer(serializers.Serializer):
    date = serializers.DateField()
    choice = serializers.ChoiceField(choices=[1, 2], default=1)


class ScanSerializer(serializers.Serializer):
    payload = serializers.CharField(max_length=200)
    scanned_at = serializers.DateTimeField(required=False, allow_null=True)


class ScanResultSerializer(serializers.ModelSerializer):
    """What the canteen phone shows after a scan: who it is, which menu to serve, whether it is paid."""

    full_name = serializers.CharField(source="user.full_name")
    employee_number = serializers.CharField(source="user.employee_number")
    menu_items = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = ["id", "date", "status", "full_name", "employee_number", "choice", "menu_items",
                  "payment_status", "amount_due", "served_at", "scan_method"]

    def get_menu_items(self, obj: Reservation) -> list[str]:
        return chosen_dishes(obj)


class DayReservationSerializer(ScanResultSerializer):
    """One row of a day's reservation list (scanner and management)."""

    department = serializers.CharField(source="user.department")

    class Meta(ScanResultSerializer.Meta):
        fields = ScanResultSerializer.Meta.fields + ["department", "reserved_at", "cancelled_at"]
