"""
Start with Windows, and only ever one copy running.

Autostart uses the standard per-user startup list (HKCU\\...\\CurrentVersion\\Run), the same place most
apps use. It shows in Task Manager > Startup apps, where you can also switch it off. No admin rights.
When Windows starts him he runs without the console window (his log goes to
Documents\\Jarvis\\logs\\jarvis.log), waits a few seconds so login isn't sluggish, and starts tucked
into the corner widget.

Single copy: the first copy holds a tiny local "doorbell" (127.0.0.1 only). Launching him again rings
it, the running copy comes to the front, and the new one quits, so you never get two of him answering.
"""
import socket
import sys
import threading
from pathlib import Path

import config

KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = "JarvisAssistant"
DOORBELL = ("127.0.0.1", 8767)


def available():
    return sys.platform == "win32"


def _program():
    """The installed app: the launcher next to the 'current' folder, whose path never changes between
    updates (current\\Jarvis.exe gets replaced each time)."""
    exe = Path(sys.executable)
    stub = exe.parent.parent / exe.name
    return stub if exe.parent.name.lower() == "current" and stub.exists() else exe


def command():
    """What Windows runs at login: the venv's windowless Python, this folder's jarvis.py, --startup."""
    if config.FROZEN:
        return f'"{_program()}" --startup'
    venv = config.BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"
    exe = venv if venv.exists() else Path(sys.executable).with_name("pythonw.exe")
    if not exe.exists():
        exe = Path(sys.executable)
    return f'"{exe}" "{config.BASE_DIR / "jarvis.py"}" --startup'


def _get():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as k:
            return winreg.QueryValueEx(k, NAME)[0]
    except OSError:
        return None


def is_on():
    """True only if it's on AND points at this copy of Jarvis (a moved folder counts as off)."""
    if not available():
        return False
    v = _get()
    mine = str(_program()) if config.FROZEN else str(config.BASE_DIR / "jarvis.py")
    return bool(v) and mine.lower() in v.lower()


def set_on(on):
    """Returns a sentence describing the result."""
    if not available():
        return "Starting with Windows only works on Windows."
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(k, NAME)
            except FileNotFoundError:
                pass
    return "I'll start with Windows from now on." if on else "I won't start with Windows anymore."


# ------------------------------------------------------------------ one copy at a time
_server = None


def claim(on_show, wait=0.0):
    """Become THE running copy. Returns False if another copy is already running (it's been told to
    come to the front, and this one should exit). wait: keep trying this long first (after an update,
    the old copy is still closing)."""
    global _server
    import time
    end = time.time() + wait
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):       # Windows: nobody else may share this port
            s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            s.bind(DOORBELL)
            break
        except OSError:
            s.close()
            if time.time() < end:
                time.sleep(0.5)
                continue
            try:
                with socket.create_connection(DOORBELL, timeout=2) as c:
                    c.sendall(b"show\n")
            except OSError:
                pass
            return False
    s.listen(2)
    _server = s

    def serve():
        while True:
            try:
                conn, addr = s.accept()
            except OSError:
                return
            with conn:
                try:
                    conn.settimeout(2)
                    if addr[0] == "127.0.0.1" and conn.recv(16).strip() == b"show":
                        on_show()
                except Exception:
                    pass
    threading.Thread(target=serve, daemon=True, name="single-copy").start()
    return True


def release():
    """Let go of the 'I'm running' lock now (restarting): the new copy can start straight away."""
    global _server
    s, _server = _server, None
    if s is not None:
        try:
            s.shutdown(socket.SHUT_RDWR)         # wakes the thread waiting in accept(); a plain close() doesn't free
        except OSError:                          # the port while that thread is still blocked on it
            pass
        try:
            s.close()
        except OSError:
            pass
