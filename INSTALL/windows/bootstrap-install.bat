@echo off
setlocal

set SCRIPT_DIR=%~dp0
set APP_ROOT=%SCRIPT_DIR%..\..
set LOG_DIR=%APP_ROOT%\data\logs
set LOG_FILE=%LOG_DIR%\installer-bootstrap.log

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo [%date% %time%] Starting installer bootstrap > "%LOG_FILE%"
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install.ps1" >> "%LOG_FILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%
echo [%date% %time%] Installer bootstrap exit code: %EXIT_CODE% >> "%LOG_FILE%"

exit /b %EXIT_CODE%
