from .base import *  # noqa: F401,F403

DEBUG = False

if SECRET_KEY.startswith("dev-only"):  # noqa: F405
    raise RuntimeError("Set DJANGO_SECRET_KEY in production.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_CONTENT_TYPE_NOSNIFF = True
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")  # noqa: F405

# Static files: compressed, with hashed names (cached forever), served by WhiteNoise. Built at image build time.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# The container health check calls http://localhost:8000/api/v1/health/ from inside the container: that host
# must be accepted, and that URL must not be redirected to HTTPS (no TLS inside the Docker network).
ALLOWED_HOSTS = [*ALLOWED_HOSTS, "localhost"]  # noqa: F405
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]
