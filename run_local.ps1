# TITAN Berserker - Local Start Script (Windows)

# 1. Setup Python Environment
if (!(Test-Path ".venv")) {
    Write-Host "Creating Virtual Environment..." -ForegroundColor Cyan
    python -m venv .venv
}

Write-Host "Installing/Updating Python Requirements..." -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

# 2. Setup Frontend
Write-Host "Checking Frontend Dependencies..." -ForegroundColor Cyan
Set-Location frontend
if (!(Test-Path "node_modules")) {
    Write-Host "Installing NPM packages..." -ForegroundColor Yellow
    npm install
}
Set-Location ..

# 3. Run System
Write-Host "------------------------------------------------" -ForegroundColor Green
Write-Host "Starting TITAN Berserker System..." -ForegroundColor Green
Write-Host "API will run at: http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend will run at: http://localhost:5173" -ForegroundColor Green
Write-Host "------------------------------------------------" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop both." -ForegroundColor Gray

# Start API in a new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd $PWD; .\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000" -WindowStyle Normal

# Start Frontend in current window (or new window)
cd frontend
npm run dev
cd ..
