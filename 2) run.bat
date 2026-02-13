@echo off
REM --- Активировать виртуальное окружение venv ---
call venv\Scripts\activate.bat

REM --- Запустить Streamlit с основным приложением ---
streamlit run streamlit_app.py

pause
