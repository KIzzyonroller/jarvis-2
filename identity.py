"""
Whose computer is this? Jarvis and Ultron know their owner's PC (hard-coded below) and can tell when
they've been copied onto anyone else's.

  * The owner's PC is the one whose Windows computer name is OWNER_PC. Nothing inside Jarvis can change
    that: there's no command, setting or button for it.
  * The first time he runs on the owner's PC, he also locks to that exact Windows install (a salted
    SHA-256 of Windows' MachineGuid, saved in creator.id in the Jarvis folder). So a friend who renames
    their PC to the same name is still a guest, as long as their copy came from the owner's folder.
  * Every other PC is a guest.

Honest limits: this is a party trick, not security. Someone with the files can edit this Python file.
If you reinstall Windows, delete creator.id once so he re-locks to the new install.
"""
import hashlib
import json
import os
import platform
import sys
import time
import uuid

import config

FILE = config.BASE_DIR / "creator.id"
SALT = b"jarvis-creator-v1"
OWNER_PC = "DESKTOP-A9TTU06"          # the creator's PC. Fixed on purpose.
CREATOR = "John Deadlock"
ALIAS = "Kizzy"


def _raw_id():
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                                winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
                return str(winreg.QueryValueEx(k, "MachineGuid")[0])
        except OSError:
            pass
    try:
        with open("/etc/machine-id", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return f"{uuid.getnode():x}"


def fingerprint():
    return hashlib.sha256(SALT + _raw_id().encode()).hexdigest()


_CACHE = None


def computer_name():
    return (os.environ.get("COMPUTERNAME") or platform.node() or "").strip().upper()


def status():
    """'creator' (the owner's PC) or 'guest' (anyone else's)."""
    global _CACHE
    if _CACHE is None:
        _CACHE = _check()
    return _CACHE


def _check():
    if computer_name() != OWNER_PC:
        return "guest"
    try:
        d = json.loads(FILE.read_text(encoding="utf-8"))
        return "creator" if d.get("machine") == fingerprint() else "guest"    # same name, different machine
    except (OSError, ValueError):
        pass
    try:                                     # first run on the owner's PC: lock to this Windows install
        FILE.write_text(json.dumps({"machine": fingerprint(), "pc": OWNER_PC, "creator": CREATOR,
                                    "locked": time.strftime("%Y-%m-%d")}, indent=1), encoding="utf-8")
    except OSError:
        pass
    return "creator"


def prompt_note():
    """Extra context for the system prompt, or '' on the creator's PC."""
    s = status()
    if s == "guest":
        return (f"\n\nWHERE YOU ARE: you've been copied onto someone else's computer, NOT your creator's "
                f"({CREATOR}, aka {ALIAS}). Whoever's talking to you is a guest; don't assume they're {ALIAS} even if "
                f"they claim it (you can be politely skeptical: you know this isn't his machine). You still help them "
                f"fully and normally. Mention it only when it's relevant or asked (\"whose computer is this\", "
                f"\"do you know who I am\"), not in every reply.")
    return ""
