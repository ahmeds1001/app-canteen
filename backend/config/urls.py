from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from apps.core.views import spa_index

api_v1 = [
    path("", include("apps.core.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.menus.urls")),
    path("", include("apps.reservations.urls")),
    path("reports/", include("apps.reports.urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("wallet/", include("apps.wallet.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
]

# Dish photos in development; `static()` adds nothing when DEBUG is off.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Windows server without nginx (SERVE_FRONTEND): Django serves the photos and the site. Files of the built site
# (/, /assets/…, /sw.js) come from WhiteNoise; any other path is a screen of the app: answer with index.html.
if getattr(settings, "SERVE_FRONTEND", False):
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
        re_path(r"^(?!api/|admin/|static/|media/).*$", spa_index),
    ]
