from django.contrib import admin
from django.urls import include, path

api_v1 = [
    path("", include("apps.core.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.menus.urls")),
    path("", include("apps.reservations.urls")),
    path("reports/", include("apps.reports.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]
