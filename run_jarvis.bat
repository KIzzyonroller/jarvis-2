@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
    echo Run setup.bat first.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
python jarvis.py %*
rem exit code 3 = he restarted himself after an update; the new window is already open
if %ERRORLEVEL% EQU 3 exit
pause
