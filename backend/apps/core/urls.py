from django.urls import path

from .views import HealthView, PublicSettingsView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("settings/public/", PublicSettingsView.as_view(), name="public-settings"),
]
