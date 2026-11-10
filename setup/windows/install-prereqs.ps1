# Installs the software the canteen app needs on a new Windows Server VM (guide step 3):
#   Python 3.12, Node.js 22 LTS, Git, SQL Server 2022 Express (instance SQLEXPRESS), ODBC Driver 18, SSMS 20.2.
#
# Two ways to use it:
#  A. The VM has a good internet connection -> in the VM, PowerShell "as administrator":
#       powershell -ExecutionPolicy Bypass -File C:\Install\install-prereqs.ps1
#  B. The VM's connection is slow -> download on another PC first (installs NOTHING there):
#       powershell -ExecutionPolicy Bypass -File install-prereqs.ps1 -DownloadOnly -Folder C:\CantineInstall
#     then copy the whole folder into the VM as C:\Install and run command A in the VM (no internet needed).
#
# Safe to run again: anything already downloaded or installed is skipped. Every file must carry a valid publisher
# signature; Microsoft's and Node's files are also checked against their official checksums.
# Log: <folder>\install-prereqs.log

param(
    [switch]$DownloadOnly,
    [string]$Folder = 'C:\Install'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'      # makes Invoke-WebRequest much faster on Windows PowerShell 5.1
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$dir = $Folder
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Start-Transcript -Path "$dir\install-prereqs.log" -Append | Out-Null

function Get-Installer([string]$url, [string]$name, [string]$sha256) {
    $path = Join-Path $dir $name
    if (Test-Path $path) { Write-Host "  using $name" } else {
        Write-Host "  downloading $name ..."
        Invoke-WebRequest -Uri $url -OutFile $path -UseBasicParsing
    }
    Test-Installer $path $sha256
    return $path
}

function Test-Installer([string]$path, [string]$sha256) {
    $name = Split-Path $path -Leaf
    if ($sha256 -and (Get-FileHash $path -Algorithm SHA256).Hash -ne $sha256.ToUpper()) {
        Remove-Item $path
        throw "$name : wrong checksum, file removed. Run the script again."
    }
    $sig = Get-AuthenticodeSignature $path
    if ($sig.Status -ne 'Valid') { throw "$name : signature not valid ($($sig.Status))." }
    Write-Host "  signed by: $($sig.SignerCertificate.GetNameInfo('SimpleName', $false))"
}

function Invoke-Installer([string]$file, [string]$arguments) {
    if ($DownloadOnly) { return }
    $p = Start-Process -FilePath $file -ArgumentList $arguments -Wait -PassThru
    if ($p.ExitCode -eq 3010) { Write-Host "  installed (Windows asks for a restart at the end)"; $script:restart = $true }
    elseif ($p.ExitCode -ne 0) { throw "$file ended with code $($p.ExitCode)." }
    else { Write-Host "  installed" }
}

function Get-MsiProductName([string]$path) {
    $i = New-Object -ComObject WindowsInstaller.Installer
    $db = $i.GetType().InvokeMember('OpenDatabase', 'InvokeMethod', $null, $i, @($path, 0))
    $v = $db.GetType().InvokeMember('OpenView', 'InvokeMethod', $null, $db, @("SELECT Value FROM Property WHERE Property='ProductName'"))
    $v.GetType().InvokeMember('Execute', 'InvokeMethod', $null, $v, $null)
    $r = $v.GetType().InvokeMember('Fetch', 'InvokeMethod', $null, $v, $null)
    return $r.GetType().InvokeMember('StringData', 'GetProperty', $null, $r, 1)
}

# In download-only mode nothing counts as "installed" on this PC: we only fetch the files.
function Test-Installed([scriptblock]$check) {
    if ($DownloadOnly) { return $false }
    if (& $check) { Write-Host '  already installed'; return $true }
    return $false
}

$restart = $false
try {
    if ($DownloadOnly) { Write-Host "DOWNLOAD ONLY into $dir - nothing is installed on this computer." -ForegroundColor Yellow }

    # 1. Python 3.12, for all users, added to PATH. A python-3.12.x installer already in the folder is used as is;
    #    otherwise 3.12.10 (last 3.12 release with a Windows installer) is downloaded.
    Write-Host "`n[1/6] Python 3.12"
    if (-not (Test-Installed { Test-Path 'C:\Program Files\Python312\python.exe' })) {
        $local = Get-ChildItem $dir | Where-Object { $_.Name -match '^python-3\.12\.\d+-amd64\.exe$' } |
            Sort-Object { [version]($_.Name -replace '^python-|-amd64\.exe$', '') } | Select-Object -Last 1
        if ($local) { Write-Host "  using $($local.Name)"; Test-Installer $local.FullName $null; $f = $local.FullName }
        else { $f = Get-Installer 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' 'python-3.12.10-amd64.exe' $null }
        Invoke-Installer $f '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0'
    }

    # 2. Node.js 22 LTS (only used to build the site). A node-v22 MSI already in the folder is used as is.
    Write-Host "`n[2/6] Node.js 22 LTS"
    if (-not (Test-Installed { Test-Path 'C:\Program Files\nodejs\node.exe' })) {
        $local = Get-ChildItem $dir -Filter 'node-v22.*-x64.msi' | Sort-Object Name | Select-Object -Last 1
        if ($local) { Write-Host "  using $($local.Name)"; Test-Installer $local.FullName $null; $f = $local.FullName } else {
            $v = ((Invoke-RestMethod 'https://nodejs.org/dist/index.json') | Where-Object { $_.version -like 'v22.*' })[0].version
            $msi = "node-$v-x64.msi"
            $line = (Invoke-WebRequest "https://nodejs.org/dist/$v/SHASUMS256.txt" -UseBasicParsing).Content -split "`n" | Where-Object { $_ -like "*  $msi" }
            $f = Get-Installer "https://nodejs.org/dist/$v/$msi" $msi ($line -split '\s+')[0]
        }
        Invoke-Installer 'msiexec.exe' "/i `"$f`" /qn /norestart"
    }

    # 3. Git for Windows (latest release, default options). A Git installer already in the folder is used as is.
    Write-Host "`n[3/6] Git"
    if (-not (Test-Installed { Test-Path 'C:\Program Files\Git\cmd\git.exe' })) {
        $local = Get-ChildItem $dir | Where-Object { $_.Name -match '^Git-[\d.]+-64-bit\.exe$' } | Sort-Object Name | Select-Object -Last 1
        if ($local) { Write-Host "  using $($local.Name)"; Test-Installer $local.FullName $null; $f = $local.FullName } else {
            $rel = Invoke-RestMethod 'https://api.github.com/repos/git-for-windows/git/releases/latest'
            $asset = $rel.assets | Where-Object { $_.name -match '^Git-[\d.]+-64-bit\.exe$' } | Select-Object -First 1
            $f = Get-Installer $asset.browser_download_url $asset.name $null
        }
        Invoke-Installer $f '/VERYSILENT /NORESTART /NOCANCEL /SP- /SUPPRESSMSGBOXES'
    }

    # 4. SQL Server 2022 Express: instance SQLEXPRESS, Windows sign-in, local administrators are sysadmin.
    #    The small Microsoft installer downloads the full offline package (SQLEXPR_x64_<lang>.exe, ~250 MB) first,
    #    so the VM needs no internet for this step.
    Write-Host "`n[4/6] SQL Server 2022 Express"
    if (-not (Test-Installed { Get-Service 'MSSQL$SQLEXPRESS' -ErrorAction SilentlyContinue })) {
        # Any language of the offline package works (ENU, FRA...): the database behaves the same.
        $found = Get-ChildItem $dir | Where-Object { $_.Name -match '^SQLEXPR_x64_[A-Z]{3}\.exe$' } | Select-Object -First 1
        $media = if ($found) { $found.FullName } else { Join-Path $dir 'SQLEXPR_x64_ENU.exe' }
        if ($found) { Write-Host "  using $($found.Name)" } else {
            $ssei = Get-Installer 'https://download.microsoft.com/download/29654887-7cde-4397-bba3-d7f087970845/SQL2022-SSEI-Expr.exe' 'SQL2022-SSEI-Expr.exe' 'E2B8E8AAD30D8B1A1922C6C0976C806F0A2E08D04B2DE100A9D70B9F94750BB1'
            Write-Host '  downloading the offline package (~250 MB, a few minutes) ...'
            $p = Start-Process -FilePath $ssei -ArgumentList "/ACTION=Download /MEDIAPATH=`"$dir`" /MEDIATYPE=Core /QUIET" -Wait -PassThru
            if ($p.ExitCode -ne 0 -or -not (Test-Path $media)) { throw "SQL Server download failed (code $($p.ExitCode))." }
        }
        Test-Installer $media $null
        if (-not $DownloadOnly) {
            $x = Join-Path $dir 'SQLEXPR'
            Write-Host '  extracting ...'
            $p = Start-Process -FilePath $media -ArgumentList "/q /x:`"$x`"" -Wait -PassThru
            if (-not (Test-Path "$x\setup.exe")) { throw "SQL Server package could not be extracted (code $($p.ExitCode))." }
            Write-Host '  installing (10-20 minutes) ...'
            Invoke-Installer "$x\setup.exe" '/Q /ACTION=Install /FEATURES=SQLEngine /INSTANCENAME=SQLEXPRESS /SQLSYSADMINACCOUNTS="BUILTIN\Administrators" /IACCEPTSQLSERVERLICENSETERMS /UPDATEENABLED=0'
        }
    }

    # 5. ODBC Driver 18 for SQL Server (the app talks to SQL Server through it). Needs the Visual C++ runtime that
    #    SQL Server installs, so it comes after step 4.
    Write-Host "`n[5/6] ODBC Driver 18 for SQL Server"
    if (-not (Test-Installed { Get-OdbcDriver -Name 'ODBC Driver 18 for SQL Server' -Platform '64-bit' -ErrorAction SilentlyContinue })) {
        $f = Get-Installer 'https://go.microsoft.com/fwlink/?linkid=2280794' 'msodbcsql-latest.msi' $null
        if ((Get-MsiProductName $f) -notlike '*ODBC Driver 18*') {
            Write-Host '  latest link is not version 18, using 18.3.3.1'
            $f = Get-Installer 'https://go.microsoft.com/fwlink/?linkid=2266640' 'msodbcsql-18.3.3.1.msi' $null
        }
        Write-Host "  $(Get-MsiProductName $f)"
        Invoke-Installer 'msiexec.exe' "/i `"$f`" /qn /norestart IACCEPTMSODBCSQLLICENSETERMS=YES"
    }

    # 6. SQL Server Management Studio 20.2 (the company's tool), English, full offline installer
    Write-Host "`n[6/6] SQL Server Management Studio 20.2 (470 MB)"
    if (-not (Test-Installed { Test-Path 'C:\Program Files (x86)\Microsoft SQL Server Management Studio 20\Common7\IDE\Ssms.exe' })) {
        $f = Get-Installer 'https://download.microsoft.com/download/9/b/e/9bee9f00-2ee2-429a-9462-c9bc1ce14c28/SSMS-Setup-ENU.exe' 'SSMS-Setup-ENU.exe' '12DD3B24330AD074DBB71F28AD06EAAA9757BD5C9A750ADD5088C4DB54A7D4F6'
        Invoke-Installer $f '/install /quiet /norestart'
    }

    if ($DownloadOnly) {
        Copy-Item -Path $PSCommandPath -Destination $dir -Force -ErrorAction SilentlyContinue
        Write-Host "`nAll files are in $dir (this script too). Copy the folder into the VM as C:\Install, then in the VM:" -ForegroundColor Green
        Write-Host '  powershell -ExecutionPolicy Bypass -File C:\Install\install-prereqs.ps1'
        Write-Host "`nDONE" -ForegroundColor Green
        return
    }

    # Check
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    Write-Host "`n=== Check ==="
    Write-Host ("python : " + (& python --version 2>&1))
    Write-Host ("node   : " + (& node --version 2>&1))
    Write-Host ("git    : " + (& git --version 2>&1))
    Write-Host ("odbc   : " + ((Get-OdbcDriver -Platform '64-bit' | Where-Object Name -like 'ODBC Driver 1*' | ForEach-Object Name) -join ', '))
    Write-Host ("ssms   : " + (Test-Path 'C:\Program Files (x86)\Microsoft SQL Server Management Studio 20\Common7\IDE\Ssms.exe'))
    Write-Host 'sql    :'
    & sqlcmd -S 'localhost\SQLEXPRESS' -E -Q 'SET NOCOUNT ON; SELECT @@VERSION' -h -1
    if ($restart) { Write-Host "`nRestart the VM now (Restart-Computer), then reconnect." -ForegroundColor Yellow }
    Write-Host "`nDONE" -ForegroundColor Green
} catch {
    Write-Host "`nSTOPPED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Fix the cause (or send this message), then run the script again: finished steps are skipped.'
} finally {
    Stop-Transcript | Out-Null
}
