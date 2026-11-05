import logging

from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import clock, services
from .models import CanteenSettings
from .permissions import IsAdmin
from .serializers import AdminSettingsSerializer, PublicSettingsSerializer

logger = logging.getLogger(__name__)


class HealthView(APIView):
    """For monitoring and the Docker health check: 200 when the API can reach the database, else 503."""

    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:  # any driver error means "database unreachable" here
            logger.exception("Health check: database unreachable")
            return Response({"status": "error", "database": "unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({
            "status": "ok",
            "database": "ok",
            "server_time": clock.local_now().isoformat(),
            "clock_shifted": bool(clock.dev_offset()),  # dev_clock in use (DEBUG only)
        })


class PublicSettingsView(APIView):
    """Settings the frontend needs to display rules (cutoff, service hours...)."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(PublicSettingsSerializer(CanteenSettings.load()).data)


class AdminSettingsView(APIView):
    """FR-46: the admin reads and changes every canteen parameter."""

    permission_classes = [IsAdmin]

    def get(self, request):
        return Response(AdminSettingsSerializer(CanteenSettings.load()).data)

    def patch(self, request):
        data = AdminSettingsSerializer(CanteenSettings.load(), data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        cfg = services.update_settings(by=request.user, changes=data.validated_data)
        return Response(AdminSettingsSerializer(cfg).data)
