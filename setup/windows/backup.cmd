@echo off
rem Nightly backup: verified copy of the database + copy of the dish photos (task "Cantine - Sauvegarde").
rem ---- To adapt ----------------------------------------------------------------------------------------
set BACKUP_DIR=D:\CantineBackups
rem -------------------------------------------------------------------------------------------------------
cd /d "%~dp0..\..\backend"
if not exist "..\logs" mkdir "..\logs"
set DJANGO_SETTINGS_MODULE=config.settings.prod
echo %date% %time% Backup to %BACKUP_DIR% >> "..\logs\backup.log"
".venv\Scripts\python.exe" manage.py backup_database --dir "%BACKUP_DIR%" >> "..\logs\backup.log" 2>&1
