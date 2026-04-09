@echo off
chcp 65001 > nul
title StudyAssist Intel System

echo ============================================================
echo   StudyAssist Intel System запускается...
echo ============================================================
echo.

:: Переходим в папку с проектом
cd /d C:\69

:: Указываем базу данных — файл studyassist.db прямо в папке C:\69
:: (создаётся автоматически при первом запуске)
set DATABASE_URL=sqlite:///studyassist.db
set APP_ENV=desktop
set PROMETHEUS_ENABLED=false
set LOG_LEVEL=WARNING

:: Проверяем что uvicorn установлен
uvicorn --version > nul 2>&1
if errorlevel 1 (
    echo  [ОШИБКА] Пакеты не установлены!
    echo  Сначала запустите файл УСТАНОВКА.bat
    echo.
    pause
    exit /b 1
)

echo  База данных: C:\69\studyassist.db
echo  Адрес в браузере: http://localhost:8000
echo.
echo  Браузер откроется автоматически через 3 секунды...
echo.
echo  Чтобы ОСТАНОВИТЬ программу — закройте это окно или нажмите Ctrl+C
echo ============================================================
echo.

:: Открываем браузер через 3 секунды в фоне
start /b cmd /c "timeout /t 3 /nobreak > nul && start http://localhost:8000"

:: Запускаем сервер (программа работает пока открыто это окно)
uvicorn app.main:app --host 127.0.0.1 --port 8000
