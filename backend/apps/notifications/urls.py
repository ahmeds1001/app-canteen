from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import NotificationViewSet, PushKeyView, PushSubscribeView, PushUnsubscribeView

router = SimpleRouter()
router.register("", NotificationViewSet, basename="notifications")

urlpatterns = [
    path("push/key/", PushKeyView.as_view(), name="push-key"),
    path("push/subscribe/", PushSubscribeView.as_view(), name="push-subscribe"),
    path("push/unsubscribe/", PushUnsubscribeView.as_view(), name="push-unsubscribe"),
    *router.urls,
]
