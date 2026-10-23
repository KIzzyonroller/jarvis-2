"""
Entry point of the installed app (Jarvis.exe). Running from source still uses jarvis.py directly.

Velopack has to see the process first: when Setup.exe installs, updates or uninstalls him it starts
Jarvis.exe with special arguments, and App().run() handles those and exits before anything heavy loads.
"""
import sys

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "JarvisAssistant"


def _remove_autostart(*_):
    """Uninstalling: take him out of Windows' startup list so nothing points at a deleted program."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, RUN_NAME)
    except OSError:
        pass


def _velopack():
    try:
        import velopack
    except ImportError:
        return
    app = velopack.App()
    app.on_before_uninstall_fast_callback(_remove_autostart)
    app.run()


def _cuda_test():
    """speech.py tests the GPU in a separate process (a bad NVIDIA driver can crash the process outright).
    In the installed app that process is Jarvis.exe --cuda-test."""
    import speech
    sys.argv = [sys.argv[0], ""]
    exec(compile(speech._CUDA_TEST, "<cuda-test>", "exec"), {"__name__": "__cuda_test__"})


SELFTEST_MODULES = [
    "config", "core", "brain", "tools", "speech", "voice", "vad", "aec", "intents", "personas", "permissions",
    "spotify", "youtube", "notifications", "briefing", "history", "connectors", "usage", "jobs", "discord_bot",
    "app_update", "autostart", "phone", "mini", "health", "cloud_stt", "download_models", "email_reader", "netflix",
    "anthropic", "numpy", "onnxruntime", "faster_whisper", "ctranslate2", "kokoro_onnx", "sounddevice", "webview",
    "edge_tts", "pygame", "requests", "psutil", "PIL", "cv2", "yt_dlp", "mcp", "discord", "velopack",
    "espeakng_loader", "phonemizer",
]
SELFTEST_WINDOWS = ["pyautogui", "pygetwindow", "pyperclip", "pycaw.pycaw", "comtypes", "pyttsx3", "pyttsx3.drivers.sapi5",
                    "screen_brightness_control", "send2trash", "winreg", "winrt.windows.media.control"]


def _selftest(out_path):
    """Run by the build (Jarvis.exe --selftest result.txt) before anything is published: does every part
    he needs actually load inside the packaged app? Missing pieces are the usual way a build breaks."""
    import importlib
    import os
    import traceback
    problems = []
    mods = SELFTEST_MODULES + (SELFTEST_WINDOWS if sys.platform == "win32" else [])
    for m in mods:
        try:
            importlib.import_module(m)
        except Exception as e:
            problems.append(f"import {m}: {type(e).__name__}: {e}")
    try:
        import config
        for rel in ("ui/index.html", "ui/mini.html", "jarvis_blender_bridge.py", "VERSION"):
            if not (config.RES_DIR / rel).exists():
                problems.append(f"missing file: {rel}")
        import faster_whisper
        assets = os.path.join(os.path.dirname(faster_whisper.__file__), "assets")
        if not os.path.isdir(assets) or not os.listdir(assets):
            problems.append("missing faster_whisper assets (speech detection model)")
    except Exception:
        problems.append(traceback.format_exc())
    text = "SELFTEST OK" if not problems else "SELFTEST FAILED\n" + "\n".join(problems)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return 0 if not problems else 1


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--selftest":     # the build's check, before anything is installed
        sys.exit(_selftest(sys.argv[2]))
    if getattr(sys, "frozen", False):
        _velopack()
        if len(sys.argv) > 1 and sys.argv[1] == "--cuda-test":
            _cuda_test()
            sys.exit(0)
    import jarvis
    jarvis.main()
