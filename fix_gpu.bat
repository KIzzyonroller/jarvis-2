@echo off
cd /d "%~dp0"
echo === Repair: put Jarvis's speech libraries back to the safe setup ===
call .venv\Scripts\activate.bat
echo Removing any GPU or duplicate versions of ONNX Runtime...
pip uninstall -y onnxruntime-directml onnxruntime-gpu onnxruntime
echo Installing the standard version...
pip install onnxruntime
if exist "%USERPROFILE%\Documents\Jarvis\cache\cuda_check.json" del "%USERPROFILE%\Documents\Jarvis\cache\cuda_check.json"
echo.
echo Done. Start Jarvis again.
echo He now tests the NVIDIA GPU safely on startup and falls back to the CPU by himself if it doesn't work.
echo If you'd rather never use the GPU, add this line to your .env file:  JARVIS_WHISPER_DEVICE=cpu
pause
