param(
    [switch]$HardReset
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "[update_windows] Root: $Root"

$Branch = (git rev-parse --abbrev-ref HEAD).Trim()
if (-not $Branch -or $Branch -eq "HEAD") {
    throw "Cannot detect current branch. Checkout a branch and retry."
}

Write-Host "[update_windows] Current branch: $Branch"
Write-Host "[update_windows] Fetching remote..."
git fetch --all --prune

if ($HardReset) {
    Write-Host "[update_windows] Hard reset to origin/$Branch (local changes will be LOST)..."
    git reset --hard "origin/$Branch"
    git clean -fd
} else {
    Write-Host "[update_windows] Pulling updates (rebase)..."
    git pull --rebase
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[update_windows] No venv found, creating .venv"
    python -m venv .venv
}

Write-Host "[update_windows] Updating backend dependencies..."
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r "apps/api/requirements.txt"

Write-Host "[update_windows] Updating frontend dependencies..."
Push-Location "apps/web"
npm install
if (Test-Path ".next") {
    Remove-Item ".next" -Recurse -Force
}
Pop-Location

Write-Host "[update_windows] Update completed. Restart API and WEB terminals if they are running."
