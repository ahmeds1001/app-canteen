"""Test suite on SQL Server (production database engine) instead of SQLite in memory.

    DB_ENGINE=mssql python manage.py test --settings=config.settings.test_mssql

Django creates and drops its own `test_<DB_NAME>` database; the real one is never touched. The connection
comes from .env / environment variables (DB_HOST, DB_USER…); an empty DB_USER uses Windows authentication.
"""
from . import base
from .test import *  # noqa: F401,F403

DATABASES = base.DATABASES  # the SQL Server settings from base, not test.py's SQLite in memory
