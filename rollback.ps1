#Requires -Version 5.1
<#
.SYNOPSIS
    Откат Local RAG Assistant до базового состояния.

.DESCRIPTION
    Удаляет все пользовательские данные и сбрасывает конфигурацию:
      • data\docs       — загруженные документы
      • data\notebooks  — базы данных и индексы ноутбуков
      • data\parsing    — промежуточные артефакты парсинга
      • apps\web\.env.local — конфиг фронтенда (сброс из .env.example)

    Файлы логов (data\logs\sessions\) НЕ удаляются.
    Исходный код и зависимости (.venv, node_modules) НЕ затрагиваются.

    После отката перезапустите программу через run.ps1.
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

$ROOT = $PSScriptRoot

# ════════════════════════════════════════════════════════════════
#  ОСНОВНАЯ ЛОГИКА
# ════════════════════════════════════════════════════════════════
Clear-Host
Write-Host ""
Write-Host "  ╔════════════════════════════════════════════╗" -ForegroundColor Yellow
Write-Host "  ║   Local RAG Assistant — Rollback           ║" -ForegroundColor Yellow
Write-Host "  ╚════════════════════════════════════════════╝" -ForegroundColor Yellow
Write-Host ""
Write-Host "  ВНИМАНИЕ: будут удалены все ноутбуки, загруженные документы" -ForegroundColor Red
Write-Host "  и поисковые индексы. Файлы логов сохранятся." -ForegroundColor Red
Write-Host "  Конфигурация .env.local будет сброшена до .env.example." -ForegroundColor Red
Write-Host ""

# ── Подтверждение ────────────────────────────────────────────────
$answer = Read-Host "  Продолжить? Введите ДА для подтверждения"
if ($answer -ne 'ДА' -and $answer -ne 'да' -and $answer -ne 'Да') {
    Write-Host ""
    Write-Host "  Отменено. Данные не изменены." -ForegroundColor Cyan
    Write-Host ""
    Read-Host "  Нажмите Enter для выхода"
    exit 0
}

Set-Location $ROOT
Write-Host ""

# ── Удаление пользовательских данных ────────────────────────────
$targets = @(
    [PSCustomObject]@{ Path = 'data\docs';      Desc = 'Загруженные документы' }
    [PSCustomObject]@{ Path = 'data\notebooks'; Desc = 'Базы данных ноутбуков' }
    [PSCustomObject]@{ Path = 'data\parsing';   Desc = 'Артефакты парсинга'    }
)

Write-Host "  Удаление пользовательских данных..." -ForegroundColor Cyan

foreach ($t in $targets) {
    $full = Join-Path $ROOT $t.Path
    if (Test-Path $full) {
        Remove-Item $full -Recurse -Force
        Write-Host "  [OK] Удалено: $($t.Path)  ($($t.Desc))" -ForegroundColor Green
    } else {
        Write-Host "  [--] Не найдено (пропущено): $($t.Path)" -ForegroundColor DarkGray
    }
}

# ── Сброс .env.local ─────────────────────────────────────────────
Write-Host ""
Write-Host "  Сброс конфигурации фронтенда..." -ForegroundColor Cyan

$envExample = Join-Path $ROOT '.env.example'
$envLocal   = Join-Path $ROOT 'apps\web\.env.local'

if (Test-Path $envExample) {
    Copy-Item $envExample $envLocal -Force
    Write-Host "  [OK] apps\web\.env.local сброшен из .env.example" -ForegroundColor Green
} else {
    Write-Host "  [!]  .env.example не найден — .env.local не изменён." -ForegroundColor Red
}

# ── Итог ─────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ════════════════════════════════════════════" -ForegroundColor Green
Write-Host "    Откат выполнен успешно!" -ForegroundColor Green
Write-Host "    Для возобновления работы запустите run.ps1" -ForegroundColor Cyan
Write-Host "  ════════════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Read-Host "  Нажмите Enter для выхода"
