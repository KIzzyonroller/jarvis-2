"""
What Jarvis/Ultron may do without asking.

Three levels:
  * Free: reading files anywhere on your fixed drives (minus secret stores), read-only
    PowerShell (Get-*, ipconfig, winget list...), everything that was never risky.
  * Ask, with an "Always allow" option: each category below. Once you say "always", that
    category stops asking. Stored in Documents/Jarvis/permissions.json, switch them back
    off in the right-hand panel or by deleting that file.
  * Always ask, no shortcut: shutdown/restart/sign out, emptying the Recycle Bin,
    PowerShell that deletes, formats, edits the registry or downloads-and-runs code,
    and writing into Windows/Program Files. One bad guess there costs too much.
"""
import json
import re
import string
import threading
import time
from pathlib import Path

import config

CATEGORIES = {
    "powershell": ("PowerShell commands", "Commands that change settings or install things. Read-only ones never ask."),
    "files": ("Edit files anywhere", "Create, edit, move and copy files outside the Jarvis folder."),
    "delete": ("Recycle Bin", "Move files and folders to the Recycle Bin (you can restore them)."),
    "force_close": ("Force-close apps", "Kill apps that won't close. Unsaved work in them is lost."),
    "clicks": ("Clicks that send or submit", "Mouse clicks that send, post, submit or install."),
    "discord_send": ("Discord messages", "Messages he posts through his Discord bot. Sending also has to be switched on."),
    "connectors": ("App connectors", "Actions through connected apps (MCP) that can change things. Read-only ones never ask."),
    "blender": ("Blender scripting", "Blender code that touches files, and clearing the scene."),
    "addon": ("Blender add-on install", "Installing the Jarvis Bridge add-on into Blender."),
    "unreal": ("Unreal scripting", "Unreal code that saves, deletes, renames or imports assets, or reaches outside the editor."),
}

_LOCK = threading.Lock()
_STATE = None


def _path():
    return config.JARVIS_DIR / "permissions.json"


def _load():
    global _STATE
    if _STATE is None:
        try:
            d = json.loads(_path().read_text(encoding="utf-8"))
            _STATE = {k: bool(v) for k, v in d.get("always", {}).items() if k in CATEGORIES}
        except Exception:
            _STATE = {}
    return _STATE


def _save():
    try:
        _path().parent.mkdir(parents=True, exist_ok=True)
        _path().write_text(json.dumps({"always": _STATE, "updated": time.strftime("%Y-%m-%d %H:%M")}, indent=1),
                           encoding="utf-8")
    except OSError as e:
        print(f"[permissions] couldn't save: {e}")


def can_always(category):
    return category in CATEGORIES


def allowed(category):
    with _LOCK:
        return bool(category) and _load().get(category, False)


def set_always(category, on=True):
    if category not in CATEGORIES:
        return False
    with _LOCK:
        _load()[category] = bool(on)
        _save()
    return True


def reset():
    global _STATE
    with _LOCK:
        _STATE = {}
        _save()


def state():
    """For the UI: every category, whether it's on 'always allow'."""
    s = _load()
    return [{"key": k, "label": v[0], "detail": v[1], "on": bool(s.get(k))} for k, v in CATEGORIES.items()]


# =================================================================== PowerShell
# Command words that only look at things. Anything not on these lists means "this changes something".
_SAFE_VERBS = {"get", "test", "select", "where", "sort", "measure", "format", "convertto", "group", "resolve",
               "split", "join", "compare", "out-string", "find"}
_SAFE_ALIASES = {"ls", "dir", "gci", "gc", "cat", "type", "gps", "ps", "gsv", "gi", "gp", "gwmi", "gcim", "gl",
                 "pwd", "select", "sort", "where", "?", "ft", "fl", "fw", "measure", "group", "echo", "write-output",
                 "out-string", "findstr", "sls", "hostname", "whoami", "systeminfo", "tasklist", "driverquery",
                 "netstat", "ping", "tracert", "pathping", "nslookup", "getmac", "ver"}
_SAFE_EXE_ARGS = {          # external programs that are read-only only with these first arguments
    "ipconfig": {"", "/all", "/displaydns"},
    "winget": {"list", "search", "show", "--version", "-v"},
    "nvidia-smi": {"", "-q", "--query", "-l", "--query-gpu", "-L"},
    "wmic": None,           # handled below: only "... get ..."
    "powercfg": {"/list", "/l", "/query", "/q", "/getactivescheme", "/a", "/availablesleepstates"},
}
_DANGER = re.compile(
    r"\b(remove-item|rm|del|erase|rd|rmdir|ri|format-volume|format|clear-disk|initialize-disk|remove-partition|"
    r"diskpart|stop-computer|restart-computer|shutdown|logoff|bcdedit|bootrec|reg\s+delete|remove-itemproperty|"
    r"clear-recyclebin|set-executionpolicy|cipher|takeown|icacls|vssadmin|wbadmin|remove-localuser|"
    r"net\s+user|disable-computerrestore|clear-eventlog|wevtutil\s+cl|remove-appxpackage|"
    r"set-mppreference|add-mppreference|netsh\s+advfirewall)\b(?!-)"
    r"|downloadstring|downloadfile|invoke-expression|\biex\b|frombase64string|-encodedcommand|-enc\b"
    r"|\b(iwr|irm|invoke-webrequest|invoke-restmethod|curl|wget)\b.*\|\s*(iex|invoke-expression|powershell|cmd)",
    re.I)


def classify_powershell(cmd):
    """'read' (just runs), 'change' (asks, can be always-allowed) or 'danger' (asks every time)."""
    c = (cmd or "").strip()
    if not c:
        return "read"
    if _DANGER.search(c):
        return "danger"
    if re.search(r"[;&>`]|\$\(|::|\.\w+\s*\(|\bstart-process\b|\binvoke-|\bsaps\b|\bstart\b|(?<!\w)-command\b|\.ps1\b|\.bat\b|\.cmd\b",
                 c, re.I):
        return "change"
    # every Verb-Noun anywhere (including inside { } blocks) must be a looking verb
    bare = re.sub(r"'[^']*'|\"[^\"]*\"", "''", c)          # text in quotes isn't run
    for m in re.finditer(r"(?<![\w\\/:.$-])([a-z]+)-([a-z]+)\b", bare, re.I):
        verb = m.group(1).lower()
        if verb not in _SAFE_VERBS and verb != "out" and m.group(0).lower() not in _SAFE_EXE_ARGS:
            return "change"
    for m in re.finditer(r"\bout-(\w+)", c, re.I):
        if m.group(1).lower() not in ("string", "host", "null"):
            return "change"
    for seg in c.split("|"):
        words = seg.strip().lstrip("(").split()
        if not words:
            return "change"
        head = words[0].lower()
        if head.endswith(".exe"):
            head = head[:-4]
        verb = head.split("-")[0]
        if "-" in head and verb in _SAFE_VERBS:
            continue
        if head in _SAFE_EXE_ARGS:
            first = words[1].lower() if len(words) > 1 else ""
            if head == "wmic":
                if " get" not in seg.lower() or re.search(r"\b(call|set|delete|create)\b", seg, re.I):
                    return "change"
                continue
            if first not in _SAFE_EXE_ARGS[head]:
                return "change"
            continue
        if head in _SAFE_ALIASES:
            continue
        return "change"
    return "read"


# =================================================================== files
def fixed_drives():
    """Every local hard drive / SSD (not network shares, not removable)."""
    import sys
    if sys.platform != "win32":
        return []
    try:
        import ctypes
        out = []
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i, letter in enumerate(string.ascii_uppercase):
            if mask & (1 << i):
                root = f"{letter}:\\"
                if ctypes.windll.kernel32.GetDriveTypeW(root) == 3:      # DRIVE_FIXED
                    out.append(Path(root))
        return out
    except Exception:
        return []


def _parts(p):
    return [x.lower() for x in Path(p).parts]


_SECRET_DIRS = [
    (".ssh",), (".aws",), (".gnupg",), (".azure",), (".kube",), (".docker",),
    ("appdata", "local", "google", "chrome", "user data"), ("appdata", "local", "microsoft", "edge", "user data"),
    ("appdata", "local", "bravesoftware",), ("appdata", "roaming", "mozilla", "firefox"),
    ("appdata", "roaming", "opera software",), ("appdata", "roaming", "microsoft", "credentials"),
    ("appdata", "local", "microsoft", "credentials"), ("appdata", "roaming", "microsoft", "protect"),
    ("appdata", "roaming", "microsoft", "crypto"), ("appdata", "roaming", "discord", "local storage"),
    ("windows", "system32", "config"),
]
_SECRET_NAMES = {".env", "spotify_token.json", "voiceprint.json", "id_rsa", "id_ed25519", ".git-credentials",
                 ".npmrc", ".pypirc", "login data", "cookies", "web data", "key4.db", "logins.json", "permissions.json"}
_SECRET_EXT = {".kdbx", ".kdb", ".pem", ".pfx", ".p12", ".key", ".ppk", ".wallet"}


def is_secret(p):
    """Password stores, keys, browser logins, Jarvis's own keys: never read or sent anywhere."""
    p = Path(p)
    if p.name.lower() in _SECRET_NAMES or p.suffix.lower() in _SECRET_EXT:
        return True
    parts = _parts(p)
    for seq in _SECRET_DIRS:
        n = len(seq)
        for i in range(len(parts) - n + 1):
            if tuple(parts[i:i + n]) == seq:
                return True
    return False


def is_system(p):
    """Windows' own folders: writing there always asks, with no 'always' shortcut."""
    parts = _parts(p)
    if len(parts) < 2:
        return True                        # a drive root itself
    top = parts[1]
    return top in ("windows", "program files", "program files (x86)", "programdata", "$recycle.bin",
                   "system volume information", "recovery", "boot")
