"""
Updating himself from a new jarvis.zip in your Downloads folder. This is for running FROM SOURCE
(python jarvis.py / run_jarvis.bat). The installed app updates through app_update.py instead.

"Jarvis, update yourself":
  1. Finds the newest jarvis zip in Downloads that's really him (has jarvis/jarvis.py and a VERSION
     newer than the running one). Anything else is ignored.
  2. Checks every file in it stays inside his folder (a booby-trapped zip can't write anywhere else).
  3. Backs up his current code to Documents\\Jarvis\\backups\\<version>.
  4. Copies the new files in. Your .env, the Python environment (.venv) and downloaded models are
     never touched. Your memory, reminders and settings live in
     Documents\\Jarvis, which an update doesn't touch either.
  5. Installs new Python packages if requirements.txt changed.
  6. Restarts.
"Jarvis, undo the update" puts the backup back the same way.
"""
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import config

KEEP = {".env"}                                   # never overwritten
SKIP_DIRS = {".venv", "models", "__pycache__", "backups", ".git"}
BACKUPS = config.JARVIS_DIR / "backups"
RESTART_CODE = 3                                                 # run_jarvis.bat closes quietly on this
RESTARTING = False                                               # set when an update restart is under way


def current_version():
    if config.FROZEN:
        import app_update
        return app_update.current_version()
    try:
        return (config.BASE_DIR / "VERSION").read_text(encoding="utf-8").strip() or "0"
    except OSError:
        return "0"


def _key(v):
    out = []
    for part in str(v).replace("-", ".").split("."):
        out.append(int(part) if part.isdigit() else 0)
    return out


def newer(a, b):
    return _key(a) > _key(b)


def downloads_dir():
    try:
        import tools
        d = tools._known_folders().get("downloads")
        if d:
            return Path(d)
    except Exception:
        pass
    return Path.home() / "Downloads"


def inspect(zip_path):
    """(version, root prefix) if this zip is a Jarvis package, else None."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
            for root in ("jarvis/", ""):
                if root + "jarvis.py" in names and root + "core.py" in names and root + "VERSION" in names:
                    return z.read(root + "VERSION").decode("utf-8", "replace").strip(), root
    except (zipfile.BadZipFile, OSError, KeyError):
        pass
    return None


def find_update(folder=None):
    """Newest Jarvis zip in Downloads that's newer than what's running: (path, version) or None."""
    folder = Path(folder) if folder else downloads_dir()
    try:
        zips = sorted(folder.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
    except OSError:
        return None
    cur = current_version()
    best = None
    for p in zips:
        if time.time() - p.stat().st_mtime > 60 * 86400:
            continue
        info = inspect(p)
        if info and newer(info[0], cur) and (best is None or newer(info[0], best[1])) and _is_safe(p, info[1]):
            best = (p, info[0])
    return best


def _safe_members(z, root):
    """Every entry under root, with a safe relative path. Raises on anything that tries to escape."""
    out = []
    for info in z.infolist():
        if not info.filename.startswith(root) or info.is_dir():
            continue
        rel = info.filename[len(root):]
        p = Path(rel)
        if not rel or p.is_absolute() or ".." in p.parts or ":" in rel or rel.startswith(("/", "\\")):
            raise ValueError(f"unsafe path in update: {info.filename!r}")
        if p.parts[0] in SKIP_DIRS or p.name in KEEP:
            continue
        out.append((info, p))
    return out


def _is_safe(zip_path, root):
    try:
        with zipfile.ZipFile(zip_path) as z:
            _safe_members(z, root)
        return True
    except (ValueError, zipfile.BadZipFile, OSError):
        print(f"[update] ignoring {Path(zip_path).name}: it tries to write outside the Jarvis folder")
        return False


def _code_files(base):
    for p in base.rglob("*"):
        rel = p.relative_to(base)
        if p.is_file() and rel.parts[0] not in SKIP_DIRS and p.name not in KEEP and p.suffix != ".pyc":
            yield rel


def backup():
    """Copy the running code to Documents/Jarvis/backups/<version>. Returns the folder."""
    dest = BACKUPS / f"{current_version()}-{time.strftime('%Y%m%d-%H%M%S')}"
    for rel in _code_files(config.BASE_DIR):
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config.BASE_DIR / rel, dest / rel)
    try:                                                     # keep the last 5
        old = sorted((p for p in BACKUPS.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)[5:]
        for p in old:
            shutil.rmtree(p, ignore_errors=True)
    except OSError:
        pass
    return dest


def apply(zip_path, log=print):
    """Install the update. Returns (new_version, needs_pip)."""
    info = inspect(zip_path)
    if not info:
        raise ValueError("That zip isn't a Jarvis update.")
    version, root = info
    with zipfile.ZipFile(zip_path) as z:
        members = _safe_members(z, root)
        tmp = Path(tempfile.mkdtemp(prefix="jarvis-update-"))
        try:
            for zi, rel in members:                          # unpack everything first: a broken zip changes nothing
                (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                with z.open(zi) as src, open(tmp / rel, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            req_old = config.BASE_DIR / "requirements.txt"
            needs_pip = (tmp / "requirements.txt").exists() and (
                not req_old.exists() or not filecmp.cmp(req_old, tmp / "requirements.txt", shallow=False))
            where = backup()
            log(f"[update] backed up {current_version()} to {where}")
            for _, rel in members:
                (config.BASE_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(tmp / rel, config.BASE_DIR / rel)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    log(f"[update] installed {version} ({len(members)} files)")
    return version, needs_pip


def latest_backup():
    try:
        dirs = sorted((p for p in BACKUPS.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return None
    return dirs[0] if dirs else None


def rollback(log=print):
    """Put the most recent backup back. Returns the version restored, or None."""
    src = latest_backup()
    if not src:
        return None
    for rel in _code_files(src):
        (config.BASE_DIR / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, config.BASE_DIR / rel)
    version = (src / "VERSION").read_text(encoding="utf-8").strip() if (src / "VERSION").exists() else "an earlier version"
    shutil.rmtree(src, ignore_errors=True)                 # used up: "undo" again goes one further back
    log(f"[update] rolled back to {version}")
    return version


def pip_install(log=print):
    py = config.BASE_DIR / ".venv" / "Scripts" / "python.exe"
    exe = str(py) if py.exists() else sys.executable.replace("pythonw.exe", "python.exe")
    r = subprocess.run([exe, "-m", "pip", "install", "-q", "-r", str(config.BASE_DIR / "requirements.txt")],
                       capture_output=True, text=True, timeout=900,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    log(f"[update] pip: exit {r.returncode} {r.stderr[-400:] if r.returncode else ''}")
    return r.returncode == 0


def restart_command():
    """How to start the new version: the same way this copy was started."""
    exe = Path(sys.executable)
    if config.FROZEN:                                       # the installed app: just start the program again
        return [str(exe), "--after-update"]
    if exe.name.lower() == "pythonw.exe":                   # started by Windows (no console): same, but no delay
        return [str(exe), str(config.BASE_DIR / "jarvis.py"), "--after-update"]
    bat = config.BASE_DIR / "run_jarvis.bat"
    if os.name == "nt" and bat.exists():                     # started from run_jarvis.bat: a fresh console window
        return ["cmd", "/c", "start", "", str(bat), "--after-update"]
    return [str(exe), str(config.BASE_DIR / "jarvis.py"), "--after-update"]


NEXT_ARGS = []        # extra arguments for the restarted copy (e.g. --calendar to come back as calendar mode)


def spawn_restart():
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    cmd = restart_command() + list(NEXT_ARGS)
    subprocess.Popen(cmd, cwd=str(config.BASE_DIR), close_fds=True, creationflags=flags)
