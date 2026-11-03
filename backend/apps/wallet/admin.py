from django.contrib import admin

from .models import BalanceTransaction


@admin.register(BalanceTransaction)
class BalanceTransactionAdmin(admin.ModelAdmin):
    """Read-only: money moves only through the app, so every movement has its audit entry."""

    list_display = ("created_at", "user", "kind", "amount", "balance_after", "by", "note")
    list_filter = ("kind",)
    search_fields = ("user__last_name", "user__employee_number", "note")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
