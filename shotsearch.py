"""
Screenshot search: "find the screenshot with the error message", "the one with the receipt from Amazon".

He reads the text in your screenshots once, with Windows' own text recognition, on this PC, and remembers it in
Documents\\Jarvis\\screenshot_index.json (just the words, never the pictures). New screenshots are read in the
background a few at a time while you're not busy. Searching is then instant.

Folders: Pictures\\Screenshots, OneDrive's screenshots, the Snipping Tool and ShareX folders, plus screenshot-
looking images on your Desktop. Settings can add or switch it off.
"""
import base64
import io
import json
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import config

IMG = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
SHOT_NAME = re.compile(r"(screenshot|screen shot|snip|capture|scr_|sharex|\d{4}-\d{2}-\d{2}[ _]\d{2}[-_.]\d{2})", re.I)
INDEX = "screenshot_index.json"
_lock = threading.Lock()
STATE = {"running": False, "done": 0, "todo": 0}


def folders():
    h = config.HOME
    out = [h / "Pictures" / "Screenshots", h / "OneDrive" / "Pictures" / "Screenshots",
           h / "OneDrive" / "Pictures" / "Screenshots 1", h / "Videos" / "Captures",
           h / "Documents" / "ShareX" / "Screenshots", h / "Pictures" / "ShareX"]
    extra = os.environ.get("JARVIS_SHOT_FOLDERS", "")
    out += [Path(p.strip()) for p in extra.split(";") if p.strip()]
    return [p for p in out if p.exists()]


def _candidates():
    seen = []
    for root in folders():
        for p in root.rglob("*"):
            if p.suffix.lower() in IMG and p.is_file():
                seen.append(p)
    desk = config.HOME / "Desktop"
    if desk.exists():
        seen += [p for p in desk.iterdir() if p.suffix.lower() in IMG and SHOT_NAME.search(p.name)]
    return seen


def _load():
    try:
        return json.loads((config.JARVIS_DIR / INDEX).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(idx):
    p = config.JARVIS_DIR / INDEX
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(idx), encoding="utf-8")


def index_some(limit=12, budget=20.0):
    """Read the text of up to `limit` screenshots not read yet. Returns how many were done."""
    import ocr
    from PIL import Image
    with _lock:
        idx = _load()
        files = _candidates()
        known = {str(p) for p in files}
        for k in list(idx):                               # forget deleted ones
            if k not in known:
                idx.pop(k)
        todo = [p for p in files if str(p) not in idx or idx[str(p)].get("m") != int(p.stat().st_mtime)]
        todo.sort(key=lambda p: -p.stat().st_mtime)       # newest first
        STATE["todo"] = len(todo)
        n, t0 = 0, time.time()
        for p in todo[:limit]:
            if time.time() - t0 > budget:
                break
            try:
                with Image.open(p) as im:
                    text = ocr.read(im.copy())
            except Exception as e:
                text = ""
                print(f"[shots] {p.name}: {e}")
            idx[str(p)] = {"m": int(p.stat().st_mtime), "t": " ".join(text.split())[:4000]}
            n += 1
        _save(idx)
        STATE["done"] = len(idx)
        STATE["todo"] = max(0, len(todo) - n)
    return n


def _score(text, words, phrase):
    t = text.lower()
    if phrase and phrase in t:
        return 100 + len(phrase)
    return sum(10 if re.search(rf"\b{re.escape(w)}", t) else 0 for w in words)


def search(query, show=True, n=6):
    q = (query or "").lower().strip()
    stop = {"the", "a", "an", "screenshot", "screenshots", "with", "of", "that", "one", "my", "find", "where", "it", "says", "say"}
    words = [w for w in re.findall(r"[\w'.-]+", q) if w not in stop]
    phrase = " ".join(words) if len(words) > 1 else ""
    if not words:
        return "What's in the screenshot? A word or two that was on screen."
    idx = _load()
    if not idx:
        index_some(40, budget=40)
        idx = _load()
    hits = []
    for path, row in idx.items():
        s = _score(row.get("t", ""), words, phrase)
        if s >= 10 * max(1, len(words) - 1):
            hits.append((s, row["m"], path, row["t"]))
    hits.sort(key=lambda h: (-h[0], -h[1]))
    hits = [h for h in hits if Path(h[2]).exists()][:n]
    pending = STATE.get("todo", 0)
    if not hits:
        return (f"No screenshot I've read mentions '{query}'." +
                (f" I still have {pending} newer ones to read; try again in a few minutes." if pending else ""))
    if show:
        _panel(query, hits)
    out = []
    for i, (s, m, path, text) in enumerate(hits, 1):
        snip = _snippet(text, words)
        out.append(f"{i}. {Path(path).name} ({datetime.fromtimestamp(m):%b %d}): \"{snip}\"")
    return (f"Found {len(hits)} screenshot{'s' if len(hits) != 1 else ''} (best first, on your desktop):\n" + "\n".join(out) +
            "\nTo open one: open with its path: " + "; ".join(f"{i}={h[2]}" for i, h in enumerate(hits, 1)))


def _snippet(text, words):
    t = text
    for w in words:
        m = re.search(re.escape(w), t, re.I)
        if m:
            a = max(0, m.start() - 50)
            return ("..." if a else "") + t[a:m.start() + 90].strip() + "..."
    return t[:120]


def _thumb(path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((360, 220))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=70)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def _panel(query, hits):
    try:
        import pulls
        rows = [{"name": Path(p).name, "when": datetime.fromtimestamp(m).strftime("%b %d"), "thumb": _thumb(p),
                 "snip": _snippet(t, [query.split()[0]] if query else [])[:140], "path": p} for _, m, p, t in hits]
        pulls.pull("shots", {"query": query, "rows": rows}, id="shots", title="Screenshots", ttl=180, focus=len(rows) > 2, auto=False)
    except Exception as e:
        print(f"[shots] panel: {e}")


def status():
    idx = _load()
    return (f"I've read {len(idx)} screenshots" + (f", {STATE['todo']} newer ones still to go" if STATE.get("todo") else "") +
            f". Folders: {', '.join(str(f).replace(str(config.HOME), '~') for f in folders()) or 'none found'}.")


def tool(action="search", query=None):
    a = (action or "search").lower()
    if a == "status":
        return status()
    if a == "reindex":
        threading.Thread(target=index_some, args=(400, 600), daemon=True).start()
        return "Reading all your screenshots again in the background."
    return search(query or "")


def _loop(core):
    time.sleep(90)
    while True:
        try:
            import tools
            if not config.LITE and not tools.in_game() and getattr(core, "_turn", None) is None:
                index_some(8, budget=15)               # a few at a time, never mid-game or while he's answering
        except Exception as e:
            print(f"[shots] {e}")
        time.sleep(120)


def start(core):
    if os.name != "nt" or os.environ.get("JARVIS_SHOT_SEARCH", "true").lower() == "false":
        return
    threading.Thread(target=_loop, args=(core,), daemon=True, name="screenshot-index").start()
