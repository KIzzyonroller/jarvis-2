"""
Duplicate finder: "find duplicate files", "how much space are duplicates wasting?", "clean up the duplicates".

Exact duplicates: same size, then the same content (checked by hashing, so two different files with the same
name are never confused). Photos also get a "looks the same" check (a tiny fingerprint of the picture), which
catches the same photo saved twice at different sizes or qualities; those are only ever suggested, never removed
automatically.

Which copy stays: the oldest one in the most "home-like" place (Pictures over Downloads, Documents over Desktop),
and never anything inside a folder Windows or an app needs. The rest go to the Recycle Bin, after you approve the
list, and "undo that" brings them back (for anything up to 200 MB).
"""
import hashlib
import os
import threading
import time
from collections import defaultdict
from pathlib import Path

import config

SKIP_DIRS = {"node_modules", ".git", "__pycache__", "appdata", "$recycle.bin", "windows", "program files",
             "program files (x86)", ".venv", "venv", "steamapps", "site-packages", ".cache"}
PHOTO = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".bmp"}
MIN_SIZE = 50 * 1024                    # ignore tiny files (icons, configs): not worth it, and risky
RANK = {"pictures": 0, "documents": 1, "videos": 1, "music": 1, "onedrive": 2, "desktop": 3, "downloads": 4}
LAST = {"groups": [], "similar": [], "at": 0}


def roots():
    h = config.HOME
    return [p for p in (h / "Downloads", h / "Desktop", h / "Documents", h / "Pictures", h / "Videos", h / "Music",
                        h / "OneDrive") if p.exists()]


def _walk(folder_list, deadline):
    for root in folder_list:
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d.lower() not in SKIP_DIRS and not d.startswith(".")]
            for f in fns:
                p = os.path.join(dp, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                if st.st_size >= MIN_SIZE:
                    yield p, st.st_size, st.st_mtime
            if time.time() > deadline:
                return


def _hash(path, first_only=False):
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as f:
        if first_only:
            h.update(f.read(65536))
        else:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    return h.hexdigest()


def _rank(path):
    parts = [x.lower() for x in Path(path).parts]
    for k, v in RANK.items():
        if k in parts:
            return v
    return 5


def _keeper(paths_mtimes):
    return sorted(paths_mtimes, key=lambda pm: (_rank(pm[0]), pm[1], len(pm[0])))[0][0]


def scan(folder=None, seconds=90):
    """Find exact duplicates (and similar photos). Returns (groups, wasted_bytes)."""
    deadline = time.time() + seconds
    folders = [Path(folder)] if folder else roots()
    by_size = defaultdict(list)
    for p, size, mt in _walk(folders, deadline):
        by_size[size].append((p, mt))
    groups = []
    for size, items in by_size.items():
        if len(items) < 2 or time.time() > deadline:
            continue
        quick = defaultdict(list)
        for p, mt in items:
            try:
                quick[_hash(p, True)].append((p, mt))
            except OSError:
                pass
        for same in quick.values():
            if len(same) < 2:
                continue
            full = defaultdict(list)
            for p, mt in same:
                try:
                    full[_hash(p)].append((p, mt))
                except OSError:
                    pass
            for g in full.values():
                if len(g) > 1:
                    keep = _keeper(g)
                    groups.append({"size": size, "keep": keep, "extra": [p for p, _ in g if p != keep]})
    groups.sort(key=lambda g: -g["size"] * len(g["extra"]))
    LAST.update(groups=groups, at=time.time())
    LAST["similar"] = _similar_photos(folders, deadline + 30)
    return groups, sum(g["size"] * len(g["extra"]) for g in groups)


def _dhash(path):
    from PIL import Image
    with Image.open(path) as im:
        im = im.convert("L").resize((9, 8))
        px = list(im.getdata())
    return sum(1 << i for i in range(64) if px[(i // 8) * 9 + i % 8] > px[(i // 8) * 9 + i % 8 + 1])


def _similar_photos(folders, deadline):
    """Same picture saved at different sizes or qualities. Suggestions only."""
    exact = {p for g in LAST["groups"] for p in [g["keep"]] + g["extra"]}
    fps = []
    for p, size, mt in _walk(folders, deadline):
        if Path(p).suffix.lower() in PHOTO and p not in exact and len(fps) < 4000:
            try:
                fps.append((p, _dhash(p), size))
            except Exception:
                pass
        if time.time() > deadline:
            break
    pairs, used = [], set()
    for i in range(len(fps)):
        if fps[i][0] in used:
            continue
        for j in range(i + 1, len(fps)):
            if fps[j][0] not in used and bin(fps[i][1] ^ fps[j][1]).count("1") <= 3:
                big, small = (fps[i], fps[j]) if fps[i][2] >= fps[j][2] else (fps[j], fps[i])
                pairs.append({"keep": big[0], "maybe": small[0], "size": small[2]})
                used |= {fps[i][0], fps[j][0]}
                break
    return pairs[:40]


def _fmt(b):
    return f"{b / 1e9:.1f} GB" if b >= 1e9 else f"{b / 1e6:.0f} MB" if b >= 1e6 else f"{b // 1024} KB"


def _short(p):
    return str(p).replace(str(config.HOME), "~")


def report(folder=None):
    groups, wasted = scan(folder)
    sim = LAST["similar"]
    if not groups and not sim:
        return "No duplicates found. Nice and tidy."
    rows = [{"name": Path(g["keep"]).name, "copies": len(g["extra"]) + 1, "size": _fmt(g["size"] * len(g["extra"])),
             "where": [_short(Path(p).parent) for p in g["extra"]][:3]} for g in groups[:12]]
    try:
        import pulls
        pulls.pull("dupes", {"wasted": _fmt(wasted), "groups": len(groups), "files": sum(len(g["extra"]) for g in groups),
                             "rows": rows, "similar": len(sim)}, id="dupes", title="Duplicates", ttl=300, focus=True, auto=False)
    except Exception as e:
        print(f"[dupes] panel: {e}")
    top = "; ".join(f"{r['name']} x{r['copies']} ({r['size']})" for r in rows[:5])
    return (f"{sum(len(g['extra']) for g in groups)} duplicate files in {len(groups)} groups, wasting {_fmt(wasted)}. "
            f"Biggest: {top}." + (f" Plus {len(sim)} photos that look like smaller copies of others (I'd only remove "
                                  f"those if you say so)." if sim else "") +
            " Say 'clean them up' to send the extra copies to the Recycle Bin (one approval, and undo works).")


def clean(confirm, include_similar=False):
    """Extra copies to the Recycle Bin, after ONE approval card listing them."""
    if not LAST["groups"] and not (include_similar and LAST["similar"]):
        return "Run the duplicate check first."
    if time.time() - LAST["at"] > 3600:
        return "That check is over an hour old; run it again first so I don't remove something that changed."
    victims = [(p, g["size"], g["keep"]) for g in LAST["groups"] for p in g["extra"]]
    if include_similar:
        victims += [(s["maybe"], s["size"], None) for s in LAST["similar"]]
    victims = [v for v in victims if os.path.exists(v[0])]
    if not victims:
        return "Nothing left to clean."
    total = sum(v[1] for v in victims)
    detail = "\n".join(_short(v[0]) for v in victims[:40]) + (f"\n...and {len(victims) - 40} more" if len(victims) > 40 else "")
    if not confirm(f"Send {len(victims)} duplicate files ({_fmt(total)}) to the Recycle Bin", detail):
        return "Okay, left them all."
    from send2trash import send2trash
    import undo
    n, done = 0, []
    for p, size, keep in victims:
        try:
            send2trash(p)
            done.append({"path": p, "keep": keep})
            n += 1
        except Exception as e:
            print(f"[dupes] {p}: {e}")
    if done:      # undo copies each one back from the copy that stayed (no extra disk used meanwhile)
        undo.record("dupes", f"removed {n} duplicate files", files=done)
    LAST["groups"], LAST["similar"] = [], []
    return f"Sent {n} duplicate files ({_fmt(total)}) to the Recycle Bin. The originals are untouched."
