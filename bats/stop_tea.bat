@echo off
title Tea Terminal - STOP
echo [!] Terminating Background Service...
cd /d "%~dp0..\service"
.\TeaService.exe stop

echo.
echo SERVICE TERMINATED
timeout /t 3