@echo off
setlocal
cd /d "%~dp0\.."

echo === Публикация Junk Cleaner на itch.io ===
echo.

set BUTLER_DIR=%~dp0butler
set BUTLER_EXE=%BUTLER_DIR%\butler.exe

if not exist "%BUTLER_EXE%" (
    echo Скачиваю butler...
    mkdir "%BUTLER_DIR%" 2>nul
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/itchio/butler/releases/download/v15.27.0/butler-windows-amd64.zip' -OutFile '%BUTLER_DIR%\butler.zip'"
    powershell -Command "Expand-Archive -Path '%BUTLER_DIR%\butler.zip' -DestinationPath '%BUTLER_DIR%' -Force"
)

if not exist "%BUTLER_EXE%" (
    echo butler.exe не найден. Скачай вручную: https://itch.io/docs/butler/installing.html
    pause
    exit /b 1
)

echo.
echo Шаг 1: Авторизация (один раз)
echo   %BUTLER_EXE% login
echo.
echo Шаг 2: Создай проект на itch.io (Kind: Tool), URL вида: YOURNAME/junk-cleaner
echo.
echo Шаг 3: Загрузка билда
echo   %BUTLER_EXE% push release\v1.0.2 YOURNAME/junk-cleaner:windows
echo.

set /p USERNAME="Введи свой itch.io username: "
if "%USERNAME%"=="" (
    echo Username не указан.
    pause
    exit /b 1
)

"%BUTLER_EXE%" push release\v1.0.2 %USERNAME%/junk-cleaner:windows
if errorlevel 1 (
    echo.
    echo Если не залогинен, выполни: %BUTLER_EXE% login
    pause
    exit /b 1
)

echo.
echo Готово! Открой https://itch.io/dashboard и сделай страницу Public.
pause
