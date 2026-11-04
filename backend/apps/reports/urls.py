from django.urls import path

from .views import AttendanceView, CashView, DailySummaryView, EmployeeMonthView, MonthlyAttendanceView

urlpatterns = [
    path("cash/", CashView.as_view(), name="report-cash"),
    path("daily/", DailySummaryView.as_view(), name="report-daily"),
    path("attendance/", AttendanceView.as_view(), name="report-attendance"),
    path("attendance/monthly/", MonthlyAttendanceView.as_view(), name="report-attendance-monthly"),
    path("attendance/monthly/<int:user_id>/", EmployeeMonthView.as_view(), name="report-attendance-employee"),
]
