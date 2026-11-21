"""
Clipboard history: "what did I copy ten minutes ago?", "copy the link I had before this one back".

Kept in memory only (gone when he closes), the last 60 text copies and the last 4 pictures.
Never kept:
  * anything a password manager marks as private (Windows' "don't put this in clipboard history" flags,
    which 1Password, Bitwarden, KeePass and Windows itself set)
  * anything that looks like a key, token or password (sk-ant-..., long random strings next to "password")
  * his own temporary clipboard use (when he pastes text for you)
"""
import re
import threading
import time
from datetime import datetime

ITEMS = []                    # newest last: {"t", "kind": "text"|"image", "text"|"size", "img"}
MAX_TEXT, MAX_IMG = 60, 4
_IGNORE = {"until": 0.0}
_lock = threading.Lock()
SECRETISH = re.compile(r"(sk-ant-|gsk_|xox[bp]-|ghp_|github_pat_|AKIA[0-9A-Z]{12}|-----BEGIN [A-Z ]*PRIVATE KEY|"
                           r"\b[MN][A-Za-z\d]{23,25}\.[\w-]{6}\.[\w-]{27,})")


def ignore_for(seconds=2.0):
    """He's about to use the clipboard himself: don't record it."""
    _IGNORE["until"] = time.time() + seconds


def _private_formats():
    """True when the copying app asked Windows not to keep this (password managers do)."""
    try:
        import ctypes
        u = ctypes.windll.user32
        for name in ("ExcludeClipboardContentFromMonitorProcessing", "CanIncludeInClipboardHistory",
                     "Clipboard Viewer Ignore"):
            fmt = u.RegisterClipboardFormatW(name)
            if fmt and u.IsClipboardFormatAvailable(fmt):
                return True
    except Exception:
        pass
    return False


def looks_secret(text):
    t = text.strip()
    if SECRETISH.search(t):
        return True
    # one long random-looking token with no spaces (passwords, keys), not a URL or a path
    if 16 <= len(t) <= 128 and " " not in t and not re.match(r"^(https?://|[a-zA-Z]:\\|/|www\.)", t):
        kinds = sum(bool(re.search(p, t)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
        if kinds >= 3 and not re.search(r"[aeiou]{2}", t.lower()):
            return True
    return False


def add_text(text, when=None):
    t = (text or "").strip("\r\n")
    if not t or looks_secret(t):
        return
    with _lock:
        if ITEMS and ITEMS[-1].get("text") == t:
            return
        ITEMS.append({"t": when or time.time(), "kind": "text", "text": t[:20000]})
        texts = [i for i in ITEMS if i["kind"] == "text"]
        if len(texts) > MAX_TEXT:
            ITEMS.remove(texts[0])


def add_image(img, when=None):
    with _lock:
        ITEMS.append({"t": when or time.time(), "kind": "image", "size": f"{img.size[0]}x{img.size[1]}", "img": img})
        imgs = [i for i in ITEMS if i["kind"] == "image"]
        if len(imgs) > MAX_IMG:
            ITEMS.remove(imgs[0])


def _ago(t):
    s = time.time() - t
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{int(s // 60)} min ago"
    return datetime.fromtimestamp(t).strftime("%I:%M %p").lstrip("0")


def recent(query=None, minutes=None, n=10):
    with _lock:
        items = list(ITEMS)
    if minutes:
        cut = time.time() - float(minutes) * 60
        items = [i for i in items if i["t"] >= cut]
    if query:
        q = query.lower()
        items = [i for i in items if i["kind"] == "text" and q in i["text"].lower()]
    return items[-n:]


def tool(action="list", query=None, minutes=None, number=None):
    """list / search / copy (put an older one back on the clipboard; number 1 = the one before the current) / clear."""
    a = (action or "list").lower()
    if a == "clear":
        with _lock:
            ITEMS.clear()
        return "Clipboard history cleared."
    items = recent(query if a in ("search", "copy") else None, minutes, n=20 if not query else 10)
    if a == "copy":
        texts = [i for i in reversed(items) if i["kind"] == "text"]
        k = int(number or 1)
        if not query:
            texts = texts[1:]                         # 1 = the one before what's on the clipboard now
            k = max(1, k)
        if len(texts) < k:
            return "I don't have that many copies in the history (it starts when I start)."
        pick = texts[k - 1]
        import pyperclip
        ignore_for(1.5)
        pyperclip.copy(pick["text"])
        return f"Back on your clipboard (from {_ago(pick['t'])}): {pick['text'][:140]}"
    if not items:
        return ("Nothing in the clipboard history" + (f" matching '{query}'" if query else "") +
                ". (It only covers what you've copied since I started, and never passwords.)")
    lines = []
    for i in reversed(items):
        if i["kind"] == "image":
            lines.append(f"{_ago(i['t'])}: a picture ({i['size']})")
        else:
            one = " ".join(i["text"].split())
            lines.append(f"{_ago(i['t'])}: {one[:180]}{'...' if len(one) > 180 else ''}")
    try:
        import pulls
        pulls.pull("clips", {"rows": [{"when": _ago(i["t"]), "text": (" ".join(i["text"].split())[:220] if i["kind"] == "text"
                                                                       else f"[picture {i['size']}]")}
                                      for i in reversed(items[-10:])]}, id="clips", title="Clipboard", ttl=60, auto=False)
    except Exception as e:
        print(f"[clips] panel: {e}")
    return "Clipboard history, newest first:\n" + "\n".join(lines[:15])


def _loop():
    import ctypes
    u = ctypes.windll.user32
    last = u.GetClipboardSequenceNumber()
    while True:
        time.sleep(0.7)
        try:
            seq = u.GetClipboardSequenceNumber()
            if seq == last:
                continue
            last = seq
            if time.time() < _IGNORE["until"] or _private_formats():
                continue
            time.sleep(0.15)                          # let the app finish putting everything on it
            import pyperclip
            try:
                text = pyperclip.paste()
            except Exception:
                text = ""
            if text:
                add_text(text)
                continue
            try:
                from PIL import ImageGrab
                img = ImageGrab.grabclipboard()
                if img is not None and hasattr(img, "size"):
                    img = img.copy()
                    img.thumbnail((1600, 1600))
                    add_image(img)
            except Exception:
                pass
        except Exception as e:
            print(f"[clips] {e}")
            time.sleep(5)


def start():
    import os
    if os.name != "nt" or os.environ.get("JARVIS_CLIP_HISTORY", "true").lower() == "false":
        return
    threading.Thread(target=_loop, daemon=True, name="clipboard-history").start()
