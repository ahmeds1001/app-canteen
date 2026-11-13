# Update the canteen app on the Windows VM to the latest pushed version (docs/installation-vm-windows.pdf).
#
#   PowerShell as administrator:   powershell -ExecutionPolicy Bypass -File C:\cantine\setup\windows\update.ps1
#
# Steps: checks -> database backup -> git pull -> only what the new commits need (Python packages, build tools,
# site build, database migrations, static files) -> restart the site and the scheduled jobs -> health check.
# The site keeps running the old version until the restart near the end (about 10 seconds of cut), and if any
# step fails before that, the script stops WITHOUT restarting: the old version stays online.
#
# Run it outside meal times and not just before the reservation deadline. Never edit code in the VM: change it
# on the PC, test, commit and push, then run this script. .env, caddy.env and the certificate are not in git.
param(
    [switch]$Force   # also run every step when there is nothing new (e.g. to finish an update that stopped)
)

$ErrorActionPreference = 'Stop'
$Root    = (Resolve-Path "$PSScriptRoot\..\..").Path
$Backend = Join-Path $Root 'backend'
$Front   = Join-Path $Root 'frontend'
$Python  = Join-Path $Backend '.venv\Scripts\python.exe'
$Manage  = Join-Path $PSScriptRoot 'manage.cmd'
$Health  = 'http://127.0.0.1:8080/api/v1/health/'   # the app itself, behind Caddy (Host: localhost is allowed)
$Public  = 'https://cantine.groupe-ovagri.com:3881/api/v1/health/'
$Logs    = Join-Path $Root 'logs'
if (-not (Test-Path $Logs)) { New-Item -ItemType Directory $Logs | Out-Null }
Start-Transcript -Path (Join-Path $Logs ("update-" + (Get-Date -Format 'yyyyMMdd-HHmm') + ".log")) | Out-Null

function Step($text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Fail($text) {
    Write-Host ""; Write-Host "STOPPED: $text" -ForegroundColor Red
    Write-Host "The site was NOT restarted: the previous version is still online." -ForegroundColor Yellow
    Stop-Transcript | Out-Null; exit 1
}
# Native commands do not stop the script on their own: check the exit code after each one.
function Run([string]$what, [scriptblock]$cmd) {
    & $cmd
    if ($LASTEXITCODE -ne 0) { Fail "$what (exit code $LASTEXITCODE)" }
}

try {
    # ---------------------------------------------------------------------------------------------- checks
    Step "Checks"
    $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
             ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) { Fail "open PowerShell as administrator" }
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    Set-Location $Root
    foreach ($t in 'git', 'npm.cmd') { if (-not (Get-Command $t -ErrorAction SilentlyContinue)) { Fail "$t not found" } }
    if (-not (Test-Path $Python)) { Fail "Python environment not found: $Python" }

    # Code edited in the VM would block the pull or be lost: it must go through the PC and git.
    $local = git status --porcelain --untracked-files=no
    if ($local) { $local; Fail "files were changed in the VM (listed above). Undo them, or ask before going on." }

    Run "git fetch" { git fetch --quiet origin main }
    $old = (git rev-parse HEAD).Trim()
    $new = (git rev-parse origin/main).Trim()
    if ($old -eq $new -and -not $Force) {
        Write-Host "Already up to date ($($old.Substring(0,7))). Nothing to do. (-Force runs every step anyway.)" -ForegroundColor Green
        Stop-Transcript | Out-Null; exit 0
    }
    if ($old -ne $new) {
        Write-Host "New commits:"
        git log --oneline "$old..$new"
    }

    # ---------------------------------------------------------------------------------------------- backup
    Step "Database backup (before any change)"
    $env:DJANGO_SETTINGS_MODULE = 'config.settings.prod'
    Push-Location $Backend
    Run "backup" { & $Python manage.py backup_database --dir 'D:\CantineBackups' }
    Pop-Location

    # ---------------------------------------------------------------------------------------------- code
    Step "Getting the code"
    Run "git pull" { git pull --ff-only --quiet origin main }
    if ($Force) { $changed = @('backend/requirements/', 'frontend/package-lock.json', 'frontend/', 'backend/') }
    else { $changed = @(git diff --name-only $old $new) }
    function Changed($prefix) { [bool]($changed | Where-Object { $_ -like "$prefix*" }) }
    $changed | ForEach-Object { "  $_" }

    # ---------------------------------------------------------------------------------------------- Python
    if (Changed 'backend/requirements/') {
        Step "Python packages"
        Run "pip install" { & $Python -m pip install --disable-pip-version-check -q -r (Join-Path $Backend 'requirements\windows.txt') }
    }

    # ---------------------------------------------------------------------------------------------- site
    if ((Changed 'frontend/package-lock.json') -or -not (Test-Path (Join-Path $Front 'node_modules'))) {
        Step "Build tools (npm ci)"
        Push-Location $Front; Run "npm ci" { npm.cmd ci --no-audit --no-fund }; Pop-Location
    }
    if (Changed 'frontend/') {
        Step "Building the site"
        # Built into dist-new first: if the build fails, the site online (dist) is untouched.
        Push-Location $Front
        if (Test-Path dist-new) { Remove-Item dist-new -Recurse -Force }
        Run "site build" { npm.cmd run build -- --outDir dist-new --emptyOutDir }
        if (-not (Test-Path 'dist-new\index.html')) { Fail "site build produced no index.html" }
        Pop-Location
    }

    # ---------------------------------------------------------------------------------------------- database
    if (Changed 'backend/') {
        Step "Database migrations and static files"
        Run "migrate" { & $Manage migrate --noinput }
        Run "createcachetable" { & $Manage createcachetable }
        Run "collectstatic" { & $Manage collectstatic --noinput }
    }

    # ---------------------------------------------------------------------------------------------- restart
    Step "Restarting the site and the scheduled jobs"
    Stop-ScheduledTask 'Cantine - Site'; Stop-ScheduledTask 'Cantine - Taches'
    # Only this app's processes (the HTTPS task, Caddy, keeps running: the certificate does not change).
    Get-Process waitress-serve, python -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -like "$Root\*" } | Stop-Process -Force
    Start-Sleep -Seconds 2
    if (Test-Path (Join-Path $Front 'dist-new')) {
        Push-Location $Front
        if (Test-Path dist-old) { Remove-Item dist-old -Recurse -Force }   # build output only, no data
        if (Test-Path dist) { Rename-Item dist dist-old }                  # previous version kept, just in case
        Rename-Item dist-new dist
        Pop-Location
    }
    Start-ScheduledTask 'Cantine - Site'; Start-ScheduledTask 'Cantine - Taches'

    # ---------------------------------------------------------------------------------------------- check
    Step "Health check"
    $ok = $false
    for ($i = 0; $i -lt 30 -and -not $ok; $i++) {
        Start-Sleep -Seconds 5
        $body = curl.exe -s --max-time 5 -H 'Host: localhost' $Health
        $ok = "$body" -match '"status":"ok"'
    }
    $public = curl.exe -s --max-time 10 $Public
    if ("$public" -notmatch '"status":"ok"') {
        Write-Host "Note: the public address did not answer from inside the VM (check it from a phone): $Public" -ForegroundColor Yellow
    }
    $tasks = Get-ScheduledTask 'Cantine - Site', 'Cantine - Taches', 'Cantine - HTTPS' | Select-Object TaskName, State
    $tasks | Format-Table -AutoSize | Out-Host
    if (-not $ok) {
        Write-Host "The site does not answer 'ok' after 2.5 minutes. Look at C:\cantine\logs\site.log (last lines):" -ForegroundColor Red
        Get-Content (Join-Path $Logs 'site.log') -Tail 20
        Stop-Transcript | Out-Null; exit 1
    }
    Write-Host $body
    Write-Host ""
    Write-Host "UPDATE DONE: version $((git rev-parse --short HEAD).Trim()) is online." -ForegroundColor Green
    Write-Host "Phones get the new version the next time they open the app (or after one reload)."
}
catch {
    Fail $_.Exception.Message
}
Stop-Transcript | Out-Null
