@echo off
REM Обновляет кэш иконок Windows, если exe показывает старую картинку
echo Обновляю кэш иконок Windows...
ie4uinit.exe -show >nul 2>&1
taskkill /f /im explorer.exe >nul 2>&1
timeout /t 2 /nobreak >nul
if exist "%localappdata%\IconCache.db" del /f /q "%localappdata%\IconCache.db"
if exist "%localappdata%\Microsoft\Windows\Explorer\iconcache_*.db" del /f /q "%localappdata%\Microsoft\Windows\Explorer\iconcache_*.db"
start explorer.exe
echo Готово. Проверь иконку JunkCleaner на рабочем столе.
