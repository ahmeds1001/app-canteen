"""Domain errors raised by services and translated to HTTP by the API layer."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


class DomainError(Exception):
    """A business rule was violated. `code` is stable and used by the frontend."""

    http_status = status.HTTP_400_BAD_REQUEST

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


class NotAllowed(DomainError):
    http_status = status.HTTP_403_FORBIDDEN


class Conflict(DomainError):
    http_status = status.HTTP_409_CONFLICT


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response({"code": exc.code, "detail": exc.message}, status=exc.http_status)
    return exception_handler(exc, context)
