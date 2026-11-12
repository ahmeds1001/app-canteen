@echo off
rem Site + API of the canteen on a Windows server (docs/installation-vm-windows.pdf, step 9).
rem Started at boot by the task "Cantine - Site"; if Waitress stops, it is restarted after 10 seconds.
rem The app listens on 127.0.0.1 only: nobody on the network reaches it directly. HTTPS is done in the same VM by
rem Caddy (run-https.cmd, task "Cantine - HTTPS"), which forwards to this port.
set PORT=8080
rem The only "proxy" allowed to tell the app the user's address and "https": Caddy, on this machine.
set PROXY_IP=127.0.0.1
cd /d "%~dp0..\..\backend"
if not exist "..\logs" mkdir "..\logs"
set DJANGO_SETTINGS_MODULE=config.settings.prod
:loop
echo %date% %time% Starting the site on 127.0.0.1:%PORT% >> "..\logs\site.log"
rem --trusted-proxy: keep the user's address and "https" sent by Caddy (without it: redirect loop, and the
rem login limit would count the whole company as one person).
".venv\Scripts\waitress-serve.exe" --listen=127.0.0.1:%PORT% --threads=8 --trusted-proxy=%PROXY_IP% ^
  --trusted-proxy-headers="x-forwarded-for x-forwarded-proto" --log-untrusted-proxy-headers ^
  config.wsgi:application >> "..\logs\site.log" 2>&1
timeout /t 10 /nobreak > nul
goto loop
