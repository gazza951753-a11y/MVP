@echo off
title StudyAssist Setup
echo =============================================
echo   StudyAssist - One-time setup
echo =============================================
echo.
python --version > /dev/null 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Go to https://python.org and download Python 3.11
    echo During install: check the box Add Python to PATH
    pause
    exit /b 1
)
echo Python found:
python --version
echo.
echo Installing packages (1-3 min)...
cd /d C:\69
pip install -r requirements.txt
if errorlevel 1 (
    echo Install failed. Check internet connection.
    pause
    exit /b 1
)
echo.
echo Done! Now run ZAPUSK.bat
pause
