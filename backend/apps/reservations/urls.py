from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import CheckinViewSet, DayListView, MyReservationViewSet, ScanView

router = SimpleRouter()
router.register("reservations", MyReservationViewSet, basename="reservations")
router.register("checkin", CheckinViewSet, basename="checkin")

urlpatterns = [
    path("scan/", ScanView.as_view(), name="scan"),
    path("reservations/day/", DayListView.as_view(), name="reservations-day"),
    *router.urls,
]
