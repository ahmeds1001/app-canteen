from rest_framework import serializers

from . import messages
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ["id", "kind", "title", "body", "link", "created_at", "read_at"]

    def _text(self, obj: Notification) -> tuple[str, str]:
        return messages.render(obj.kind, obj.params, self.context.get("language", "fr"))

    def get_title(self, obj: Notification) -> str:
        return self._text(obj)[0]

    def get_body(self, obj: Notification) -> str:
        return self._text(obj)[1]


class PreferencesSerializer(serializers.Serializer):
    evening_reminder = serializers.BooleanField()


class PushSubscriptionSerializer(serializers.Serializer):
    """Shape of `PushSubscription.toJSON()` in the browser."""

    endpoint = serializers.URLField(max_length=500)
    keys = serializers.DictField(child=serializers.CharField(max_length=200))

    def validate_keys(self, value: dict) -> dict:
        if not value.get("p256dh") or not value.get("auth"):
            raise serializers.ValidationError("p256dh and auth are required.")
        return value


class UnsubscribeSerializer(serializers.Serializer):
    endpoint = serializers.URLField(max_length=500)
