@echo off
cd /d "%~dp0"
where nvidia-smi >nul 2>nul
if errorlevel 1 (
    echo No NVIDIA GPU driver found. Speech recognition will keep using the CPU, which is fine.
    pause
    exit /b 0
)
call .venv\Scripts\activate.bat
echo Installing NVIDIA libraries for GPU speech recognition (about 1 GB, one time)...
pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
echo.
echo Done. Restart Jarvis. He tests the GPU safely on startup: the boot log says "on CUDA" if it works,
echo and he quietly stays on the CPU if it doesn't. If anything goes wrong, run fix_gpu.bat.
pause
