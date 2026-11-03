"""Read-only queries for the prepaid balance."""
from django.db.models import Q, QuerySet

from apps.accounts.models import User

from .models import BalanceTransaction


def history(user: User, limit: int = 100) -> QuerySet[BalanceTransaction]:
    return BalanceTransaction.objects.filter(user=user).select_related("by", "reservation")[:limit]


def accounts(q: str) -> QuerySet[User]:
    """Active accounts for the cashier: search by first name, last name, employee number or email."""
    qs = User.objects.filter(status=User.Status.ACTIVE)
    if q:
        qs = qs.filter(
            Q(last_name__icontains=q) | Q(first_name__icontains=q)
            | Q(employee_number__icontains=q) | Q(work_email__icontains=q)
        )
    return qs.order_by("last_name", "first_name")
