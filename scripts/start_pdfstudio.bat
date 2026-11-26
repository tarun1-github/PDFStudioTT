@echo off
setlocal
set "APP_ROOT=E:\Projects\PDFStudio\app"
set "LOG_DIR=E:\Projects\PDFStudio\data\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

cd /d "%APP_ROOT%"
echo [%date% %time%] Starting PDF Studio test environment... >> "%LOG_DIR%\startup.log"
powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_ROOT%\scripts\start_all.ps1" >> "%LOG_DIR%\startup.log" 2>&1
exit /b %ERRORLEVEL%
