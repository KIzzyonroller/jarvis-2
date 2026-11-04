@echo off
setlocal
cd /d "%~dp0"
echo === JARVIS setup ===

if not exist .venv (
    echo Creating virtual environment...
    py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || python -m venv .venv
)
if not exist .venv\Scripts\activate.bat (
    echo.
    echo Couldn't create a Python environment. Install Python 3.11 or 3.12 from python.org
    echo and tick "Add python.exe to PATH" during install, then run this again.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Package install failed. Scroll up for the error.
    pause
    exit /b 1
)

rem One ONNX Runtime only: the DirectML build (processor included), so his voice can use the graphics card
rem once it passes its test. Two builds installed at once fight each other.
pip show onnxruntime-gpu >nul 2>nul && pip uninstall -y onnxruntime-gpu
pip uninstall -y onnxruntime onnxruntime-directml >nul 2>nul
pip install --no-deps --force-reinstall onnxruntime-directml

python download_models.py


if not exist .env (
    copy .env.example .env >nul
    echo.
    echo Opening .env in Notepad. Paste your Anthropic API key, save, close.
    notepad .env
)

echo.
echo Done. Double-click run_jarvis.bat to start.
pause
