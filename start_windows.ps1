param(
    [string]$ApiHost = "127.0.0.1",
    [int]$ApiPort = 8000,
    [int]$WebPort = 3000
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "[start_windows] Root: $Root"

if (-not (Test-Path ".venv")) {
    Write-Host "[start_windows] Creating Python virtual environment..."
    python -m venv .venv
}

Write-Host "[start_windows] Installing backend dependencies..."
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r "apps/api/requirements.txt"

if (-not (Test-Path "apps/web/.env.local")) {
    Write-Host "[start_windows] Creating apps/web/.env.local from .env.example"
    Copy-Item ".env.example" "apps/web/.env.local"
}

Write-Host "[start_windows] Installing frontend dependencies..."
Push-Location "apps/web"
npm install
Pop-Location


$logFile = Join-Path $Root "data/logs/app.log"
$apiCmd = "Set-Location -LiteralPath '$Root'; .\.venv\Scripts\Activate.ps1; uvicorn apps.api.main:app --host $ApiHost --port $ApiPort --reload"
$webCmd = "Set-Location -LiteralPath '$Root\apps\web'; `$env:PORT='$WebPort'; npm run dev"
$logCmd = "Set-Location -LiteralPath '$Root'; if (-not (Test-Path 'data/logs')) { New-Item -ItemType Directory -Path 'data/logs' -Force | Out-Null }; if (-not (Test-Path '$logFile')) { New-Item -ItemType File -Path '$logFile' -Force | Out-Null }; Write-Host '[start_windows] Tailing log file: $logFile'; Get-Content -Path '$logFile' -Wait -Tail 30"

Write-Host "[start_windows] Starting API terminal..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", $apiCmd

Start-Sleep -Seconds 2

Write-Host "[start_windows] Starting API log terminal..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", $logCmd

Write-Host "[start_windows] Starting Web terminal..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", $webCmd

Write-Host "[start_windows] Done. API: http://$ApiHost`:$ApiPort, Web: http://localhost:$WebPort, Log: $logFile"
