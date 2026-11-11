@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo   Privora -- Private Document Intelligence (Dev Stack)
echo ==========================================================
echo.

:: Detect Python executable
where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PY_CMD=py"
) else (
    set "PY_CMD=python"
)

:: Start Backend API server
if exist "backend\.venv\Scripts\activate.bat" (
    start "Privora API" cmd /k "cd /d "%~dp0backend" && call .venv\Scripts\activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
) else (
    start "Privora API" cmd /k "cd /d "%~dp0backend" && %PY_CMD% -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
)

:: Start Frontend dev server
start "Privora Web" cmd /k "cd /d "%~dp0" && npm run dev"
