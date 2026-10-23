@echo off
rem Run this once on YOUR (the creator's) PC. Copies of the Jarvis folder on other PCs will then know they're guests.
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
    echo Run setup.bat first.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
python jarvis.py --mark-creator
pause
