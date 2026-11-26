@echo off
setlocal
set "APP_ROOT=E:\Projects\PDFStudio\app"
powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_ROOT%\scripts\stop_all.ps1"
exit /b %ERRORLEVEL%
