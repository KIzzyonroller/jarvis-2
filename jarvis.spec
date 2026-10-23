# PyInstaller recipe for the installed app. Used by build.ps1; you don't run this by hand.
# Produces dist\Jarvis\ (Jarvis.exe plus everything it needs), which Velopack then turns into Setup.exe.
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("ui", "ui"), ("jarvis_blender_bridge.py", "."), ("VERSION", ".")]
if os.path.exists("update_source.txt"):
    datas.append(("update_source.txt", "."))
binaries = []
hiddenimports = [
    # loaded by name at runtime, so PyInstaller can't see them
    "pyttsx3.drivers", "pyttsx3.drivers.sapi5", "comtypes.stream", "pycaw.pycaw",
    "edge_tts", "sounddevice", "send2trash", "screen_brightness_control",
]
# Packages that ship data files, native libraries or plugins next to their code
for pkg in ["faster_whisper", "ctranslate2", "onnxruntime", "kokoro_onnx", "espeakng_loader", "phonemizer",
            "language_tags", "segments", "csvw", "webview", "mcp", "discord", "velopack", "certifi",
            "screen_brightness_control", "pycaw", "comtypes", "_sounddevice_data"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as e:                       # not installed on this machine (e.g. Windows-only on a test box)
        print(f"[spec] skipping {pkg}: {e}")
hiddenimports += collect_submodules("yt_dlp.extractor") if sys.platform == "win32" else []

a = Analysis(
    ["app_main.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # Heavy things only reachable through optional code paths he never uses (about 100 MB)
    excludes=["torch", "tensorflow", "matplotlib", "IPython", "pytest", "pandas", "scipy", "sklearn",
              "onnxruntime.transformers", "onnxruntime.quantization", "tkinter.test"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Jarvis",
    icon="assets/jarvis.ico",
    console=False,            # a window app: no black console (the log goes to Documents\Jarvis\logs)
    upx=False,                # compressed exes trip antivirus far more often
)
coll = COLLECT(exe, a.binaries, a.datas, name="Jarvis", upx=False)
