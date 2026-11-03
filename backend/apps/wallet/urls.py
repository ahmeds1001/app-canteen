from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import AccountViewSet, MyBalanceView

router = SimpleRouter()
router.register("accounts", AccountViewSet, basename="wallet-accounts")

urlpatterns = [path("me/", MyBalanceView.as_view(), name="wallet-me"), *router.urls]
