@echo off
title Tea Terminal - START
echo [1/2] Initializing Background Service...
cd /d "%~dp0..\service"
.\TeaService.exe start

echo [2/2] Launching Interface...
timeout /t 2 >nul
start http://127.0.0.1:5000

echo.
echo SERVICE ACTIVE
pause