#Requires -Version 5.1
<#
.SYNOPSIS
    Запуск Local RAG Assistant с просмотром логов в реальном времени.

.DESCRIPTION
    Запускает API и Web в отдельных окнах, затем открывает
    два дополнительных окна с live-просмотром логов:
      • RAG — Серверный лог  (app_*.log)
      • RAG — UI события     (ui_*.log)

    Используйте это вместо run.ps1, когда нужно отслеживать
    работу приложения в режиме реального времени.
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

$ROOT = $PSScriptRoot

# ── Вывод ────────────────────────────────────────────────────────
function Write-OK([string]$msg)  { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-ERR([string]$msg) { Write-Host "  [!]  $msg" -ForegroundColor Red   }

# ── Проверка Node.js ─────────────────────────────────────────────
function Confirm-Node {
    $node = $null

    try {
        $null = node --version 2>$null
        $node = 'node'
    } catch {}

    if (-not $node) {
        $candidates = @(
            "$env:ProgramFiles\nodejs\node.exe",
            "${env:ProgramFiles(x86)}\nodejs\node.exe",
            "$env:LOCALAPPDATA\Programs\nodejs\node.exe"
        )
        foreach ($p in $candidates) {
            if (Test-Path $p) { $node = $p; break }
        }
    }

    if (-not $node) {
        Write-ERR "Node.js не обнаружен ни в PATH, ни в стандартных папках!"
        Write-Host "       Установите Node.js 22 LTS или 20 LTS: https://nodejs.org/"
        return $null
    }

    $ver = (& $node --version 2>&1).Trim()
    if ($ver -match '^v(\d+)\.(\d+)') {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]

        if ($major -eq 19 -or $major -eq 21) {
            Write-ERR "Node.js $ver — нечётная (не-LTS) версия, не поддерживается."
            return $null
        }
        if ($major -lt 20) {
            Write-ERR "Node.js $ver устарел. Требуется 20.9.0 LTS+ или 22 LTS."
            return $null
        }
        if ($major -eq 20 -and $minor -lt 9) {
            Write-ERR "Node.js $ver — слишком старая сборка 20.x. Требуется 20.9.0+."
            return $null
        }
    } else {
        Write-ERR "Не удалось разобрать версию Node.js: $ver"
        return $null
    }

    Write-OK "Node.js $ver"
    return $node
}

# ── Проверка Python ──────────────────────────────────────────────
function Confirm-Python {
    $py = $null
    foreach ($cmd in 'python', 'python3') {
        try {
            $v = & $cmd --version 2>&1
            if ("$v" -match 'Python \d') { $py = $cmd; break }
        } catch {}
    }

    if (-not $py) {
        Write-ERR "Python не обнаружен!"
        Write-Host "       Установите Python 3.10+ с https://www.python.org/"
        return $null
    }

    $ver = ("$(& $py --version 2>&1)").Trim() -replace '^Python\s*', ''
    if ($ver -match '^(\d+)\.(\d+)') {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
            Write-ERR "Python $ver устарел. Требуется 3.10+."
            return $null
        }
    }

    Write-OK "Python $ver"
    return $py
}

# ── Вспомогательная функция: запуск окна с логом ─────────────────
function Start-LogWindow([string]$title, [string]$prefix, [string]$logDir) {
    # Ждём появления файла лога (до 30 сек), потом tail
    $watchScript = @"
`$host.UI.RawUI.WindowTitle = '$title'
`$logDir = '$logDir'
`$prefix = '$prefix'

Write-Host "Ожидание файла лога ($prefix`_*.log)..." -ForegroundColor Cyan

`$deadline = (Get-Date).AddSeconds(30)
`$f = `$null

while ((Get-Date) -lt `$deadline -and -not `$f) {
    `$f = Get-ChildItem "`$logDir\`${prefix}_*.log" -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime -Descending |
          Select-Object -First 1
    if (-not `$f) { Start-Sleep -Milliseconds 500 }
}

if (-not `$f) {
    Write-Host "Файл лога не найден в `$logDir" -ForegroundColor Red
    Read-Host "Нажмите Enter для выхода"
} else {
    Write-Host "Читаю: `$(`$f.FullName)" -ForegroundColor Green
    Write-Host "-------------------------------------------"
    Get-Content `$f.FullName -Wait -Tail 50
}
"@
    Start-Process powershell -ArgumentList @(
        '-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $watchScript
    )
}

# ════════════════════════════════════════════════════════════════
#  ОСНОВНАЯ ЛОГИКА
# ════════════════════════════════════════════════════════════════
Clear-Host
Write-Host ""
Write-Host "  ╔════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "  ║    Local RAG Assistant — Run + Logs        ║" -ForegroundColor Yellow
Write-Host "  ╚════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""

Set-Location $ROOT

$nodeExe = Confirm-Node
if (-not $nodeExe) {
    Read-Host "`n  Нажмите Enter для выхода"
    exit 1
}

$pyExe = Confirm-Python
if (-not $pyExe) {
    Read-Host "`n  Нажмите Enter для выхода"
    exit 1
}

# ── Виртуальное окружение ────────────────────────────────────────
$venvPy = Join-Path $ROOT '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Write-Host "  Создание виртуального окружения .venv..."
    & $pyExe -m venv (Join-Path $ROOT '.venv')
    if ($LASTEXITCODE -ne 0) {
        Write-ERR "Не удалось создать .venv."
        Read-Host "`n  Нажмите Enter для выхода"
        exit 1
    }
    Write-Host ""
}

# ── Зависимости backend ──────────────────────────────────────────
Write-Host "  Проверка зависимостей backend..."
& $venvPy -m pip install -q --upgrade pip
& $venvPy -m pip install -q -r (Join-Path $ROOT 'apps\api\requirements.txt')
if ($LASTEXITCODE -ne 0) {
    Write-ERR "Ошибка pip install. Удалите папку .venv и запустите снова."
    Read-Host "`n  Нажмите Enter для выхода"
    exit 1
}
Write-Host ""

# ── .env.local ───────────────────────────────────────────────────
$envLocal   = Join-Path $ROOT 'apps\web\.env.local'
$envExample = Join-Path $ROOT '.env.example'
if (-not (Test-Path $envLocal) -and (Test-Path $envExample)) {
    Copy-Item $envExample $envLocal
    Write-Host "  Создан apps\web\.env.local из .env.example"
    Write-Host ""
}

# ── API Backend ──────────────────────────────────────────────────
Write-Host "  Запуск API backend (uvicorn)..."
$apiCmd = "& { `$host.UI.RawUI.WindowTitle = 'RAG — API Backend'; Set-Location '$ROOT'; & '.venv\Scripts\python.exe' -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 }"
Start-Process powershell -ArgumentList @(
    '-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $apiCmd
) -WorkingDirectory $ROOT

Write-Host "  Ожидание запуска API (3 сек)..."
Start-Sleep -Seconds 3

# ── Зависимости frontend (при необходимости) ─────────────────────
$webDir = Join-Path $ROOT 'apps\web'
if (-not (Test-Path (Join-Path $webDir 'node_modules'))) {
    Write-Host "  Установка frontend-зависимостей (npm install)..."
    Push-Location $webDir
    npm install --no-fund --no-audit
    $npmExit = $LASTEXITCODE
    Pop-Location
    if ($npmExit -ne 0) {
        Write-ERR "npm install завершился с ошибкой."
        Read-Host "`n  Нажмите Enter для выхода"
        exit 1
    }
    Write-Host ""
}

# ── Web Frontend ─────────────────────────────────────────────────
Write-Host "  Запуск Web frontend (npm run dev)..."
$webCmd = "& { `$host.UI.RawUI.WindowTitle = 'RAG — Web Frontend'; Set-Location '$webDir'; npm run dev }"
Start-Process powershell -ArgumentList @(
    '-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', $webCmd
) -WorkingDirectory $webDir

# ── Окна с логами ────────────────────────────────────────────────
Write-Host "  Ожидание инициализации логов (2 сек)..."
Start-Sleep -Seconds 2

$logDir = Join-Path $ROOT 'data\logs\sessions'
Write-Host "  Открытие окна серверного лога (app_*.log)..."
Start-LogWindow 'RAG — Серверный лог' 'app' $logDir

Write-Host "  Открытие окна UI-лога (ui_*.log)..."
Start-LogWindow 'RAG — UI события' 'ui' $logDir

# ── Итог ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ════════════════════════════════════════════" -ForegroundColor Green
Write-Host "    Запущено!" -ForegroundColor Green
Write-Host "    API:  http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "    Web:  http://localhost:3000"  -ForegroundColor Cyan
Write-Host "    Docs: http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "  ════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Открыто 4 окна: API, Web, серверный лог, UI-лог." -ForegroundColor Yellow
Write-Host "  Закройте все окна для полной остановки программы." -ForegroundColor Yellow
Write-Host ""
Read-Host "  Нажмите Enter для выхода из лаунчера"
