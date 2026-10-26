"""Accounts API controllers: validate input, call a service, return a representation."""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.permissions import IsHR

from . import services
from .models import User
from .serializers import (
    EmailSerializer,
    EmployeeNumberSerializer,
    LoginSerializer,
    OTPVerifySerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    RegisterSerializer,
    RejectSerializer,
    RoleSerializer,
    UserSerializer,
)


def _tokens(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "user": UserSerializer(user).data}


class _Public(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]


class RegisterView(_Public):
    throttle_scope = "register"

    def post(self, request):
        data = RegisterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.register(**data.validated_data)
        return Response({"status": user.status, "work_email": user.work_email}, status=status.HTTP_201_CREATED)


class OTPVerifyView(_Public):
    throttle_scope = "otp_verify"

    def post(self, request):
        data = OTPVerifySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = get_object_or_404(User, work_email=data.validated_data["work_email"].lower())
        user = services.verify_otp(user, data.validated_data["code"])
        return Response({"status": user.status})


class OTPResendView(_Public):
    throttle_scope = "register"

    def post(self, request):
        data = EmailSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = User.objects.filter(work_email=data.validated_data["work_email"].lower()).first()
        if user is not None and user.status == User.Status.REGISTERED:
            services.issue_otp(user)
        return Response({"detail": "If this account is waiting for verification, a new code was sent."})


class LoginView(_Public):
    throttle_scope = "login"

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = services.login(data.validated_data["work_email"], data.validated_data["password"])
        return Response(_tokens(user))


class PasswordForgotView(_Public):
    throttle_scope = "password_reset"

    def post(self, request):
        data = EmailSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.request_password_reset(data.validated_data["work_email"])
        return Response({"detail": "If this email exists, a link has been sent."})


class PasswordResetConfirmView(_Public):
    throttle_scope = "password_reset"

    def post(self, request):
        data = PasswordResetConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.confirm_password_reset(data.validated_data["token"], data.validated_data["new_password"])
        return Response({"detail": "Password changed. You can log in."})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = PasswordChangeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.change_password(request.user, data.validated_data["new_password"])
        return Response(_tokens(request.user))


class UserAdminViewSet(GenericViewSet):
    """HR dashboard: list accounts and act on them (FR-04, FR-06, FR-40)."""

    permission_classes = [IsHR]
    serializer_class = UserSerializer

    def get_queryset(self):
        qs = User.objects.all()
        if status_filter := self.request.query_params.get("status"):
            qs = qs.filter(status=status_filter)
        if search := self.request.query_params.get("q"):
            qs = qs.filter(
                Q(last_name__icontains=search) | Q(first_name__icontains=search)
                | Q(employee_number__icontains=search) | Q(work_email__icontains=search)
            )
        return qs

    def list(self, request):
        return Response(self.get_serializer(self.get_queryset(), many=True).data)

    def _act(self, request, pk, fn, **kwargs):
        user = fn(get_object_or_404(User, pk=pk), by=request.user, **kwargs)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        data = EmployeeNumberSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._act(request, pk, services.approve, employee_number=data.validated_data["employee_number"])

    @action(detail=True, methods=["post"], url_path="employee-number")
    def employee_number(self, request, pk=None):
        data = EmployeeNumberSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._act(request, pk, services.set_employee_number,
                         employee_number=data.validated_data["employee_number"])

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        data = RejectSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._act(request, pk, services.reject, reason=data.validated_data["reason"])

    @action(detail=True, methods=["post"], url_path=r"status/(?P<transition>suspend|reactivate|deactivate)")
    def change_status(self, request, pk=None, transition=None):
        user = services.change_status(get_object_or_404(User, pk=pk), transition, by=request.user)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"])
    def role(self, request, pk=None):
        """FR-41: admin only (checked in the service)."""
        data = RoleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return self._act(request, pk, services.change_role, role=data.validated_data["role"])

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        temp = services.staff_reset_password(get_object_or_404(User, pk=pk), by=request.user)
        return Response({"temporary_password": temp, "expires_in_hours": 72})
