from django.conf import settings
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from apps.core.permissions import IsEmployee

from . import push, services
from .serializers import (
    NotificationSerializer,
    PreferencesSerializer,
    PushSubscriptionSerializer,
    UnsubscribeSerializer,
)


class NotificationViewSet(ViewSet):
    """The current user's notifications (bell + list)."""

    permission_classes = [IsEmployee]

    def list(self, request):
        context = {"language": getattr(request, "LANGUAGE_CODE", "fr")}
        items = NotificationSerializer(services.for_user(request.user), many=True, context=context).data
        return Response({
            "unread": services.unread_count(request.user),
            "evening_reminder": request.user.evening_reminder,
            "results": items,
        })

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        services.mark_read(request.user, int(pk))
        return Response({"unread": services.unread_count(request.user)})

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        services.mark_all_read(request.user)
        return Response({"unread": 0})

    @action(detail=False, methods=["patch"])
    def preferences(self, request):
        data = PreferencesSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.set_preferences(request.user, **data.validated_data)
        return Response({"evening_reminder": user.evening_reminder})


class PushKeyView(APIView):
    permission_classes = [IsEmployee]

    def get(self, request):
        return Response({"enabled": push.enabled(), "public_key": settings.VAPID_PUBLIC_KEY})


class PushSubscribeView(APIView):
    permission_classes = [IsEmployee]

    def post(self, request):
        data = PushSubscriptionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        keys = data.validated_data["keys"]
        services.subscribe(
            request.user, endpoint=data.validated_data["endpoint"], p256dh=keys["p256dh"], auth=keys["auth"],
            user_agent=request.headers.get("User-Agent", ""),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PushUnsubscribeView(APIView):
    permission_classes = [IsEmployee]

    def post(self, request):
        data = UnsubscribeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.unsubscribe(request.user, endpoint=data.validated_data["endpoint"])
        return Response(status=status.HTTP_204_NO_CONTENT)
