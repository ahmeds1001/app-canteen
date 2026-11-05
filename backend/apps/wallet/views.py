"""Prepaid balance API: the employee's own balance, and the cashier screen (cashier and management, FR-47)."""
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from apps.accounts.models import User
from apps.core.permissions import IsCashierOrManagement, IsEmployee, IsManagement

from . import selectors, services
from .serializers import AccountSerializer, CorrectionSerializer, TopUpSerializer, TransactionSerializer


class MyBalanceView(APIView):
    permission_classes = [IsEmployee]

    def get(self, request):
        return Response({
            "balance": str(request.user.balance),
            "transactions": TransactionSerializer(selectors.history(request.user), many=True).data,
        })


class AccountViewSet(GenericViewSet):
    """Cashier: find an employee, record the cash they gave (top-up), see their history.
    Corrections are for management only."""

    serializer_class = AccountSerializer

    def get_permissions(self):
        return [IsManagement()] if self.action == "correct" else [IsCashierOrManagement()]

    def _account(self, pk) -> User:
        return get_object_or_404(User, pk=pk)

    def list(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Response([])
        return Response(self.get_serializer(selectors.accounts(q)[:30], many=True).data)

    @action(detail=True, methods=["get"])
    def transactions(self, request, pk=None):
        account = self._account(pk)
        return Response({
            "account": self.get_serializer(account).data,
            "transactions": TransactionSerializer(selectors.history(account), many=True).data,
        })

    @action(detail=True, methods=["post"])
    def topup(self, request, pk=None):
        data = TopUpSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        account = self._account(pk)
        entry = services.top_up(account, data.validated_data["amount"], by=request.user)
        return self._moved(account, entry)

    @action(detail=True, methods=["post"])
    def correct(self, request, pk=None):
        data = CorrectionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        account = self._account(pk)
        entry = services.correct(account, data.validated_data["amount"], by=request.user,
                                 reason=data.validated_data["reason"])
        return self._moved(account, entry)

    def _moved(self, account: User, entry) -> Response:
        return Response({
            "account": self.get_serializer(account).data, "transaction": TransactionSerializer(entry).data,
        })
