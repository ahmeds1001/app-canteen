from django.contrib import admin

from .models import Notification, PushSubscription


class _ReadOnly(admin.ModelAdmin):
    """Notifications are a record: viewable for support, never edited or deleted here."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(_ReadOnly):
    list_display = ("created_at", "kind", "user", "read_at", "pushed_at")
    list_filter = ("kind",)
    search_fields = ("user__work_email", "dedupe_key")


@admin.register(PushSubscription)
class PushSubscriptionAdmin(_ReadOnly):
    list_display = ("user", "created_at", "revoked_at", "user_agent")
    search_fields = ("user__work_email",)
