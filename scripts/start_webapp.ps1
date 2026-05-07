# Start TITAN Berserker Web Application
# This script starts both the FastAPI backend and the Vite dev frontend.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host "  ======================================" -ForegroundColor Yellow
Write-Host "   TITAN BERSERKER - Web Dashboard" -ForegroundColor Yellow
Write-Host "  ======================================" -ForegroundColor Yellow
Write-Host ""

# Start FastAPI backend
Write-Host "[1/2] Starting API server on port 8000..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit -Command `"cd '$root'; uvicorn api.main:app --reload --port 8000 --no-access-log`""

# Start Vite frontend dev server
Write-Host "[2/2] Starting frontend dev server on port 5173..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit -Command `"cd '$root\frontend'; npm run dev`""

Start-Sleep -Seconds 2
Write-Host ""
Write-Host "  Dashboard:  http://localhost:5173" -ForegroundColor Green
Write-Host "  API Docs:   http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "  Press Ctrl+C in each window to stop." -ForegroundColor DarkGray
