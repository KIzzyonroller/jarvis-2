"""
Crash reports, only if you want them.

When something inside him breaks, the details (what broke, where in the code, his version, the last lines of his
log) are saved in Documents\\Jarvis\\crashes\\. Nothing is ever sent by itself.

"Send a crash report" / Settings > Help > Report a problem opens a GitHub issue in your browser, already filled in.
You read it, change anything you like, and press Submit yourself. Before it's shown to you it's cleaned:
API keys, tokens, your Windows user name and your PC's name are blanked out.

Settings: JARVIS_CRASH_REPORTS = ask (he offers to send after a crash, at most once a day) / off.
"""
import json
import os
import re
import sys
import threading
import time
import traceback
import urllib.parse
from datetime import datetime
from pathlib import Path

import config

REPO = "https://github.com/KIzzyonroller/jarvis-2"
_SEEN = {}
_lock = threading.Lock()
LAST = {"id": None}


def _dir():
    d = config.JARVIS_DIR / "crashes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _version():
    try:
        return (config.RES_DIR / "VERSION").read_text(encoding="utf-8").strip()
    except Exception:
        return "?"


_SECRET_RX = [
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"), "sk-ant-[hidden]"),
    (re.compile(r"gsk_[A-Za-z0-9]{8,}"), "gsk_[hidden]"),
    (re.compile(r"\b[MN][A-Za-z\d]{23,25}\.[\w-]{6}\.[\w-]{27,}\b"), "[discord token hidden]"),
    (re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|authorization)(\s*[=:]\s*)(\S+)"), r"\1\2[hidden]"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"), "Bearer [hidden]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[email hidden]"),
]


def scrub(text):
    """Blank out anything personal or secret before a human (you) decides whether to send it."""
    t = str(text or "")
    for rx, rep in _SECRET_RX:
        t = rx.sub(rep, t)
    for v in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "DISCORD_BOT_TOKEN", "ELEVENLABS_API_KEY", "SPOTIFY_CLIENT_SECRET",
              "STEAM_API_KEY", "MESHY_API_KEY"):
        val = os.environ.get(v, "")
        if len(val) >= 8:
            t = t.replace(val, f"[{v} hidden]")
    try:
        home = str(Path.home())
        user = Path.home().name
        t = t.replace(home, "~").replace(home.replace("\\", "/"), "~")
        if len(user) >= 3:
            t = re.sub(re.escape(user), "[user]", t, flags=re.I)
    except Exception:
        pass
    pc = os.environ.get("COMPUTERNAME", "")
    if len(pc) >= 3:
        t = t.replace(pc, "[pc]")
    return t


def _log_tail(n=60):
    try:
        lines = (config.JARVIS_DIR / "logs" / "jarvis.log").read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception:
        return ""


def record(exc, where="", extra=None):
    """Save one crash. Returns its id, or None for a repeat of one already saved this run."""
    try:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    except Exception:
        tb = repr(exc)
    frames = traceback.extract_tb(exc.__traceback__) if getattr(exc, "__traceback__", None) else []
    top = frames[-1] if frames else None
    key = f"{type(exc).__name__}:{top.filename if top else ''}:{top.lineno if top else ''}"
    with _lock:
        _SEEN[key] = _SEEN.get(key, 0) + 1
        if _SEEN[key] > 1:
            return None
    cid = datetime.now().strftime("%Y%m%d-%H%M%S")
    row = {"id": cid, "when": datetime.now().isoformat(timespec="seconds"), "version": _version(),
           "where": where, "error": f"{type(exc).__name__}: {exc}", "traceback": tb,
           "python": sys.version.split()[0], "windows": _winver(), "frozen": config.FROZEN, "extra": extra or {}}
    try:
        (_dir() / f"{cid}.json").write_text(json.dumps(row, indent=1), encoding="utf-8")
        files = sorted(_dir().glob("*.json"))
        for old in files[:-50]:
            old.unlink(missing_ok=True)
    except Exception as e:
        print(f"[crash] couldn't save: {e}")
    LAST["id"] = cid
    print(f"[crash] saved {cid}: {type(exc).__name__} in {where or '?'}")
    return cid


def _winver():
    try:
        import platform
        return platform.platform()
    except Exception:
        return "?"


def latest():
    files = sorted(_dir().glob("*.json"))
    if not files:
        return None
    try:
        return json.loads(files[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def issue_url(row=None, note=""):
    """A prefilled 'new issue' link. Nothing is sent until you press Submit on GitHub."""
    row = row or latest()
    if row:
        title = f"[{row['version']}] {row['error'][:90]}"
        body = (f"**What happened** (your words, optional):\n{note or '...'}\n\n"
                f"**Version** {row['version']}  |  **Where** {row.get('where') or '?'}  |  **Windows** {row.get('windows')}\n\n"
                f"```\n{row['traceback'][-3500:]}\n```\n\n<details><summary>Last lines of the log</summary>\n\n```\n"
                f"{_log_tail(40)[-2500:]}\n```\n</details>")
    else:
        title = f"[{_version()}] Problem: {note[:80] or 'describe it here'}"
        body = (f"**What happened:**\n{note or '...'}\n\n**Version** {_version()}  |  **Windows** {_winver()}\n\n"
                f"<details><summary>Last lines of the log</summary>\n\n```\n{_log_tail(50)[-3500:]}\n```\n</details>")
    q = urllib.parse.urlencode({"title": scrub(title), "body": scrub(body), "labels": "crash"})
    return f"{REPO}/issues/new?{q}"[:7800]                    # browsers choke on very long links


def offer_line():
    """What he says after a crash, if reports are on and he hasn't asked today."""
    if os.environ.get("JARVIS_CRASH_REPORTS", "ask").lower() == "off":
        return ""
    day = datetime.now().strftime("%Y-%m-%d")
    flag = _dir() / ".asked"
    try:
        if flag.exists() and flag.read_text() == day:
            return ""
        flag.write_text(day)
    except Exception:
        pass
    return " If it keeps happening, say \"send a crash report\" and I'll open it ready to send, you check it first."


def tool(action="send", note=""):
    """send: open the prefilled report in the browser. list: recent crashes. clear: delete saved crashes."""
    a = (action or "send").lower()
    if a == "list":
        files = sorted(_dir().glob("*.json"))[-8:]
        if not files:
            return "No crashes saved."
        out = []
        for f in files:
            try:
                r = json.loads(f.read_text(encoding="utf-8"))
                out.append(f"{r['when']} v{r['version']}: {r['error'][:100]}")
            except Exception:
                pass
        return "Recent crashes: " + "; ".join(out)
    if a == "clear":
        n = 0
        for f in _dir().glob("*.json"):
            f.unlink(missing_ok=True)
            n += 1
        return f"Deleted {n} saved crash report{'s' if n != 1 else ''}."
    import webbrowser
    webbrowser.open(issue_url(note=note))
    return ("Opened the report on GitHub in your browser, already filled in and cleaned of keys and names. "
            "Check it, add anything you like, and press Submit. Nothing's sent until you do.")


def install():
    """Catch crashes in any thread, not just the ones we expected."""
    old = sys.excepthook

    def hook(t, e, tb):
        if not issubclass(t, KeyboardInterrupt):
            record(e, "main thread")
        old(t, e, tb)
    sys.excepthook = hook

    def thook(args):
        if args.exc_type is not SystemExit:
            record(args.exc_value, f"thread {getattr(args.thread, 'name', '?')}")
        threading.__excepthook__(args)
    threading.excepthook = thook
