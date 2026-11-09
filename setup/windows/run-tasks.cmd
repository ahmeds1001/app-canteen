@echo off
rem Scheduled jobs of the canteen, every minute (closing reservations, finalization, reminders, notifications).
rem Started at boot by the task "Cantine - Taches"; restarted after 10 seconds if it stops. ONE copy only.
cd /d "%~dp0..\..\backend"
if not exist "..\logs" mkdir "..\logs"
set DJANGO_SETTINGS_MODULE=config.settings.prod
:loop
echo %date% %time% Starting the scheduled jobs >> "..\logs\tasks.log"
".venv\Scripts\python.exe" manage.py run_scheduler >> "..\logs\tasks.log" 2>&1
timeout /t 10 /nobreak > nul
goto loop
