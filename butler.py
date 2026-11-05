"""
File butler: keeps Downloads (or Desktop) from turning into a landfill.

  * report: what's in there by type, how much space, and what looks safe to clear (installers and archives you
    downloaded over a month ago, "file (1).zip" style duplicates).
  * tidy: sorts the loose files into folders (Installers, Archives, Pictures, Videos, Music, Documents, Code,
    3D, Other) inside the same folder. Asks first, shows how many files move, and can be undone ("undo the tidy").
  * clean: sends the old installers / archives and the duplicates to the Recycle Bin (never deletes for good).
    Always asks first, with the list and total size. You can still restore them from the Recycle Bin.

It never touches files still downloading or changed in the last 10 minutes, folders, hidden/system files, or
anything that looks like a password store or key. Only folders inside your user folder are allowed.
"""
import json
import re
import shutil
import time
from collections import defaultdict
from pathlib import Path

import config

CATS = {
    "Installers": {".exe", ".msi", ".msix", ".msixbundle", ".appx", ".appxbundle"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".iso"},
    "Pictures": {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".svg", ".psd", ".avif"},
    "Videos": {".mp4", ".mkv", ".mov", ".avi", ".webm", ".wmv", ".m4v"},
    "Music": {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac", ".opus"},
    "Documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".ppt", ".pptx", ".txt", ".md", ".rtf", ".odt", ".epub"},
    "Code": {".py", ".js", ".ts", ".json", ".html", ".css", ".cpp", ".c", ".h", ".cs", ".java", ".ps1", ".bat", ".sh", ".lua"},
    "3D": {".blend", ".fbx", ".obj", ".glb", ".gltf", ".stl", ".uasset", ".usd", ".usdz", ".3mf"},
}
PARTIAL = {".crdownload", ".part", ".partial", ".tmp", ".download", ".opdownload"}
OLD_DAYS = 30
DUPE = re.compile(r"^(.*?)\s*\((\d+)\)(\.[^.]+)?$")
UNDO = "butler_undo.json"


def _cat(p):
    ext = p.suffix.lower()
    for name, exts in CATS.items():
        if ext in exts:
            return name
    return "Other"


def human(n):
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("bytes", "KB") else f"{n:.1f} {unit}"
        n /= 1024


def folder(name=None):
    """Downloads by default; Desktop or any folder inside your user folder. None if not allowed."""
    n = (name or "downloads").strip().strip('"')
    low = n.lower()
    if low in ("downloads", "download", ""):
        p = config.HOME / "Downloads"
    elif low == "desktop":
        p = config.HOME / "Desktop"
        if not p.exists():
            p = config.HOME / "OneDrive" / "Desktop"
    else:
        p = Path(n).expanduser()
        if not p.is_absolute():
            p = config.HOME / n
    try:
        p = p.resolve()
        home = config.HOME.resolve()
    except OSError:
        return None
    if p == home or home not in p.parents or not p.is_dir():
        return None
    import permissions
    if permissions.is_secret(p) or "appdata" in [x.lower() for x in p.parts]:
        return None
    return p


def _files(root):
    """Loose files you can safely touch, with (size, modified time)."""
    import permissions
    out = []
    now = time.time()
    for f in root.iterdir():
        try:
            if not f.is_file() or f.name.startswith(".") or f.name.lower() in ("desktop.ini", "thumbs.db"):
                continue
            if f.suffix.lower() in PARTIAL or permissions.is_secret(f):
                continue
            st = f.stat()
            if getattr(st, "st_file_attributes", 0) & (0x2 | 0x4):          # hidden / system
                continue
            if now - st.st_mtime < 600:                                  # still downloading, or just saved
                continue
            out.append((f, st.st_size, st.st_mtime))
        except OSError:
            continue
    return out


def _clearable(files):
    """(old installers/archives, duplicates) - the stuff 'clean' would recycle."""
    now = time.time()
    names = {f.name.lower() for f, _, _ in files}
    old, dupes = [], []
    for f, size, mt in files:
        m = DUPE.match(f.name)
        if m and ((m.group(1) + (m.group(3) or "")).lower() in names):
            dupes.append((f, size))
        elif _cat(f) in ("Installers", "Archives") and now - mt > OLD_DAYS * 86400:
            old.append((f, size))
    return old, dupes


def report(name=None):
    root = folder(name)
    if root is None:
        return None, "That folder isn't one I'm allowed to tidy (Downloads, Desktop, or a folder in your user folder)."
    files = _files(root)
    by = defaultdict(lambda: [0, 0])
    for f, size, _ in files:
        by[_cat(f)][0] += 1
        by[_cat(f)][1] += size
    old, dupes = _clearable(files)
    total = sum(s for _, s, _ in files)
    info = {"folder": str(root), "files": len(files), "size": total,
            "by": {k: {"n": v[0], "size": v[1]} for k, v in sorted(by.items(), key=lambda kv: -kv[1][1])},
            "old": len(old), "old_size": sum(s for _, s in old), "dupes": len(dupes), "dupe_size": sum(s for _, s in dupes)}
    parts = ", ".join(f"{v['n']} {k.lower()} ({human(v['size'])})" for k, v in list(info["by"].items())[:6])
    text = f"{root.name}: {len(files)} loose files, {human(total)}. {parts}."
    if old or dupes:
        text += (f" Safe to clear: {len(old)} installers/archives older than {OLD_DAYS} days ({human(info['old_size'])})"
                 f" and {len(dupes)} duplicate downloads ({human(info['dupe_size'])}).")
    return info, text


def tidy(name=None, confirm=None):
    root = folder(name)
    if root is None:
        return "That folder isn't one I'm allowed to tidy."
    files = _files(root)
    if not files:
        return f"{root.name} has no loose files to sort."
    plan = defaultdict(list)
    for f, _, _ in files:
        plan[_cat(f)].append(f)
    detail = "\n".join(f"{k}: {len(v)} file{'s' if len(v) != 1 else ''}" for k, v in plan.items())
    if confirm and not confirm(f"Sort {len(files)} files in {root.name} into folders", detail + "\n\nYou can undo this."):
        return "Okay, left it as it is."
    moved = []
    for cat, fs in plan.items():
        dest = root / cat
        dest.mkdir(exist_ok=True)
        for f in fs:
            target = dest / f.name
            i = 2
            while target.exists():
                target = dest / f"{f.stem} ({i}){f.suffix}"
                i += 1
            try:
                shutil.move(str(f), str(target))
                moved.append([str(f), str(target)])
            except OSError as e:
                print(f"[butler] couldn't move {f.name}: {e}")
    (config.JARVIS_DIR / UNDO).write_text(json.dumps({"t": time.time(), "moves": moved}), encoding="utf-8")
    return f"Sorted {len(moved)} files in {root.name} into {len(plan)} folders. Say \"undo the tidy\" to put them back."


def undo():
    p = config.JARVIS_DIR / UNDO
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return "There's no tidy to undo."
    back = 0
    for src, dst in reversed(d.get("moves", [])):
        s, t = Path(src), Path(dst)
        if t.exists() and not s.exists():
            try:
                shutil.move(str(t), str(s))
                back += 1
            except OSError:
                pass
    for src, dst in d.get("moves", []):                    # drop folders the tidy made, if they're empty now
        try:
            Path(dst).parent.rmdir()
        except OSError:
            pass
    p.unlink(missing_ok=True)
    return f"Put {back} files back where they were."


def clean(name=None, confirm=None):
    root = folder(name)
    if root is None:
        return "That folder isn't one I'm allowed to clean."
    old, dupes = _clearable(_files(root))
    items = old + dupes
    if not items:
        return f"Nothing in {root.name} looks safe to clear (no installers or archives older than {OLD_DAYS} days, no duplicates)."
    size = sum(s for _, s in items)
    names = "\n".join(f.name for f, _ in items[:25]) + (f"\n...and {len(items) - 25} more" if len(items) > 25 else "")
    if confirm is None or not confirm(f"Send {len(items)} files ({human(size)}) from {root.name} to the Recycle Bin",
                                      names + "\n\nThey stay in the Recycle Bin until you empty it."):
        return "Okay, nothing cleared."
    from send2trash import send2trash
    done = 0
    for f, _ in items:
        try:
            send2trash(str(f))
            done += 1
        except Exception as e:
            print(f"[butler] couldn't recycle {f.name}: {e}")
    return f"Sent {done} files ({human(size)}) to the Recycle Bin. You can still restore them from there."


def nudge_line():
    """For the weekly check-in: a line if Downloads has a lot to clear, else None."""
    info, _ = report("downloads")
    if not info:
        return None, None
    clear = info["old_size"] + info["dupe_size"]
    if clear < 1.5 * 2**30 and info["files"] < 120:
        return None, None
    line = (f"Your Downloads folder has {human(clear)} of old installers, archives and duplicates"
            + (f", and {info['files']} loose files" if info["files"] >= 120 else "")
            + ". Want me to tidy it up? I'll show you everything first.")
    return line, {"title": "Downloads", "big": human(clear), "text": "safe to clear"}
