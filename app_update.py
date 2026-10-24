"""
Updates for the INSTALLED app (the Setup.exe build), through Velopack.

How it works for whoever uses him:
  * A few seconds after he starts (and every 6 hours), he quietly checks your GitHub releases page for
    a newer version and downloads it in the background (only the changed parts, when possible).
  * He tells you it's ready. "Update yourself" restarts into it right away (with the approval card);
    otherwise it installs itself the next time he starts.
  * Keys, voice models, memory and settings live outside the program folder, so updates never touch them.

Where updates come from: UPDATE_SOURCE, baked into each build by the GitHub workflow (update_source.txt),
or JARVIS_UPDATE_SOURCE in .env to override. Running from source (python jarvis.py) doesn't use this:
that still updates from a jarvis.zip in Downloads (updater.py).
"""
import os
import threading

import config

_LOCK = threading.Lock()
_STATE = {"um": None, "pending": None, "error": None}


def source():
    s = os.environ.get("JARVIS_UPDATE_SOURCE", "").strip()
    if s:
        return s
    try:
        return (config.RES_DIR / "update_source.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _manager():
    """The Velopack UpdateManager, or None when this copy wasn't installed with Setup.exe."""
    if _STATE["um"] is not None:
        return _STATE["um"]
    if not config.FROZEN or not source():
        return None
    try:
        import velopack
        src = source()
        if "github.com/" in src:
            token = os.environ.get("JARVIS_UPDATE_TOKEN") or None        # only needed for a private repo
            src = velopack.GithubSource(src.rstrip("/"), token, False)
        _STATE["um"] = velopack.UpdateManager(src)
    except Exception as e:                       # e.g. run straight from the build folder, not installed
        _STATE["error"] = f"{type(e).__name__}: {e}"
        print(f"[update] updates unavailable: {_STATE['error'][:200]}")
        return None
    return _STATE["um"]


def available():
    return _manager() is not None


def current_version():
    um = _manager()
    if um is not None:
        try:
            return str(um.get_current_version())
        except Exception:
            pass
    try:
        return (config.RES_DIR / "VERSION").read_text(encoding="utf-8").strip() or "0"
    except OSError:
        return "0"


def explain(e):
    """A sentence about why checking for updates failed, for the log and for 'update yourself'."""
    msg = f"{type(e).__name__}: {e}"
    if "404" in msg or "Not Found" in msg:
        return (f"the releases page at {source()} wasn't found. If that GitHub repo is private, installed copies "
                "can't see it: make it public, or publish releases to a public repo (RELEASING.md).")
    if "403" in msg or "rate limit" in msg.lower():
        return "GitHub is rate-limiting update checks from this network for the moment; it'll work again within the hour."
    return f"couldn't check {source()} ({msg[:160]})"


def pending_version():
    p = _STATE["pending"]
    return str(p.TargetFullRelease.Version) if p is not None else None


def pending_notes():
    p = _STATE["pending"]
    try:
        return (p.TargetFullRelease.NotesMarkdown or "").strip() if p is not None else ""
    except Exception:
        return ""


def check_and_download(progress=None):
    """Returns the new version once it's downloaded and ready, or None if he's up to date."""
    um = _manager()
    if um is None:
        return None
    with _LOCK:
        if _STATE["pending"] is not None:
            return pending_version()
        info = um.check_for_updates()
        if not info:
            return None
        if progress is not None:
            um.download_updates(info, progress)
        else:
            um.download_updates(info)
        _STATE["pending"] = info
        return pending_version()


def apply_and_restart():
    """Hand over to Velopack: it waits for this process to exit, swaps in the new version and starts it
    again. The caller must shut down right after (closing the window, releasing the mic)."""
    um = _manager()
    p = _STATE["pending"]
    if um is None or p is None:
        return False
    um.wait_exit_then_apply_updates(p, True, True, ["--after-update"])
    return True
