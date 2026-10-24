from django.urls import path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = SimpleRouter()
router.register("users", views.UserAdminViewSet, basename="users")

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("otp/verify/", views.OTPVerifyView.as_view(), name="otp-verify"),
    path("otp/resend/", views.OTPResendView.as_view(), name="otp-resend"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", views.MeView.as_view(), name="me"),
    path("password/change/", views.PasswordChangeView.as_view(), name="password-change"),
    path("password/forgot/", views.PasswordForgotView.as_view(), name="password-forgot"),
    path("password/reset/", views.PasswordResetConfirmView.as_view(), name="password-reset"),
    *router.urls,
]
