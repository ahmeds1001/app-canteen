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

# Login and sign-up limits count per user address. Requests reach Django through 2 proxies (the company HTTPS
# proxy, then nginx), so the client is the 2nd address from the end of X-Forwarded-For. Without this, everyone
# would share one address and the login limit (10 per minute) would apply to the whole company at once.
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": int(env("NUM_PROXIES", "2"))}  # noqa: F405

# The limits' counters must be shared by every gunicorn worker (an in-memory cache would give each worker its
# own count: 4 workers = 4x the limit). A table in the app's own database; created by the "migrate" service.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "django_cache"}}

# Windows server without Docker (setup/windows/): no nginx, so Django also serves the built site (frontend/dist)
# and the dish photos. Docker keeps SERVE_FRONTEND off: nginx does both there.
SERVE_FRONTEND = env_bool("SERVE_FRONTEND", False)  # noqa: F405
if SERVE_FRONTEND:
    WHITENOISE_ROOT = BASE_DIR.parent / "frontend" / "dist"  # noqa: F405
    WHITENOISE_INDEX_FILE = True
    # Windows does not know .webmanifest: without this the install file of the app goes out as octet-stream.
    WHITENOISE_MIMETYPES = {".webmanifest": "application/manifest+json"}

    def WHITENOISE_IMMUTABLE_FILE_TEST(path, url):  # noqa: N802 - setting name
        return url.startswith("/assets/") or url.startswith("/static/")  # file names carry a hash

    def WHITENOISE_ADD_HEADERS_FUNCTION(headers, path, url):  # noqa: N802 - setting name
        if url in ("/", "/index.html", "/sw.js"):  # phones must get a new version of the app at once
            headers["Cache-Control"] = "no-cache"
