@echo off
REM --- Активировать venv ---
call venv\Scripts\activate.bat

REM --- Установить нужные пакеты ---
pip install --upgrade pip
pip install -U setuptools
pip install -r requirements.txt

REM --- Если нужны еще: просто добавляй через пробел ---
REM pip install python-docx pdfminer.six

pause
