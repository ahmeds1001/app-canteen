from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import clock
from .models import CanteenSettings


class PublicSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CanteenSettings
        fields = [
            "cutoff_time",
            "service_window_start",
            "service_window_end",
            "finalization_deadline",
            "service_weekdays",
            "publish_deadline_days",
            "payment_enabled",
            "currency",
            "default_language",
            "enabled_languages",
        ]


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            "status": "ok",
            "server_time": clock.local_now().isoformat(),
            "clock_shifted": bool(clock.dev_offset()),  # dev_clock in use (DEBUG only)
        })


class PublicSettingsView(APIView):
    """Settings the frontend needs to display rules (cutoff, service hours...)."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(PublicSettingsSerializer(CanteenSettings.load()).data)
