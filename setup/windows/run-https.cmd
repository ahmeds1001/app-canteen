@echo off
rem HTTPS in front of the canteen app: Caddy on port 3881 (docs/installation-vm-windows.pdf, section 14).
rem Started at boot by the task "Cantine - HTTPS"; if Caddy stops, it is restarted after 10 seconds.
rem Needs C:\cantine\tools\caddy.exe (build with the OVH DNS module) and C:\cantine\caddy.env (the OVH API key).
cd /d "%~dp0..\.."
if not exist "logs" mkdir "logs"
:loop
echo %date% %time% Starting HTTPS (Caddy) on port 3881 >> "logs\https.log"
"tools\caddy.exe" run --config "setup\windows\Caddyfile" --adapter caddyfile --envfile "caddy.env" >> "logs\https.log" 2>&1
timeout /t 10 /nobreak > nul
goto loop
