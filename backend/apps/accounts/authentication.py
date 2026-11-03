from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class ActiveAccountJWTAuthentication(JWTAuthentication):
    """JWT auth that also rejects tokens of accounts no longer Active (suspended, deactivated...)."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if not user.is_active_account:
            raise AuthenticationFailed("Account is not active.", code="account_not_active")
        return user


def active_account_rule(user) -> bool:
    """SIMPLE_JWT USER_AUTHENTICATION_RULE: only Active accounts may obtain or refresh tokens."""
    return user is not None and user.is_active_account
