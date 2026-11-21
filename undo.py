"""
"Undo that": he takes back his last change.

Every change he makes that can be reversed is written down here first (undo.json, the last 30), so undo works
even after a restart:

  move / rename     moved back to where it was (if nothing's been put there since)
  new file          made by him (a document, a copy, a zip): goes to the Recycle Bin
  edit              the file goes back to how it was before his edit
  delete            he kept a copy before sending it to the Recycle Bin (files under 200 MB), and puts it back
  settings          a setting he changed by voice goes back to its old value (his world, widgets, modes...)

Things that can't be taken back (a message he sent, something you approved in another app) are never claimed as
undone. Undo only ever reverses HIS changes, and each step only once.
"""
import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path

import config

FILE = "undo.json"
KEEP = 30
_lock = threading.Lock()
SAFE_COPY_MAX = 200 * 1024 * 1024
CORE = None


def _path():
    return config.JARVIS_DIR / FILE


def _vault():
    d = config.JARVIS_DIR / "undo_vault"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load():
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items):
    try:
        _path().parent.mkdir(parents=True, exist_ok=True)
        _path().write_text(json.dumps(items[-KEEP:], indent=1), encoding="utf-8")
    except Exception as e:
        print(f"[undo] save: {e}")
    keep = {i.get("data", {}).get("vault") for i in items[-KEEP:]}
    try:
        for f in _vault().iterdir():
            if str(f) not in keep and time.time() - f.stat().st_mtime > 3600:   # an hour's grace for copies in flight
                (shutil.rmtree if f.is_dir() else os.remove)(f)
    except Exception:
        pass


def record(kind, desc, **data):
    """Write down a change BEFORE (or right after) making it."""
    with _lock:
        items = _load()
        items.append({"id": uuid.uuid4().hex[:6], "t": time.time(), "kind": kind, "desc": desc, "data": data})
        _save(items)


def keep_copy(p):
    """Before a delete: keep a copy so undo can bring it back. Returns the vault path, or None if too big."""
    p = Path(p)
    try:
        size = p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        if size > SAFE_COPY_MAX:
            return None
        dst = _vault() / f"{uuid.uuid4().hex[:8]}_{p.name}"
        (shutil.copytree if p.is_dir() else shutil.copy2)(p, dst)
        return str(dst)
    except Exception as e:
        print(f"[undo] couldn't keep a copy of {p}: {e}")
        return None


def last():
    items = _load()
    return items[-1] if items else None


def listing(n=6):
    items = _load()[-n:]
    if not items:
        return "Nothing to undo."
    return "Recent changes I can undo, newest last: " + "; ".join(
        f"{i['desc']} ({_ago(i['t'])})" for i in items)


def _ago(t):
    s = time.time() - t
    return "just now" if s < 90 else f"{int(s // 60)} min ago" if s < 3600 else f"{int(s // 3600)} h ago" if s < 86400 \
        else f"{int(s // 86400)} days ago"


def undo(steps=1):
    """Reverse the last change (or the last N). Says exactly what happened."""
    out = []
    for _ in range(max(1, min(int(steps or 1), 10))):
        with _lock:
            items = _load()
            if not items:
                break
            item = items.pop()
            _save(items)
        try:
            out.append(_reverse(item))
        except Exception as e:
            out.append(f"Couldn't undo \"{item['desc']}\": {type(e).__name__}: {e}")
    return " ".join(out) if out else "Nothing to undo."


def _reverse(item):
    k, d = item["kind"], item["data"]
    if k == "move":
        src, dst = Path(d["src"]), Path(d["dst"])
        if not dst.exists():
            return f"Can't undo \"{item['desc']}\": {dst.name} isn't at {dst.parent} any more."
        if src.exists():
            return f"Can't undo \"{item['desc']}\": something called {src.name} is back in {src.parent} already."
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dst), str(src))
        return f"Undone: {src.name} is back in {src.parent}."
    if k == "new":
        p = Path(d["path"])
        if not p.exists():
            return f"{p.name} is already gone."
        if d.get("mtime") and abs(p.stat().st_mtime - d["mtime"]) > 2:
            return f"Didn't undo: {p.name} was changed after I made it, so I left it alone."
        from send2trash import send2trash
        send2trash(str(p))
        return f"Undone: {p.name} is in the Recycle Bin."
    if k == "edit":
        p, backup = Path(d["path"]), Path(d["backup"])
        if not backup.exists():
            return f"Can't undo the edit to {p.name}: the saved original is gone."
        shutil.copy2(backup, p)
        return f"Undone: {p.name} is back to how it was before my edit."
    if k == "delete":
        p, vault = Path(d["path"]), d.get("vault")
        if not vault or not Path(vault).exists():
            return f"I can't bring {p.name} back myself (it was too big to keep a copy). It's in the Recycle Bin."
        if p.exists():
            return f"Can't undo: there's a new {p.name} in that spot already."
        p.parent.mkdir(parents=True, exist_ok=True)
        (shutil.copytree if Path(vault).is_dir() else shutil.copy2)(vault, p)
        return f"Undone: {p.name} is back in {p.parent}. (The other copy is still in the Recycle Bin.)"
    if k == "dupes":
        back, gone = 0, []
        for f in d.get("files", []):
            p, keep = Path(f["path"]), f.get("keep")
            if p.exists():
                continue
            if keep and Path(keep).exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(keep, p)
                back += 1
            else:
                gone.append(p.name)
        return (f"Undone: put {back} duplicate{'s' if back != 1 else ''} back." +
                (f" {len(gone)} were look-alike photos with no exact copy left; those are in the Recycle Bin." if gone else ""))
    if k == "settings":
        before = d.get("before") or {}
        if CORE is None:
            return "Can't undo a setting right now."
        import settings
        CORE.set_widgets({k2: (v if v is not None else settings.DEFAULTS.get(k2, "")) for k2, v in before.items()},
                         record_undo=False)
        return "Undone: " + item["desc"].replace("Changed", "put back").replace("changed", "put back") + "."
    return f"\"{item['desc']}\" can't be undone."


def start(core):
    global CORE
    CORE = core
