@echo off
rem Run a Django command with the PRODUCTION settings (Windows server, docs/installation-vm-windows.pdf).
rem   manage.cmd migrate          manage.cmd createsuperuser          manage.cmd generate_vapid_keys
rem Never "python manage.py" directly on the server: it would use the development settings (debug on).
cd /d "%~dp0..\..\backend"
set DJANGO_SETTINGS_MODULE=config.settings.prod
".venv\Scripts\python.exe" manage.py %*
