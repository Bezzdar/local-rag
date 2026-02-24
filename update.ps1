#Requires -Version 5.1
<#
.SYNOPSIS
    Обновление Local RAG Assistant с GitHub.

.DESCRIPTION
    Шаги:
      [1/4] git pull --rebase
      [2/4] Обновление Python-зависимостей (pip)
      [3/4] Обновление Node-зависимостей (npm)
      [4/4] Очистка кэша Next.js (.next)
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

$ROOT = $PSScriptRoot

# ── Вывод ────────────────────────────────────────────────────────
function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "  $msg" -ForegroundColor Cyan
}
function Write-OK([string]$msg)  { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-ERR([string]$msg) { Write-Host "  [!]  $msg" -ForegroundColor Red   }

# ── Проверка Node.js ─────────────────────────────────────────────
function Confirm-Node {
    $node = $null

    # 1) Ищем в PATH
    try {
        $null = node --version 2>$null
        $node = 'node'
    } catch {}

    # 2) Стандартные папки установки
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
        Write-Host "       При установке отметьте «Add to PATH», затем перезапустите скрипт."
        return $null
    }

    $ver = (& $node --version 2>&1).Trim()
    if ($ver -match '^v(\d+)\.(\d+)') {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]

        if ($major -eq 19 -or $major -eq 21) {
            Write-ERR "Node.js $ver — нечётная (не-LTS) версия, не поддерживается."
            Write-Host "       Установите Node.js 22 LTS или 20 LTS."
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
        Write-Host "       При установке отметьте «Add Python to PATH»."
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

# ════════════════════════════════════════════════════════════════
#  ОСНОВНАЯ ЛОГИКА
# ════════════════════════════════════════════════════════════════
Clear-Host
Write-Host ""
Write-Host "  ╔════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "  ║       Local RAG Assistant — Update         ║" -ForegroundColor Yellow
Write-Host "  ╚════════════════════════════════════════════╝" -ForegroundColor Yellow

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

# [1/4] git pull --rebase
Write-Step "[1/4] git pull --rebase..."
git pull --rebase
if ($LASTEXITCODE -ne 0) {
    Write-ERR "git pull завершился с ошибкой. Проверьте статус репозитория."
    Read-Host "`n  Нажмите Enter для выхода"
    exit 1
}

# [2/4] pip
Write-Step "[2/4] Обновление backend-зависимостей (pip)..."
$venvPy = Join-Path $ROOT '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Write-Host "  Создание виртуального окружения .venv..."
    & $pyExe -m venv (Join-Path $ROOT '.venv')
    if ($LASTEXITCODE -ne 0) {
        Write-ERR "Не удалось создать .venv."
        Read-Host "`n  Нажмите Enter для выхода"
        exit 1
    }
}
& $venvPy -m pip install -q --upgrade pip
& $venvPy -m pip install -q -r (Join-Path $ROOT 'apps\api\requirements.txt')
if ($LASTEXITCODE -ne 0) {
    Write-ERR "pip install завершился с ошибкой."
    Read-Host "`n  Нажмите Enter для выхода"
    exit 1
}
Write-OK "Backend-зависимости обновлены."

# [3/4] npm install
Write-Step "[3/4] Обновление frontend-зависимостей (npm)..."
$webDir = Join-Path $ROOT 'apps\web'
$nm     = Join-Path $webDir 'node_modules'
if (Test-Path $nm) {
    Write-Host "  Удаление node_modules для чистой установки..."
    Remove-Item $nm -Recurse -Force
}
Push-Location $webDir
npm install --no-fund --no-audit
$npmExit = $LASTEXITCODE
Pop-Location
if ($npmExit -ne 0) {
    Write-ERR "npm install завершился с ошибкой."
    Read-Host "`n  Нажмите Enter для выхода"
    exit 1
}
Write-OK "Frontend-зависимости обновлены."

# [4/4] Очистка .next
Write-Step "[4/4] Очистка кэша Next.js (.next)..."
foreach ($p in @((Join-Path $ROOT '.next'), (Join-Path $webDir '.next'))) {
    if (Test-Path $p) {
        Remove-Item $p -Recurse -Force
        Write-Host "  Удалено: $p"
    }
}
Write-OK "Кэш Next.js очищен."

Write-Host ""
Write-Host "  ════════════════════════════════════════════" -ForegroundColor Green
Write-Host "    Обновление успешно завершено!" -ForegroundColor Green
Write-Host "  ════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Read-Host "  Нажмите Enter для выхода"
