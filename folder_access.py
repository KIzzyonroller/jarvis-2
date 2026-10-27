"""
Specific folders (or files) you've let him into: "Jarvis, you can work in my Game Project folder".

  * read:  he can look inside, even where he normally can't (a USB stick, a network drive, or anywhere at all
           when "Read files anywhere" is off in Settings).
  * edit:  he can also create, change, move, copy and rename files there without asking each time.
           Deleting still asks (it goes to the Recycle Bin).
Granting always shows an approval card first (there's no "always allow" for it), and only happens when you ask.
Never allowed, whatever you grant: password stores, keys and browser logins (permissions.is_secret), and editing
inside Windows' own folders or a whole drive. The list is in the System panel, with Remove; he can also
"stop accessing" a folder when you tell him to. Saved in Documents\\Jarvis\\folders.json.
"""
import json
import threading
import time
from pathlib import Path

import config
import permissions

_LOCK = threading.Lock()
_DATA = None


def _path():
    return config.JARVIS_DIR / "folders.json"


def _load():
    global _DATA
    if _DATA is None:
        try:
            d = json.loads(_path().read_text(encoding="utf-8"))
            _DATA = [g for g in d.get("folders", []) if g.get("path") and g.get("mode") in ("read", "edit")]
        except (OSError, ValueError):
            _DATA = []
    return _DATA


def _save():
    try:
        _path().parent.mkdir(parents=True, exist_ok=True)
        tmp = _path().with_suffix(".tmp")
        tmp.write_text(json.dumps({"folders": _DATA}, indent=1), encoding="utf-8")
        tmp.replace(_path())
    except OSError as e:
        print(f"[folders] couldn't save: {e}")


def _norm(p):
    try:
        return Path(p).expanduser().resolve()
    except Exception:
        return Path(p)


def _inside(p, root):
    try:
        _norm(p).relative_to(_norm(root))
        return True
    except ValueError:
        return False


def items():
    with _LOCK:
        return [dict(g) for g in _load()]


def _match(p, need_edit=False):
    for g in _load():
        if _inside(p, g["path"]) and (g["mode"] == "edit" or not need_edit):
            return g
    return None


def can_read(p):
    with _LOCK:
        return _match(p) is not None and not permissions.is_secret(p)


def can_edit(p):
    with _LOCK:
        return (_match(p, need_edit=True) is not None and not permissions.is_secret(p)
                and not permissions.is_system(p))


def problem(p, mode):
    """Why this can't be granted, or None."""
    p = _norm(p)
    if not p.exists():
        return f"{p} doesn't exist. Check the name (I can search for it with files find)."
    if permissions.is_secret(p):
        return "That's a password, key or login store. I don't go in there, even with permission."
    parts = p.parts
    if mode == "edit":
        if len(parts) <= 1:
            return "That's a whole drive. Pick the specific folder you want me working in."
        if permissions.is_system(p):
            return "That's one of Windows' own folders. I can read it, but I won't edit in there."
        if p == _norm(config.HOME):
            return "That's your whole user folder. Pick the specific folder you want me working in."
    return None


def grant(path, mode, confirm):
    """confirm(title, detail, category) -> bool. Returns a sentence."""
    mode = "edit" if str(mode or "").lower() in ("edit", "write", "full", "change") else "read"
    p = _norm(path)
    why = problem(p, mode)
    if why:
        return why
    with _LOCK:
        cur = _match(p, need_edit=(mode == "edit"))
    if cur and _norm(cur["path"]) == p:
        return f"I already have {cur['mode']} access to {p}."
    what = "folder" if p.is_dir() else "file"
    if mode == "edit":
        title = f"Let him edit in {p.name or p}"
        detail = (f"{p}\n\nHe can create, change, move, copy and rename files in this {what} without asking each time. "
                  "Deleting still asks. Passwords and keys stay off-limits. Remove it any time in the System panel.")
    else:
        title = f"Let him read {p.name or p}"
        detail = (f"{p}\n\nHe can look at and read the files in this {what} (nothing is changed). "
                  "Remove it any time in the System panel.")
    if not confirm(title, detail, None):
        return "DENIED"
    with _LOCK:
        data = _load()
        data[:] = [g for g in data if _norm(g["path"]) != p]
        data.append({"path": str(p), "mode": mode, "added": time.strftime("%Y-%m-%d %H:%M"),
                     "kind": what})
        _save()
    return (f"Done: I can {'read and edit' if mode == 'edit' else 'read'} {p} now"
            + (" (deleting still asks)." if mode == "edit" else "."))


def revoke(path):
    p = _norm(path)
    with _LOCK:
        data = _load()
        keep = [g for g in data if _norm(g["path"]) != p]
        if len(keep) == len(data):
            # "stop accessing my Projects folder": allow a name instead of a full path
            low = str(path or "").strip().lower()
            keep = [g for g in data if Path(g["path"]).name.lower() != low]
        if len(keep) == len(data):
            return f"I didn't have special access to {path}."
        gone = [g["path"] for g in data if g not in keep]
        data[:] = keep
        _save()
    return "Removed my access to " + ", ".join(gone) + "."


def describe():
    g = items()
    if not g:
        return ("No extra folders. I can read your user folder" + (" and your local drives" if config.READ_ANYWHERE else "")
                + ", and edit freely only in the Jarvis folder; anything else asks.")
    return "Folders you've let me into: " + "; ".join(f"{x['path']} ({x['mode']})" for x in g) + "."
