from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from . import services
from .models import EmployeeRoster, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("last_name",)
    list_display = ("work_email", "full_name", "employee_number", "role", "status")
    list_filter = ("role", "status")
    search_fields = ("work_email", "last_name", "employee_number")
    fieldsets = (
        (None, {"fields": ("work_email", "password")}),
        ("Identity", {"fields": ("first_name", "last_name", "employee_number", "department", "preferred_language")}),
        ("Access", {"fields": ("role", "status", "is_staff", "is_superuser")}),
        ("History", {"fields": ("email_verified_at", "approved_by", "approved_at", "rejection_reason")}),
    )
    add_fieldsets = (
        (None, {"fields": ("work_email", "first_name", "last_name", "employee_number", "role",
                           "password1", "password2")}),
    )
    readonly_fields = ("email_verified_at", "approved_by", "approved_at")

    def save_model(self, request, obj, form, change):
        # Role, admin rights and status changes go to the audit log (spec §5 Security).
        before = services.access_snapshot(User.objects.get(pk=obj.pk)) if change else None
        super().save_model(request, obj, form, change)
        services.record_admin_access_change(obj, before, by=request.user)

    def has_delete_permission(self, request, obj=None):
        return False  # data is never deleted: deactivate the account instead


@admin.register(EmployeeRoster)
class EmployeeRosterAdmin(admin.ModelAdmin):
    list_display = ("employee_number", "full_name", "department", "imported_at")
    search_fields = ("employee_number", "full_name")
