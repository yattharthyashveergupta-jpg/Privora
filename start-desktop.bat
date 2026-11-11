@echo off
title Privora Desktop Launcher
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-desktop.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Privora launcher encountered an error or exited with code %ERRORLEVEL%.
    pause
)
