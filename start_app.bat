@echo off
setlocal
cd /d "%~dp0"

echo === Запуск RAG приложения в браузере ===

if not exist venv\Scripts\activate.bat (
    echo [ERROR] venv не найден. Сначала выполните setup_venv.bat
    exit /b 1
)

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Не удалось активировать venv.
    exit /b 1
)

start "" cmd /c "timeout /t 3 /nobreak >nul && start \"\" http://localhost:8501"
streamlit run streamlit_app.py --server.headless true --server.port 8501

endlocal
