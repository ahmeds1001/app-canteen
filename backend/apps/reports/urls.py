from django.urls import path

from .views import AttendanceView, DailySummaryView

urlpatterns = [
    path("daily/", DailySummaryView.as_view(), name="report-daily"),
    path("attendance/", AttendanceView.as_view(), name="report-attendance"),
]
