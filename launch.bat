@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul 2>&1
title Local RAG Assistant — Launcher

:: ----------------------------------------------------------------
:: Корневая директория репозитория (папка, где находится этот файл)
:: ----------------------------------------------------------------
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

goto :MAIN_MENU


:: ================================================================
::  ГЛАВНОЕ МЕНЮ
:: ================================================================
:MAIN_MENU
cls
echo.
echo  ╔════════════════════════════════════════════╗
echo  ║       Local RAG Assistant — Launcher       ║
echo  ╚════════════════════════════════════════════╝
echo.
echo    1.  Обновление с GitHub
echo    2.  Запустить программу
echo    3.  Откат настроек до базовых
echo    4.  Логи
echo    0.  Выход
echo.
choice /c 12340 /n /m "  Ваш выбор: "
if %errorlevel%==1 goto :UPDATE
if %errorlevel%==2 goto :START
if %errorlevel%==3 goto :RESET
if %errorlevel%==4 goto :LOGS_MENU
if %errorlevel%==5 goto :EXIT
goto :MAIN_MENU


:: ================================================================
::  1) ОБНОВЛЕНИЕ С GITHUB
:: ================================================================
:UPDATE
cls
echo.
echo  ── Обновление с GitHub ──────────────────────────────────────
echo.
cd /d "%ROOT%"

echo  [1/4] git pull --rebase...
git pull --rebase
if %errorlevel% neq 0 (
    echo.
    echo  [!] git pull завершился с ошибкой. Проверьте подключение
    echo      или выполните слияние вручную.
    echo.
    pause
    goto :MAIN_MENU
)

echo.
echo  [2/4] Обновление backend-зависимостей (pip)...
if not exist ".venv\Scripts\python.exe" (
    echo  Создание виртуального окружения...
    python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q --upgrade pip
".venv\Scripts\python.exe" -m pip install -q -r apps\api\requirements.txt
if %errorlevel% neq 0 (
    echo  [!] pip install завершился с ошибкой.
    pause
    goto :MAIN_MENU
)

echo.
echo  [3/4] Обновление frontend-зависимостей (npm)...
cd /d "%ROOT%\apps\web"
npm install --prefer-offline 2>&1
if %errorlevel% neq 0 (
    echo  [!] npm install завершился с ошибкой.
    cd /d "%ROOT%"
    pause
    goto :MAIN_MENU
)

echo.
echo  [4/4] Очистка кэша Next.js (.next)...
if exist "%ROOT%\.next" rmdir /s /q "%ROOT%\.next"

cd /d "%ROOT%"
echo.
echo  Обновление успешно завершено!
echo  Перезапустите программу если она была запущена.
echo.
pause
goto :MAIN_MENU


:: ================================================================
::  2) ЗАПУСК ПРОГРАММЫ
:: ================================================================
:START
cls
echo.
echo  ── Запуск программы ─────────────────────────────────────────
echo.
cd /d "%ROOT%"

:: Создать venv если не существует
if not exist ".venv\Scripts\python.exe" (
    echo  Создание виртуального окружения Python...
    python -m venv .venv
    echo.
)

:: Установить/проверить зависимости backend
echo  Проверка зависимостей backend...
".venv\Scripts\python.exe" -m pip install -q -r apps\api\requirements.txt
echo.

:: Создать .env.local если не существует
if not exist "apps\web\.env.local" (
    echo  Создание apps\web\.env.local из .env.example...
    copy /y ".env.example" "apps\web\.env.local" > nul
    echo.
)

:: Запустить API (uvicorn) — окно останется открытым
echo  Запуск API backend (uvicorn)...
start "RAG — API Backend" powershell -NoExit -NoProfile -Command "Set-Location -LiteralPath '%ROOT%'; .\.venv\Scripts\Activate.ps1; uvicorn apps.api.main:app --host 127.0.0.1 --port 8000"

:: Дать API время на старт
timeout /t 3 /nobreak > nul

:: Запустить Web (npm run dev) — окно останется открытым
echo  Запуск Web frontend (npm run dev)...
start "RAG — Web Frontend" powershell -NoExit -NoProfile -Command "Set-Location -LiteralPath '%ROOT%\apps\web'; npm run dev"

echo.
echo  Запущено!
echo    API:  http://127.0.0.1:8000
echo    Web:  http://localhost:3000
echo    Docs: http://127.0.0.1:8000/docs
echo.
pause
goto :MAIN_MENU


:: ================================================================
::  3) ОТКАТ НАСТРОЕК ДО БАЗОВЫХ
:: ================================================================
:RESET
cls
echo.
echo  ── Откат настроек до базовых ────────────────────────────────
echo.
echo  ВНИМАНИЕ: будут удалены все ноутбуки, загруженные документы
echo  и индексы. Файлы логов сохранятся.
echo  Конфигурация .env.local будет сброшена до .env.example.
echo.
choice /c YN /n /m "  Продолжить? (Y — да, N — отмена): "
if %errorlevel%==2 (
    echo.
    echo  Отменено.
    timeout /t 1 /nobreak > nul
    goto :MAIN_MENU
)

cd /d "%ROOT%"
echo.
echo  Удаление пользовательских данных...
if exist "data\docs"      rmdir /s /q "data\docs"
if exist "data\notebooks" rmdir /s /q "data\notebooks"
if exist "data\parsing"   rmdir /s /q "data\parsing"

echo  Сброс конфигурации frontend...
if exist ".env.example" (
    copy /y ".env.example" "apps\web\.env.local" > nul
    echo  apps\web\.env.local сброшен из .env.example
) else (
    echo  [!] .env.example не найден, .env.local не изменён.
)

echo.
echo  Откат выполнен. Перезапустите программу для применения.
echo.
pause
goto :MAIN_MENU


:: ================================================================
::  4) МЕНЮ ЛОГОВ
:: ================================================================
:LOGS_MENU
cls
echo.
echo  ╔════════════════════════════════════════════╗
echo  ║            Логи — подменю                  ║
echo  ╚════════════════════════════════════════════╝
echo.
echo    A.  Открыть серверный лог  (app_*.log)
echo    B.  Открыть UI-события     (ui_*.log)
echo    C.  Открыть папку с логами
echo    0.  Назад
echo.
choice /c ABC0 /n /m "  Ваш выбор: "
if %errorlevel%==1 goto :OPEN_LOG_APP
if %errorlevel%==2 goto :OPEN_LOG_UI
if %errorlevel%==3 goto :OPEN_LOGS_FOLDER
if %errorlevel%==4 goto :MAIN_MENU
goto :LOGS_MENU

:OPEN_LOG_APP
call :OPEN_LOG_WINDOW "RAG — Серверный лог" "app"
goto :LOGS_MENU

:OPEN_LOG_UI
call :OPEN_LOG_WINDOW "RAG — UI события" "ui"
goto :LOGS_MENU

:OPEN_LOGS_FOLDER
if not exist "%ROOT%\data\logs\sessions" (
    echo.
    echo  Папка с логами не найдена. Запустите программу хотя бы один раз.
    timeout /t 2 /nobreak > nul
) else (
    start "" explorer "%ROOT%\data\logs\sessions"
)
goto :LOGS_MENU


:: ================================================================
::  ВЫХОД
:: ================================================================
:EXIT
cls
echo.
echo  До свидания!
echo.
timeout /t 1 /nobreak > nul
exit /b 0


:: ================================================================
::  ВСПОМОГАТЕЛЬНЫЕ ПОДПРОГРАММЫ
:: ================================================================

:: OPEN_LOG_WINDOW <title> <prefix>
:: Открывает новое окно с хвостом последнего лог-файла.
:OPEN_LOG_WINDOW
setlocal
set "WIN_TITLE=%~1"
set "LOG_PREFIX=%~2"
set "LOG_DIR=%ROOT%\data\logs\sessions"

if not exist "%LOG_DIR%" (
    echo.
    echo  Логи не найдены. Запустите программу хотя бы один раз.
    timeout /t 2 /nobreak > nul
    endlocal
    exit /b 0
)

start "%WIN_TITLE%" powershell -NoExit -NoProfile -Command "$f = Get-ChildItem '%LOG_DIR%\%LOG_PREFIX%_*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if (-not $f) { Write-Host 'Файл лога не найден.' } else { Get-Content $f.FullName -Wait -Tail 50 }"

endlocal
exit /b 0
