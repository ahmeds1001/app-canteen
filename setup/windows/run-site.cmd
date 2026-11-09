@echo off
rem Site + API of the canteen on a Windows server (docs/installation-vm-windows.pdf, step 9).
rem Started at boot by the task "Cantine - Site"; if Waitress stops, it is restarted after 10 seconds.
rem ---- To adapt (the 2 lines below) -------------------------------------------------------------------
set PORT=8080
rem Address of the company HTTPS proxy, the only machine allowed to talk to this port:
set PROXY_IP=192.168.1.10
rem -------------------------------------------------------------------------------------------------------
cd /d "%~dp0..\..\backend"
if not exist "..\logs" mkdir "..\logs"
set DJANGO_SETTINGS_MODULE=config.settings.prod
:loop
echo %date% %time% Starting the site on port %PORT% >> "..\logs\site.log"
rem --trusted-proxy: keep the user's address and "https" sent by the proxy (without it: redirect loop, and the
rem login limit would count the whole company as one person).
".venv\Scripts\waitress-serve.exe" --listen=0.0.0.0:%PORT% --threads=8 --trusted-proxy=%PROXY_IP% ^
  --trusted-proxy-headers="x-forwarded-for x-forwarded-proto" --log-untrusted-proxy-headers ^
  config.wsgi:application >> "..\logs\site.log" 2>&1
timeout /t 10 /nobreak > nul
goto loop
