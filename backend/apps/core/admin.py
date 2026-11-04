from django.contrib import admin

from .models import AuditLog, CanteenSettings


@admin.register(CanteenSettings)
class CanteenSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # read-only here: changes go through the app's Settings screen (checked, audited — FR-46)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "target_type", "target_id")
    list_filter = ("action",)
    search_fields = ("target_id", "actor__work_email")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
