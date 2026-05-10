#!/bin/bash
# Start TITAN Berserker Web Application for Linux/macOS

set -e
# Get the absolute path to the project root
root=$(cd "$(dirname "$0")/.." && pwd)

echo ""
echo -e "\033[1;33m  ======================================\033[0m"
echo -e "\033[1;33m   TITAN BERSERKER - Web Dashboard\033[0m"
echo -e "\033[1;33m  ======================================\033[0m"
echo ""

# Start FastAPI backend
echo -e "\033[1;36m[1/2] Starting API server on port 8000...\033[0m"
cd "$root"
uvicorn api.main:app --reload --port 8000 --no-access-log &
BACKEND_PID=$!

# Start Vite frontend dev server
echo -e "\033[1;36m[2/2] Starting frontend dev server on port 5173...\033[0m"
cd "$root/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo -e "\033[1;32m  Dashboard:  http://localhost:5173\033[0m"
echo -e "\033[1;32m  API Docs:   http://127.0.0.1:8000/docs\033[0m"
echo ""
echo -e "\033[0;90m  Press Ctrl+C to stop both servers.\033[0m"

# Trap SIGINT (Ctrl+C) and kill children
trap "kill $BACKEND_PID $FRONTEND_PID; exit" SIGINT

wait
