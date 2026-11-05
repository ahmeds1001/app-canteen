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
