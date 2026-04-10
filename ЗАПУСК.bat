@echo off
title StudyAssist
cd /d C:\69
uvicorn --version > /dev/null 2>&1
if errorlevel 1 (
    echo ERROR: Run USTANOVKA.bat first!
    pause
    exit /b 1
)
echo StudyAssist starting...
echo Open browser: http://localhost:8000
echo Close this window to stop.
echo.
start /b cmd /c "timeout /t 3 /nobreak > /dev/null && start http://localhost:8000"
uvicorn app.main:app --host 127.0.0.1 --port 8000
