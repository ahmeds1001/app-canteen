# Copies the project agents into .claude\agents so Claude Code can use them.
# Run once from the repository root:  powershell -ExecutionPolicy Bypass -File setup\install-agents.ps1
$src = Join-Path $PSScriptRoot "claude-agents"
$dst = Join-Path (Split-Path $PSScriptRoot -Parent) ".claude\agents"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item -Path (Join-Path $src "*") -Destination $dst -Force
Write-Host "Agents installed in $dst :" (Get-ChildItem $dst -Filter *.md).Count "agents"
