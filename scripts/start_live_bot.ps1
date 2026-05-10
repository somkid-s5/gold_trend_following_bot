# Start TITAN Berserker Live Engine (Multi-Symbol Portfolio)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = "python"
$LogDir = Join-Path $Root "logs"
if (!(Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
$LogFile = Join-Path $LogDir "launcher.log"

Write-Host "🚀 Starting TITAN Portfolio Engine..." -ForegroundColor Cyan
"[$(Get-Date -Format o)] Starting portfolio engine" | Tee-Object -FilePath $LogFile -Append
& $Python ".\main.py" --mode=live 2>&1 | Tee-Object -FilePath $LogFile -Append
