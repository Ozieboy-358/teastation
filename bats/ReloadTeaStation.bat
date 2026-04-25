@echo off
title Tea Terminal - RELOAD
echo [!] Terminating Background Service...
cd /d "%~dp0..\service"
.\TeaService.exe stop

echo [!] Initializing Background Service...
timeout /t 2 >nul
.\TeaService.exe start

echo.
echo SERVICE RELOADED
timeout /t 3