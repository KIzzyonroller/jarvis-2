@echo off
cd /d "%~dp0"
echo === Run Jarvis's voice on your graphics card (any GPU: NVIDIA, AMD or Intel) ===
echo This swaps the CPU version of ONNX Runtime for the DirectML (GPU) version.
call .venv\Scripts\activate.bat
pip uninstall -y onnxruntime
pip install onnxruntime-directml
if errorlevel 1 (
    echo Install failed. Putting the CPU version back.
    pip install onnxruntime
    pause
    exit /b 1
)
echo.
echo Done. Restart Jarvis. The console should say "VOICE SYNTHESIS ONLINE [KOKORO ON GPU]".
echo if the voice ever sounds wrong, run:  pip uninstall -y onnxruntime-directml ^&^& pip install onnxruntime
pause
