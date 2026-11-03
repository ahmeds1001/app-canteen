from rest_framework import serializers

from apps.accounts.models import User

from .models import BalanceTransaction


class TransactionSerializer(serializers.ModelSerializer):
    by_name = serializers.SerializerMethodField()
    meal_date = serializers.DateField(source="reservation.date", default=None, read_only=True)

    class Meta:
        model = BalanceTransaction
        fields = ["id", "kind", "amount", "balance_after", "meal_date", "note", "by_name", "created_at"]

    def get_by_name(self, obj: BalanceTransaction) -> str:
        return obj.by.full_name if obj.by else ""


class AccountSerializer(serializers.ModelSerializer):
    """An account as the cashier sees it."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "employee_number", "department", "balance"]


class TopUpSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=3)


class CorrectionSerializer(TopUpSerializer):
    reason = serializers.CharField(max_length=200)
