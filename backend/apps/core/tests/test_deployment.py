"""Deployment details the Docker stack relies on (docs/architecture-technique.pdf)."""
import importlib
import os
from unittest import mock

from django.db.utils import OperationalError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


def prod_settings():
    with mock.patch.dict(os.environ, {"DJANGO_SECRET_KEY": "x" * 50, "DJANGO_ALLOWED_HOSTS": "cantine.example.tn"}):
        importlib.reload(importlib.import_module("config.settings.base"))  # prod reads base's values
        return importlib.reload(importlib.import_module("config.settings.prod"))


class HealthTests(TestCase):
    def test_ok_when_the_database_answers(self):
        body = APIClient().get("/api/v1/health/").json()
        self.assertEqual((body["status"], body["database"]), ("ok", "ok"))

    def test_503_when_the_database_is_unreachable(self):
        down = mock.patch("apps.core.views.connection.cursor", side_effect=OperationalError("down"))
        with down, self.assertLogs("apps.core.views", level="ERROR"):
            response = APIClient().get("/api/v1/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["database"], "unavailable")


class ProductionSettingsTests(TestCase):
    def test_container_health_check_is_accepted_and_not_redirected(self):
        prod = prod_settings()
        self.assertEqual(prod.ALLOWED_HOSTS, ["cantine.example.tn", "localhost"])
        with override_settings(SECURE_SSL_REDIRECT=True, SECURE_REDIRECT_EXEMPT=prod.SECURE_REDIRECT_EXEMPT,
                               ALLOWED_HOSTS=prod.ALLOWED_HOSTS):
            # What `docker compose` runs inside the container: plain HTTP to localhost.
            self.assertEqual(APIClient().get("/api/v1/health/", HTTP_HOST="localhost").status_code, 200)
            # Any other page is still forced to HTTPS.
            self.assertEqual(APIClient().get("/api/v1/menus/", HTTP_HOST="localhost").status_code, 301)

    def test_https_seen_through_the_proxy_header(self):
        prod = prod_settings()
        self.assertEqual(prod.SECURE_PROXY_SSL_HEADER, ("HTTP_X_FORWARDED_PROTO", "https"))
        with override_settings(SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=prod.SECURE_PROXY_SSL_HEADER):
            # nginx forwards the proxy's "https": no redirect loop.
            response = APIClient().get("/api/v1/settings/public/", HTTP_X_FORWARDED_PROTO="https")
        self.assertEqual(response.status_code, 200)

    def test_static_files_served_by_whitenoise(self):
        prod = prod_settings()
        self.assertEqual(prod.STORAGES["staticfiles"]["BACKEND"],
                         "whitenoise.storage.CompressedManifestStaticFilesStorage")
        self.assertIn("whitenoise.middleware.WhiteNoiseMiddleware", prod.MIDDLEWARE)


# The test settings use a cache that stores nothing; the limit needs a real one to count.
@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                       "LOCATION": "login-limit-tests"}})
class LoginLimitBehindProxiesTests(TestCase):
    """The login limit (10 per minute) counts per person, not for the whole company behind the proxies."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()  # throttle counters

    def _login(self, client_ip):
        # What reaches Django in production: the company proxy added the user's address, nginx added the proxy's.
        return APIClient().post("/api/v1/auth/login/", {"work_email": "x@ovagri.test", "password": "wrong"},
                                format="json", HTTP_X_FORWARDED_FOR=f"{client_ip}, 10.0.0.2",
                                REMOTE_ADDR="172.18.0.4")

    def test_two_hundred_people_can_log_in_in_the_same_minute(self):
        prod = prod_settings()
        with override_settings(REST_FRAMEWORK=prod.REST_FRAMEWORK):
            codes = {self._login(f"192.168.1.{n}").status_code for n in range(1, 201)}
        self.assertNotIn(429, codes)

    def test_one_person_retrying_is_still_limited(self):
        prod = prod_settings()
        with override_settings(REST_FRAMEWORK=prod.REST_FRAMEWORK):
            codes = [self._login("192.168.1.7").status_code for _ in range(11)]
        self.assertEqual(codes[-1], 429)
        self.assertNotIn(429, codes[:10])
