@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul 2>&1
title Local RAG Assistant — Launcher

:: ----------------------------------------------------------------
:: Корневая директория репозитория (папка, где находится этот файл)
:: ----------------------------------------------------------------
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

:: Временные файлы для хранения PID запущенных окон с логами
set "TMPDIR=%TEMP%\rag_launcher"
if not exist "%TMPDIR%" mkdir "%TMPDIR%"

set "MODE_FILE=%TMPDIR%\window_mode.txt"
set "API_PID_FILE=%TMPDIR%\api.pid"
set "WEB_PID_FILE=%TMPDIR%\web.pid"
set "LOG_APP_PID_FILE=%TMPDIR%\log_app.pid"
set "LOG_UI_PID_FILE=%TMPDIR%\log_ui.pid"

:: Загрузить сохранённый режим окон (visible / hidden)
set "WINDOW_MODE=visible"
if exist "%MODE_FILE%" (
    set /p WINDOW_MODE=<"%MODE_FILE%"
)

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
if exist ".next" rmdir /s /q ".next"

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

:: Показать текущий режим окон
echo  Режим окон: !WINDOW_MODE!
echo  (изменить режим можно в меню Логи → R)
echo.

:: Запустить API (uvicorn)
echo  Запуск API backend (uvicorn)...
if /i "!WINDOW_MODE!"=="hidden" (
    powershell -NoProfile -Command ^
      "$p = Start-Process powershell ^
        -ArgumentList '-NoExit','-Command','Set-Location -LiteralPath ''%ROOT%''; .\.venv\Scripts\Activate.ps1; uvicorn apps.api.main:app --host 127.0.0.1 --port 8000' ^
        -WindowStyle Hidden -PassThru; ^
        $p.Id | Out-File -Encoding ascii '%API_PID_FILE%'"
) else (
    powershell -NoProfile -Command ^
      "$p = Start-Process powershell ^
        -ArgumentList '-NoExit','-Command','Set-Location -LiteralPath ''%ROOT%''; .\.venv\Scripts\Activate.ps1; uvicorn apps.api.main:app --host 127.0.0.1 --port 8000' ^
        -PassThru; ^
        $p.Id | Out-File -Encoding ascii '%API_PID_FILE%'"
)

:: Дать API время на старт
timeout /t 3 /nobreak > nul

:: Запустить Web (npm run dev)
echo  Запуск Web frontend (npm run dev)...
if /i "!WINDOW_MODE!"=="hidden" (
    powershell -NoProfile -Command ^
      "$p = Start-Process powershell ^
        -ArgumentList '-NoExit','-Command','Set-Location -LiteralPath ''%ROOT%\apps\web''; npm run dev' ^
        -WindowStyle Hidden -PassThru; ^
        $p.Id | Out-File -Encoding ascii '%WEB_PID_FILE%'"
) else (
    powershell -NoProfile -Command ^
      "$p = Start-Process powershell ^
        -ArgumentList '-NoExit','-Command','Set-Location -LiteralPath ''%ROOT%\apps\web''; npm run dev' ^
        -PassThru; ^
        $p.Id | Out-File -Encoding ascii '%WEB_PID_FILE%'"
)

echo.
echo  Запущено!
echo    API:  http://127.0.0.1:8000
echo    Web:  http://localhost:3000
echo    Docs: http://127.0.0.1:8000/docs
echo.
if /i "!WINDOW_MODE!"=="hidden" (
    echo  Процессы работают в скрытом режиме.
    echo  Для просмотра логов используйте меню: Логи ^(4^)
)
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

:: Проверить состояние окон с логами
call :CHECK_PID "%LOG_APP_PID_FILE%" STAT_APP
call :CHECK_PID "%LOG_UI_PID_FILE%"  STAT_UI

echo.
echo  ╔════════════════════════════════════════════╗
echo  ║            Логи — подменю                  ║
echo  ╚════════════════════════════════════════════╝
echo.
echo    A.  Серверный лог  (app_*.log)   [!STAT_APP!]
echo    B.  UI-события     (ui_*.log)    [!STAT_UI!]
echo    C.  Открыть папку с логами
echo    R.  Режим запуска процессов:     [!WINDOW_MODE!]
echo    0.  Назад
echo.
choice /c ABCR0 /n /m "  Ваш выбор: "
if %errorlevel%==1 goto :TOGGLE_LOG_APP
if %errorlevel%==2 goto :TOGGLE_LOG_UI
if %errorlevel%==3 goto :OPEN_LOGS_FOLDER
if %errorlevel%==4 goto :TOGGLE_MODE
if %errorlevel%==5 goto :MAIN_MENU
goto :LOGS_MENU


:TOGGLE_LOG_APP
call :TOGGLE_LOG_WINDOW "%LOG_APP_PID_FILE%" "RAG — Серверный лог" "app"
goto :LOGS_MENU

:TOGGLE_LOG_UI
call :TOGGLE_LOG_WINDOW "%LOG_UI_PID_FILE%" "RAG — UI события" "ui"
goto :LOGS_MENU

:OPEN_LOGS_FOLDER
set "LOGS_FOLDER=%ROOT%\data\logs\sessions"
if not exist "%LOGS_FOLDER%" (
    echo.
    echo  Папка с логами не найдена. Запустите программу хотя бы один раз.
    timeout /t 2 /nobreak > nul
) else (
    start "" explorer "%LOGS_FOLDER%"
)
goto :LOGS_MENU

:TOGGLE_MODE
if /i "!WINDOW_MODE!"=="visible" (
    set "WINDOW_MODE=hidden"
) else (
    set "WINDOW_MODE=visible"
)
echo !WINDOW_MODE!> "%MODE_FILE%"
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

:: CHECK_PID <pid_file> <out_var>
:: Проверяет, работает ли процесс из pid-файла.
:: Устанавливает <out_var> в ОТКРЫТ или ЗАКРЫТ.
:CHECK_PID
set "%~2=ЗАКРЫТ"
if not exist "%~1" exit /b 0
set /p _PID=<"%~1"
if "!_PID!"=="" exit /b 0
:: Проверка через tasklist
tasklist /fi "PID eq !_PID!" 2>nul | findstr /i "!_PID!" > nul
if %errorlevel%==0 (
    set "%~2=ОТКРЫТ"
) else (
    del /q "%~1" > nul 2>&1
)
exit /b 0


:: TOGGLE_LOG_WINDOW <pid_file> <title> <prefix>
:: Открывает или закрывает окно просмотра лога.
:TOGGLE_LOG_WINDOW
setlocal
set "PID_F=%~1"
set "WIN_TITLE=%~2"
set "LOG_PREFIX=%~3"

call :CHECK_PID "%PID_F%" _STATUS
if /i "!_STATUS!"=="ОТКРЫТ" (
    :: Закрыть окно
    set /p _PID=<"%PID_F%"
    taskkill /pid !_PID! /f > nul 2>&1
    del /q "%PID_F%" > nul 2>&1
    echo.
    echo  Окно "%WIN_TITLE%" закрыто.
    timeout /t 1 /nobreak > nul
) else (
    :: Открыть окно с tail лог-файла
    set "LOG_DIR=%ROOT%\data\logs\sessions"
    if not exist "!LOG_DIR!" (
        echo.
        echo  Логи не найдены. Запустите программу хотя бы один раз.
        timeout /t 2 /nobreak > nul
        goto :TOGGLE_LOG_WINDOW_END
    )
    :: Найти последний файл с нужным префиксом
    powershell -NoProfile -Command ^
      "$f = Get-ChildItem '%LOG_DIR%\%LOG_PREFIX%_*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1; ^
       if (!$f) { Write-Host 'Файл лога не найден'; exit 1 }; ^
       $p = Start-Process cmd -ArgumentList '/k','title %WIN_TITLE% & powershell -NoProfile -Command Get-Content -Path '''+$f.FullName+''' -Wait -Tail 50' -PassThru; ^
       $p.Id | Out-File -Encoding ascii '%PID_F%'"
    echo.
    echo  Окно "%WIN_TITLE%" открыто.
    timeout /t 1 /nobreak > nul
)
:TOGGLE_LOG_WINDOW_END
endlocal
exit /b 0
