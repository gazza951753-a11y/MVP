@echo off
chcp 65001 > nul
title Установка StudyAssist

echo ============================================================
echo   Установка StudyAssist Intel System
echo   Это нужно сделать ОДИН РАЗ
echo ============================================================
echo.

:: Проверяем что Python установлен
python --version > nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ОШИБКА] Python не найден на вашем компьютере!
    echo.
    echo  Сделайте следующее:
    echo  1. Откройте браузер и зайдите на https://python.org/downloads
    echo  2. Нажмите большую жёлтую кнопку "Download Python 3.11"
    echo  3. Запустите скачанный файл
    echo  4. ОБЯЗАТЕЛЬНО поставьте галочку "Add Python to PATH"
    echo  5. Нажмите Install Now
    echo  6. После установки снова запустите этот файл
    echo.
    pause
    exit /b 1
)

echo  [OK] Python найден:
python --version
echo.

:: Переходим в папку с проектом
cd /d C:\69

echo  Устанавливаем все необходимые пакеты...
echo  (это займёт 1-3 минуты, подождите)
echo.

pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo  [ОШИБКА] Что-то пошло не так при установке пакетов.
    echo  Проверьте подключение к интернету и попробуйте снова.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Установка завершена успешно!
echo.
echo   Теперь для запуска программы используйте файл:
echo   ЗАПУСК.bat
echo ============================================================
echo.
pause
