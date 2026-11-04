from django.urls import path

from .views import AdminSettingsView, HealthView, PublicSettingsView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("settings/public/", PublicSettingsView.as_view(), name="public-settings"),
    path("settings/", AdminSettingsView.as_view(), name="admin-settings"),
]
