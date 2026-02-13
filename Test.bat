@echo off
REM ================================================
REM  TestConnection.bat – проверка MySQL в контейнере
REM ================================================

set CONTAINER=ragflow-mysql
set DB_USER=root
set DB_PASS=infini_rag_flow

echo Проверяем доступность MySQL в контейнере %CONTAINER%...
docker exec -i %CONTAINER% mysqladmin -u%DB_USER% -p%DB_PASS% ping

echo.
pause
