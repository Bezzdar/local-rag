@echo off
cd /d "%~dp0"
echo.
echo === УДАЛЕНИЕ СТАРОГО VENV (если есть) ===
if exist venv (
    rmdir /s /q venv
    echo [OK] Старая venv удалена.
) else (
    echo [OK] venv не обнаружен.
)
echo.

echo === СОЗДАНИЕ НОВОГО VENV ===
python -m venv venv
if errorlevel 1 (
    echo [ОШИБКА] Не удалось создать venv. Проверьте, что установлен Python 3.10+
    pause
    exit /b 1
)
echo [OK] venv создан.
echo.

echo === АКТИВАЦИЯ VENV ===
call venv\Scripts\activate
if errorlevel 1 (
    echo [ОШИБКА] Не удалось активировать venv!
    pause
    exit /b 1
)

echo.
echo === ОБНОВЛЕНИЕ PIP ===
python -m pip install --upgrade pip

echo.
echo === УСТАНОВКА ЗАВИСИМОСТЕЙ ===
pip install -U setuptools
pip install -r requirements.txt
if errorlevel 1 (
    echo [ОШИБКА] Не удалось установить зависимости!
    pause
    exit /b 1
)
echo [OK] Все зависимости установлены.

echo.
echo === ЗАПУСК STREAMLIT ===
streamlit run streamlit_app.py

pause
