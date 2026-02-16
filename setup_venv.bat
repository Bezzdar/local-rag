@echo off
setlocal
cd /d "%~dp0"

echo === Создание/обновление виртуального окружения (./venv) ===

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python не найден в PATH. Установите Python 3.10+ и повторите.
    exit /b 1
)

if not exist venv (
    echo [INFO] venv не найден, создаю...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Не удалось создать venv.
        exit /b 1
    )
) else (
    echo [INFO] venv уже существует, использую текущий.
)

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Не удалось активировать venv.
    exit /b 1
)

python -m pip install --upgrade pip
if errorlevel 1 (
    echo [ERROR] Не удалось обновить pip.
    exit /b 1
)

if not exist requirements.txt (
    echo [ERROR] Файл requirements.txt не найден в корне проекта.
    exit /b 1
)

pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Не удалось установить зависимости.
    exit /b 1
)

echo [OK] Виртуальная среда готова, зависимости установлены.
endlocal
