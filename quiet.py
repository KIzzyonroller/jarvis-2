"""
Whisper mode: late at night, or while you're on a call, he talks much more quietly and keeps it to a sentence.

On automatically (Settings > Voice & effects > Whisper mode: auto) between the hours you pick and whenever a call app
is using your microphone (Discord, Zoom, Teams, Skype, Slack, Google Meet in Chrome or Edge...). Windows records
which apps are using the mic right now, so that's read rather than guessed. Or just say "whisper mode on / off".
"""
import os
import sys
import threading
import time
from datetime import datetime

import config

CALL_APPS = ("discord", "zoom", "teams", "ms-teams", "skype", "slack", "webex", "chrome", "msedge", "firefox", "opera",
             "brave", "telegram", "whatsapp", "signal", "obs64")
MANUAL = {"on": None}          # None = automatic, True / False = you said so (until you say otherwise or restart)
STATE = {"on": False, "why": ""}


def _settings():
    mode = os.environ.get("JARVIS_WHISPER", "auto").lower()
    try:
        a, b = int(os.environ.get("JARVIS_WHISPER_FROM", "23")), int(os.environ.get("JARVIS_WHISPER_TO", "7"))
    except ValueError:
        a, b = 23, 7
    try:
        vol = max(5, min(100, int(os.environ.get("JARVIS_WHISPER_VOL", "35")))) / 100
    except ValueError:
        vol = .35
    return mode, a, b, vol


def mic_in_use():
    """Apps using the microphone right now (other than him), from Windows' privacy records."""
    if sys.platform != "win32":
        return []
    import winreg
    out = []
    base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
    me = os.path.basename(sys.executable).lower()

    def scan(path):
        try:
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
        except OSError:
            return
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(k, i)
            except OSError:
                break
            i += 1
            if sub == "NonPackaged":
                scan(path + "\\" + sub)
                continue
            try:
                sk = winreg.OpenKey(k, sub)
                stop, _ = winreg.QueryValueEx(sk, "LastUsedTimeStop")
                start, _ = winreg.QueryValueEx(sk, "LastUsedTimeStart")
            except OSError:
                continue
            if stop == 0 and start:
                name = sub.replace("#", "\\").rsplit("\\", 1)[-1].lower()
                if name != me and "jarvis" not in name and "python" not in name:
                    out.append(name)
    scan(base)
    return out


def on_call():
    try:
        return [a for a in mic_in_use() if any(c in a for c in CALL_APPS)]
    except Exception:
        return []


def check():
    mode, a, b, vol = _settings()
    why = ""
    if MANUAL["on"] is not None:
        on = MANUAL["on"]
        why = "you asked"
    elif mode == "on":
        on, why = True, "always on"
    elif mode == "off":
        on = False
    else:
        h = datetime.now().hour
        late = (a <= h or h < b) if a > b else (a <= h < b)
        calls = on_call()
        on = late or bool(calls)
        why = ("on a call (" + calls[0].replace(".exe", "") + ")") if calls else ("late" if late else "")
    import voice
    voice.GAIN = vol if on else 1.0
    if on != STATE["on"]:
        print(f"[whisper] {'on: ' + why if on else 'off'}")
    STATE.update(on=on, why=why)
    return on


def note():
    """Added to his instructions for this turn while it's on."""
    if not STATE["on"]:
        return ""
    return (f"(Whisper mode is on: {STATE['why']}. One short, low-key sentence unless they ask for more; "
            "no jokes that need a big reaction.)")


def set_manual(on):
    MANUAL["on"] = on
    check()
    return STATE


def start():
    def loop():
        while True:
            try:
                check()
            except Exception as e:
                print(f"[whisper] {e}")
            time.sleep(5)
    threading.Thread(target=loop, daemon=True, name="whisper-mode").start()
