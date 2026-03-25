param(
  [string]$Symbol = "XAUUSD",
  [string]$Strategy = "trend_following"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = "python"
$LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "launcher.log"

"[$(Get-Date -Format o)] Starting bot for $Symbol / $Strategy" | Tee-Object -FilePath $LogFile -Append
& $Python ".\main.py" --mode=live --symbol=$Symbol --strategy=$Strategy 2>&1 | Tee-Object -FilePath $LogFile -Append
