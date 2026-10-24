from django.contrib import admin

from .models import Reservation


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("date", "user", "status", "payment_status", "served_at")
    list_filter = ("status", "payment_status", "date")
    search_fields = ("user__last_name", "user__employee_number")
    readonly_fields = ("qr_token", "qr_signed_payload")
