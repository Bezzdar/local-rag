@echo off
setlocal enabledelayedexpansion

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "MODE=%~1"

echo [update_windows] Root: %CD%
for /f %%i in ('git rev-parse --abbrev-ref HEAD') do set "BRANCH=%%i"
if "%BRANCH%"=="" goto :err
if "%BRANCH%"=="HEAD" (
  echo [update_windows] ERROR: detached HEAD. Checkout a branch first.
  goto :err
)

echo [update_windows] Current branch: %BRANCH%
git fetch --all --prune || goto :err

if /I "%MODE%"=="--hard-reset" (
  echo [update_windows] Hard reset to origin/%BRANCH% (local changes will be LOST)...
  git reset --hard origin/%BRANCH% || goto :err
  git clean -fd || goto :err
) else (
  echo [update_windows] Pulling updates (rebase)...
  git pull --rebase || goto :err
)

if not exist ".venv\Scripts\python.exe" (
  echo [update_windows] No venv found, creating .venv
  python -m venv .venv || goto :err
)

echo [update_windows] Updating backend dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :err
".venv\Scripts\python.exe" -m pip install -r apps\api\requirements.txt || goto :err

echo [update_windows] Updating frontend dependencies...
pushd apps\web
call npm install || goto :err
if exist .next rmdir /s /q .next
popd

echo [update_windows] Done. Restart API and WEB terminals if they are running.
exit /b 0

:err
echo [update_windows] ERROR.
exit /b 1
