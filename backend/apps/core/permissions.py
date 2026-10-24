"""Role-based permissions for the API (spec §2 roles)."""
from rest_framework.permissions import BasePermission


def _has_role(user, *roles: str) -> bool:
    # An account with a temporary password (FR-40) may only change its password.
    return bool(
        user
        and user.is_authenticated
        and user.is_active_account
        and not user.must_change_password
        and user.role in roles
    )


def role_permission(*roles: str) -> type[BasePermission]:
    """Build a DRF permission class allowing only the given roles (admin always allowed)."""

    class _RolePermission(BasePermission):
        message = "Your role does not allow this action."

        def has_permission(self, request, view) -> bool:
            return _has_role(request.user, *roles, "admin")

    _RolePermission.__name__ = f"Role_{'_'.join(roles)}"
    return _RolePermission


IsEmployee = role_permission("employee", "hr", "chef", "scanner", "management")
IsHR = role_permission("hr")
IsChef = role_permission("chef")
IsScanner = role_permission("scanner")
IsManagement = role_permission("management")
IsChefOrManagement = role_permission("chef", "management")
IsAdmin = role_permission("admin")
