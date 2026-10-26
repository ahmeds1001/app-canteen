from .base import *  # noqa: F401,F403

DEBUG = False
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast tests only
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}  # noqa: F405
# The public auth views set their own rate limits; a cache that stores nothing keeps tests from adding up.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
