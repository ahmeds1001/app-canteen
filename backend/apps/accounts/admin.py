from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

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


@admin.register(EmployeeRoster)
class EmployeeRosterAdmin(admin.ModelAdmin):
    list_display = ("employee_number", "full_name", "department", "imported_at")
    search_fields = ("employee_number", "full_name")
