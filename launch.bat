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
set "_CHOICE=!errorlevel!"
if "!_CHOICE!"=="1" goto :UPDATE
if "!_CHOICE!"=="2" goto :START
if "!_CHOICE!"=="3" goto :RESET
if "!_CHOICE!"=="4" goto :LOGS_MENU
if "!_CHOICE!"=="5" goto :EXIT
goto :MAIN_MENU


:: ================================================================
::  ПРОВЕРКА NODE.JS
:: ================================================================
:CHECK_NODE
set "_NODE_EXE="

:: 1) Попытка найти node в PATH
for /f "tokens=*" %%v in ('node --version 2^>nul') do set "_NODE_EXE=node"

:: 2) Если не нашли — ищем в стандартных папках установки
if not defined _NODE_EXE (
    for %%p in (
        "%ProgramFiles%\nodejs\node.exe"
        "%ProgramFiles(x86)%\nodejs\node.exe"
        "%LOCALAPPDATA%\Programs\nodejs\node.exe"
    ) do (
        if exist %%p (
            set "_NODE_EXE=%%~p"
            goto :_node_found
        )
    )
)

:_node_found
if not defined _NODE_EXE (
    echo.
    echo  [!] Node.js не обнаружен ни в PATH, ни в стандартных папках!
    echo.
    echo      Решение:
    echo        1. Установите Node.js 22 LTS или 20 LTS:
    echo           https://nodejs.org/
    echo        2. При установке отметьте «Add to PATH»
    echo        3. ЗАКРОЙТЕ и откройте это окно заново после установки
    echo.
    pause
    exit /b 1
)

:: Получаем версию
set "_NODE_VER="
set "_NODE_MAJOR="
set "_NODE_MINOR="
for /f "tokens=*" %%v in ('"%_NODE_EXE%" --version 2^>nul') do set "_NODE_VER=%%v"
for /f "tokens=1,2 delims=." %%a in ("!_NODE_VER:~1!") do (
    set "_NODE_MAJOR=%%a"
    set "_NODE_MINOR=%%b"
)

if not defined _NODE_VER (
    echo.
    echo  [!] Не удалось определить версию Node.js через "!_NODE_EXE!".
    echo      Закройте и откройте это окно заново.
    echo.
    pause
    exit /b 1
)

if not defined _NODE_MAJOR (
    echo.
    echo  [!] Невозможно разобрать версию Node.js: !_NODE_VER!
    echo.
    pause
    exit /b 1
)

:: Нечётные (не-LTS) версии
if "!_NODE_MAJOR!"=="19" (
    echo  [!] Node.js !_NODE_VER! — нечётная версия, не поддерживается.
    echo      Установите Node.js 22 LTS или 20 LTS: https://nodejs.org/
    set "_NODE_VER=" & set "_NODE_MAJOR=" & set "_NODE_MINOR=" & set "_NODE_EXE="
    pause
    exit /b 1
)
if "!_NODE_MAJOR!"=="21" (
    echo  [!] Node.js !_NODE_VER! — нечётная версия, не поддерживается.
    echo      Установите Node.js 22 LTS или 20 LTS: https://nodejs.org/
    set "_NODE_VER=" & set "_NODE_MAJOR=" & set "_NODE_MINOR=" & set "_NODE_EXE="
    pause
    exit /b 1
)

:: Минимальная версия — 20
if !_NODE_MAJOR! LSS 20 (
    echo  [!] Node.js !_NODE_VER! устарел. Требуется 20 LTS+ или 22 LTS.
    set "_NODE_EXE=" & set "_NODE_VER=" & set "_NODE_MAJOR=" & set "_NODE_MINOR="
    pause
    exit /b 1
)

:: Для Node.js 20: минимум 20.9.0
if "!_NODE_MAJOR!"=="20" if !_NODE_MINOR! LSS 9 (
    echo  [!] Node.js !_NODE_VER! — слишком старая сборка 20.
    echo      Требуется 20.9.0+ или Node.js 22 LTS.
    set "_NODE_EXE=" & set "_NODE_VER=" & set "_NODE_MAJOR=" & set "_NODE_MINOR="
    pause
    exit /b 1
)

echo  [OK] Node.js !_NODE_VER! (путь: !_NODE_EXE!)
set "_NODE_MAJOR=" & set "_NODE_MINOR="
exit /b 0


:: ================================================================
::  ПРОВЕРКА PYTHON
:: ================================================================
:CHECK_PYTHON
set "_PY_EXE="
for /f "tokens=*" %%v in ('python --version 2^>nul') do set "_PY_EXE=python"
if not defined _PY_EXE (
    for /f "tokens=*" %%v in ('python3 --version 2^>nul') do set "_PY_EXE=python3"
)
if not defined _PY_EXE (
    echo.
    echo  [!] Python не обнаружен!
    echo      Установите Python 3.11+ с https://www.python.org/
    echo      При установке отметьте «Add Python to PATH».
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('"!_PY_EXE!" --version 2^>^&1') do set "_PY_VER=%%v"
for /f "tokens=1 delims=." %%a in ("!_PY_VER!") do set "_PY_MAJOR=%%a"
if not defined _PY_MAJOR (
    echo  [!] Невозможно разобрать версию Python: !_PY_VER!
    pause
    exit /b 1
)
if !_PY_MAJOR! LSS 3 (
    echo  [!] Обнаружен Python !_PY_VER!. Требуется Python 3.11+.
    set "_PY_EXE=" & set "_PY_VER=" & set "_PY_MAJOR="
    pause
    exit /b 1
)
echo  [OK] Python !_PY_VER!
set "_PY_VER=" & set "_PY_MAJOR="
exit /b 0


:: ================================================================
::  1) ОБНОВЛЕНИЕ С GITHUB
:: ================================================================
:UPDATE
cls
echo.
echo  ── Обновление с GitHub ──────────────────────────────────────
echo.
cd /d "%ROOT%"

call :CHECK_NODE
if !errorlevel! neq 0 goto :MAIN_MENU

call :CHECK_PYTHON
if !errorlevel! neq 0 goto :MAIN_MENU

echo.
echo  [1/4] git pull --rebase...
git pull --rebase
if !errorlevel! neq 0 (
    echo.
    echo  [!] git pull завершился с ошибкой.
    echo.
    pause
    goto :MAIN_MENU
)

echo.
echo  [2/4] Обновление backend-зависимостей (pip)...
if not exist ".venv\Scripts\python.exe" (
    echo  Создание виртуального окружения...
    "!_PY_EXE!" -m venv .venv
)
call ".venv\Scripts\python.exe" -m pip install -q --upgrade pip
call ".venv\Scripts\python.exe" -m pip install -q -r apps\api\requirements.txt
if !errorlevel! neq 0 (
    echo  [!] pip install завершился с ошибкой.
    pause
    goto :MAIN_MENU
)

echo.
echo  [3/4] Обновление frontend-зависимостей (npm)...
cd /d "%ROOT%\apps\web"
if exist "node_modules" rmdir /s /q "node_modules"
call npm install --no-fund --no-audit
if !errorlevel! neq 0 (
    echo  [!] npm install завершился с ошибкой.
    cd /d "%ROOT%"
    pause
    goto :MAIN_MENU
)

echo.
echo  [4/4] Очистка кэша Next.js (.next)...
if exist "%ROOT%\.next" rmdir /s /q "%ROOT%\.next"
if exist "%ROOT%\apps\web\.next" rmdir /s /q "%ROOT%\apps\web\.next"

cd /d "%ROOT%"
echo.
echo  Обновление успешно завершено!
echo.
set "_NODE_EXE=" & set "_PY_EXE="
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

call :CHECK_NODE
if !errorlevel! neq 0 goto :MAIN_MENU

call :CHECK_PYTHON
if !errorlevel! neq 0 goto :MAIN_MENU

:: ---------- venv ----------
if not exist ".venv\Scripts\python.exe" (
    echo  Создание виртуального окружения Python...
    "!_PY_EXE!" -m venv .venv
    if !errorlevel! neq 0 (
        echo  [!] Не удалось создать .venv
        pause
        goto :MAIN_MENU
    )
    echo.
)

:: ---------- pip ----------
echo  Проверка зависимостей backend...
call ".venv\Scripts\python.exe" -m pip install -q --upgrade pip
call ".venv\Scripts\python.exe" -m pip install -q -r apps\api\requirements.txt
if !errorlevel! neq 0 (
    echo.
    echo  [!] Ошибка при установке Python-зависимостей.
    echo      Попробуйте: удалите папку .venv и запустите снова.
    echo.
    pause
    goto :MAIN_MENU
)
echo.

:: ---------- .env.local ----------
if not exist "apps\web\.env.local" (
    if exist ".env.example" (
        echo  Создание apps\web\.env.local из .env.example...
        copy /y ".env.example" "apps\web\.env.local" > nul
        echo.
    )
)

:: ---------- API backend ----------
echo  Запуск API backend (uvicorn)...
start "RAG — API Backend" cmd /k ""cd /d "%ROOT%" && ".venv\Scripts\python.exe" -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000""

:: Дать API время на старт
echo  Ожидание запуска API (3 сек)...
timeout /t 3 /nobreak > nul

:: ---------- npm install ----------
if not exist "%ROOT%\apps\web\node_modules\.bin\next.cmd" (
    echo  Установка frontend-зависимостей (npm install)...
    cd /d "%ROOT%\apps\web"
    call npm install --no-fund --no-audit
    if !errorlevel! neq 0 (
        echo  [!] npm install завершился с ошибкой.
        cd /d "%ROOT%"
        pause
        goto :MAIN_MENU
    )
    cd /d "%ROOT%"
    echo.
)

:: ---------- Web frontend ----------
echo  Запуск Web frontend (npm run dev)...
start "RAG — Web Frontend" cmd /k ""cd /d "%ROOT%\apps\web" && call npm run dev""

echo.
echo  ════════════════════════════════════════════
echo    Запущено!
echo    API:  http://127.0.0.1:8000
echo    Web:  http://localhost:3000
echo    Docs: http://127.0.0.1:8000/docs
echo  ════════════════════════════════════════════
echo.
echo  НЕ закрывайте окна «RAG — API Backend» и «RAG — Web Frontend».
echo.
set "_NODE_EXE=" & set "_PY_EXE="
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
set "_CHOICE=!errorlevel!"
if "!_CHOICE!"=="2" (
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
if exist "data\citations" rmdir /s /q "data\citations"
if exist "data\notes"     rmdir /s /q "data\notes"
if exist "data\store.db"  del /f /q "data\store.db"

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
set "_CHOICE=!errorlevel!"
if "!_CHOICE!"=="1" goto :OPEN_LOG_APP
if "!_CHOICE!"=="2" goto :OPEN_LOG_UI
if "!_CHOICE!"=="3" goto :OPEN_LOGS_FOLDER
if "!_CHOICE!"=="4" goto :MAIN_MENU
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

start "%WIN_TITLE%" powershell -NoExit -NoProfile -ExecutionPolicy Bypass -Command "$f = Get-ChildItem '%LOG_DIR%\%LOG_PREFIX%_*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if (-not $f) { Write-Host 'Файл лога не найден.' } else { Get-Content $f.FullName -Wait -Tail 50 }"

endlocal
exit /b 0
