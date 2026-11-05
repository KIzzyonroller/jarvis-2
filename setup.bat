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

rem A GPU experiment can leave two versions of ONNX Runtime fighting each other. Put it back to one.
pip show onnxruntime-directml >nul 2>nul && (pip uninstall -y onnxruntime-directml onnxruntime & pip install onnxruntime)
pip show onnxruntime-gpu >nul 2>nul && (pip uninstall -y onnxruntime-gpu onnxruntime & pip install onnxruntime)

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
