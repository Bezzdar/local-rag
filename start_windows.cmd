@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo [start_windows] Root: %CD%

if not exist ".venv\Scripts\python.exe" (
  echo [start_windows] Creating Python virtual environment...
  python -m venv .venv || goto :err
)

echo [start_windows] Installing backend dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :err
".venv\Scripts\python.exe" -m pip install -r apps\api\requirements.txt || goto :err

if not exist "apps\web\.env.local" (
  echo [start_windows] Creating apps\web\.env.local from .env.example
  copy /Y ".env.example" "apps\web\.env.local" >nul || goto :err
)

echo [start_windows] Installing frontend dependencies...
pushd apps\web
call npm install || goto :err
popd

set "LOG_FILE=%ROOT%data\logs\app.log"
if not exist "%ROOT%data\logs" mkdir "%ROOT%data\logs"
if not exist "%LOG_FILE%" type nul > "%LOG_FILE%"

echo [start_windows] Starting API terminal...
start "RAG API" cmd /k "cd /d %ROOT% && call .venv\Scripts\activate.bat && uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 2 /nobreak >nul

echo [start_windows] Starting API LOG terminal...
start "RAG API LOG" cmd /k "cd /d %ROOT% && echo [start_windows] Tailing %LOG_FILE% && powershell -NoProfile -Command \"Get-Content -Path '%LOG_FILE%' -Wait -Tail 30\""

echo [start_windows] Starting WEB terminal...
start "RAG WEB" cmd /k "cd /d %ROOT%apps\web && set PORT=3000 && npm run dev"

echo [start_windows] Done. API: http://127.0.0.1:8000 WEB: http://localhost:3000 LOG: %LOG_FILE%
exit /b 0

:err
echo [start_windows] ERROR.
exit /b 1
