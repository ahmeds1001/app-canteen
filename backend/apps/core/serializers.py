from decimal import Decimal

from rest_framework import serializers

from .models import CanteenSettings
from .services import EDITABLE_FIELDS


class PublicSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CanteenSettings
        fields = [
            "cutoff_days",
            "cutoff_time",
            "service_window_start",
            "service_window_end",
            "finalization_deadline",
            "service_weekdays",
            "publish_deadline_days",
            "publish_deadline_time",
            "payment_enabled",
            "currency",
            "default_language",
            "enabled_languages",
        ]


class AdminSettingsSerializer(serializers.ModelSerializer):
    """Settings screen (FR-46). Ranges only; the order of the day's steps is checked by the service."""

    service_weekdays = serializers.CharField(max_length=20, allow_blank=True)  # empty: refused by the service
    cutoff_days = serializers.IntegerField(min_value=0, max_value=7)
    publish_deadline_days = serializers.IntegerField(min_value=1, max_value=14)
    buffer_value = serializers.IntegerField(min_value=0, max_value=500)
    kitchen_max_plates = serializers.IntegerField(min_value=1, max_value=5000, allow_null=True)
    booking_horizon_days = serializers.IntegerField(min_value=1, max_value=365, allow_null=True)
    no_show_warning_threshold = serializers.IntegerField(min_value=1, max_value=31)
    meal_price_default = serializers.DecimalField(
        max_digits=8, decimal_places=3, min_value=Decimal("0"), max_value=Decimal("1000")
    )

    class Meta:
        model = CanteenSettings
        fields = sorted(EDITABLE_FIELDS) + ["currency", "updated_at"]
        read_only_fields = ["currency", "updated_at"]

    def validate_service_weekdays(self, value: str) -> str:
        days = [d.strip() for d in value.split(",") if d.strip()]
        if any(d not in "0123456" or len(d) != 1 for d in days):
            raise serializers.ValidationError("Days are 0 (Monday) to 6 (Sunday).")
        return ",".join(sorted(set(days)))
