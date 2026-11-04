from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import clock, services
from .models import CanteenSettings
from .permissions import IsAdmin
from .serializers import AdminSettingsSerializer, PublicSettingsSerializer


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
