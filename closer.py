"""
Closing apps properly ("close Discord", "close Steam and Chrome", "close Minecraft").

What used to go wrong: it matched process names only, sent one polite close and said "closed" whether or not
anything happened. Discord and Steam just hid in the tray, a "save changes?" prompt was missed, and apps known by
another name (Word = winword.exe, Teams = ms-teams.exe, a game whose window says "Minecraft") weren't found.

Now:
  1. Find the app by its name, its process names (Steam is steam.exe AND steamwebhelper.exe) or its window title.
  2. Close its windows the normal way (like clicking X), so apps can save and shut down cleanly.
  3. Check it actually went. If a window is still up, it's usually asking something (unsaved work): say so and
     don't force anything. If it closed its windows but kept running in the tray, finish it off (no windows
     means nothing unsaved is open). Steam gets its own clean shutdown.
  4. Force close (killing it outright) still needs your approval.
Never touches Windows itself (explorer, system processes) or Jarvis.
"""
import difflib
import os
import re
import subprocess
import sys
import time

import app_ready

WM_CLOSE = 0x0010
PROTECTED = {
    "system", "system idle process", "csrss.exe", "winlogon.exe", "lsass.exe", "services.exe", "svchost.exe",
    "smss.exe", "wininit.exe", "dwm.exe", "explorer.exe", "python.exe", "pythonw.exe", "registry", "fontdrvhost.exe",
    "msedgewebview2.exe", "jarvis.exe", "update.exe", "searchhost.exe", "startmenuexperiencehost.exe",
    "shellexperiencehost.exe", "textinputhost.exe", "sihost.exe", "ctfmon.exe", "runtimebroker.exe", "taskhostw.exe",
    "conhost.exe", "audiodg.exe", "spoolsv.exe", "lockapp.exe", "securityhealthsystray.exe", "msmpeng.exe",
}
UWP_HOST = "applicationframehost.exe"
BROWSERS = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "opera_gx.exe", "vivaldi.exe"}
# Apps that keep running in the tray after their window closes. Quitting them fully when asked is safe: once
# their windows are gone there's nothing unsaved to lose.
TRAY = {"spotify", "discord", "steam", "teams", "microsoft teams", "slack", "epic games", "epic games launcher",
        "battle.net", "battlenet", "ea", "ea app", "riot client", "obs", "obs studio", "whatsapp", "telegram",
        "onedrive", "dropbox", "zoom", "skype", "ubisoft connect", "gog galaxy", "nvidia broadcast", "medal",
        "overwolf", "logitech g hub", "razer synapse", "icue", "wallpaper engine", "steelseries gg", "apple music",
        "itunes", "signal", "messenger", "notion", "docker desktop"}
EXTRA = {   # more apps whose process names differ from what people call them
    "ubisoft connect": ("upc.exe", "uplaypclient.exe"), "gog galaxy": ("galaxyclient.exe",),
    "onedrive": ("onedrive.exe",), "dropbox": ("dropbox.exe",), "zoom": ("zoom.exe",), "skype": ("skype.exe",),
    "task manager": ("taskmgr.exe",), "calculator": ("calculatorapp.exe", "calc.exe"),
    "settings": ("systemsettings.exe",), "photos": ("photos.exe", "microsoft.photos.exe"),
    "medal": ("medal.exe",), "overwolf": ("overwolf.exe",), "logitech g hub": ("lghub.exe", "lghub_agent.exe"),
    "razer synapse": ("razer synapse 3.exe", "razer synapse service process.exe"), "icue": ("icue.exe",),
    "wallpaper engine": ("wallpaper32.exe", "wallpaper64.exe"), "steelseries gg": ("steelseriesgg.exe",),
    "signal": ("signal.exe",), "messenger": ("messenger.exe",), "notion": ("notion.exe",),
    "docker desktop": ("docker desktop.exe",), "nvidia broadcast": ("nvidia broadcast.exe",),
    "paint": ("mspaint.exe",), "media player": ("microsoft.media.player.exe", "wmplayer.exe"),
    "minecraft launcher": ("minecraft.exe", "minecraftlauncher.exe"), "roblox": ("robloxplayerbeta.exe", "robloxstudiobeta.exe"),
    "fortnite": ("fortniteclient-win64-shipping.exe",), "valorant": ("valorant-win64-shipping.exe",),
    "league of legends": ("league of legends.exe", "leagueclient.exe", "leagueclientux.exe"),
    "file explorer": (), "explorer": (), "files": (),
}
EXPLORER_NAMES = {"file explorer", "explorer", "files", "folders", "folder windows"}


def _key(name):
    k = re.sub(r"\s+", " ", str(name or "").lower().strip())
    k = re.sub(r"^(the|my)\s+", "", k)
    k = re.sub(r"\s+(app|application|program|window|windows|launcher client)$", "", k)
    return k.removesuffix(".exe").strip()


def _flat(s):
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def _exes_for(key):
    if key in EXTRA:
        return EXTRA[key]
    return app_ready.procs_for(key)


def _self_pids():
    import psutil
    out = {os.getpid()}
    try:
        p = psutil.Process()
        out |= {c.pid for c in p.children(recursive=True)}
        par = p.parent()
        if par is not None and par.name().lower() in ("jarvis.exe", "update.exe"):
            out.add(par.pid)
    except Exception:
        pass
    return out


def _procs():
    import psutil
    out = []
    for p in psutil.process_iter(["pid", "ppid", "name"]):
        try:
            out.append((p.info["pid"], p.info["ppid"], (p.info["name"] or "").lower()))
        except Exception:
            continue
    return out


def _windows():
    """Visible top-level windows: (hwnd, title, pid, pname)."""
    import tools
    out = []
    for w in tools._windows():
        h = getattr(w, "_hWnd", None)
        try:
            pid = tools._wpid(h)
        except Exception:
            continue
        out.append((h, (w.title or "").strip(), pid, app_ready._pname(h)))
    return out


class Target:
    def __init__(self, label):
        self.label = label
        self.pids = set()          # processes to close
        self.windows = []          # (hwnd, title) to close the normal way
        self.tray_ok = False       # fine to finish it off if it hides in the tray
        self.explorer_only = False
        self.tabs = []             # (hwnd, title) browser windows whose CURRENT tab is the thing: close just that tab


def find(name):
    """What to close for a name. Returns (Target or None, suggestions)."""
    key = _key(name)
    if not key:
        return None, []
    me = _self_pids()
    procs = [(pid, ppid, n) for pid, ppid, n in _procs() if pid not in me]
    wins = [w for w in _windows() if w[2] not in me]
    t = Target(name.strip())

    if key in EXPLORER_NAMES:                         # never kill explorer.exe; close its folder windows instead
        t.explorer_only = True
        t.windows = [(h, title) for h, title, pid, pn in wins if pn == "explorer.exe"]
        t.label = "File Explorer windows"
        return (t if t.windows else None), []

    exes = {e.lower() for e in _exes_for(key)}
    flat = _flat(key)
    exact = {pid for pid, _, n in procs if n in exes and n not in PROTECTED}
    if not exact and len(flat) >= 3:
        exact = {pid for pid, _, n in procs if _flat(n.removesuffix(".exe")) == flat and n not in PROTECTED}
    loose = set()
    if not exact and len(flat) >= 4:
        loose = {pid for pid, _, n in procs if flat in _flat(n.removesuffix(".exe")) and n not in PROTECTED}
    titled = [(h, title, pid, pn) for h, title, pid, pn in wins if app_ready._title_matches(title, key)]

    chosen = exact or loose
    names = {n for pid, _, n in procs if pid in chosen}
    chosen |= {pid for pid, _, n in procs if n in names}           # whole families: Steam's helpers, Discord's renderers
    distinct = {_nice(n) for n in names}
    if not exact and len(distinct) > 3:
        t.label = "?"
        return t, sorted(distinct)
    by_pid = {}
    for h, title, pid, pn in wins:
        by_pid.setdefault(pid, []).append((h, title))
    for h, title, pid, pn in titled:
        if pid in chosen or pn in PROTECTED and pn != UWP_HOST:
            continue
        if exact:
            continue                                  # "close chrome" means Chrome, not a window that mentions it
        if pn != UWP_HOST and all(app_ready._title_matches(tt, key) for _, tt in by_pid.get(pid, [])):
            chosen.add(pid)                           # its only window(s) are this: it's the app (a game, say)
            names.add(pn)
        elif pn in BROWSERS:
            t.tabs.append((h, title))                 # a website: close its tab, not the whole browser window
        else:
            t.windows.append((h, title))              # one window of something bigger: close just that
    if not chosen and not t.windows and not t.tabs:
        running = sorted({_nice(pn) for _, _, pid, pn in wins if pn and pn not in PROTECTED})
        return None, difflib.get_close_matches(key, [r.lower() for r in running], n=3, cutoff=0.5) or running[:8]
    t.pids = chosen
    t.windows += [(h, title) for h, title, pid, pn in wins if pid in chosen]
    tray_exes = {e for k in TRAY for e in _exes_for(k)}
    t.tray_ok = key in TRAY or any(n in tray_exes for n in names)
    if not exact and len(distinct) == 1 and not titled:
        t.label = next(iter(distinct))
    return t, []


_FRIENDLY = None


def _nice(pname):
    """'winword.exe' -> 'Word', 'steamwebhelper.exe' -> 'Steam', 'spotify.exe' -> 'Spotify'."""
    global _FRIENDLY
    if _FRIENDLY is None:
        _FRIENDLY = {}
        for k, exes in list(app_ready.KNOWN.items()) + list(EXTRA.items()):
            for e in exes:
                cur = _FRIENDLY.get(e)
                if cur is None or len(k) > len(cur):
                    _FRIENDLY[e] = k
    p = (pname or "").lower()
    if p in _FRIENDLY:
        return " ".join(w if w.isupper() or "." in w else w.capitalize() for w in _FRIENDLY[p].split())
    base = re.sub(r"(?i)\.exe$", "", pname or "").replace("_", " ").strip() or pname
    return base[:1].upper() + base[1:]


def _post_close(hwnd):
    """True if Windows accepted the close message. False when it's refused, which for a window that exists means
    it belongs to an app running as administrator (Windows blocks normal apps from closing those)."""
    try:
        import tools
        _, _, u, _ = tools._win()
        return bool(u.PostMessageW(hwnd, WM_CLOSE, 0, 0))
    except Exception:
        return False


def _alive(pids):
    import psutil
    out = set()
    for pid in pids:
        try:
            if psutil.Process(pid).status() != "zombie":
                out.add(pid)
        except Exception:
            continue
    return out


def _taskkill(pids, force):
    """End process trees. Returns (ok, denied)."""
    import psutil
    roots = set()
    for pid in pids:
        try:
            par = psutil.Process(pid).ppid()
        except Exception:
            continue
        if par not in pids:
            roots.add(pid)
    denied = False
    for pid in roots or pids:
        cmd = ["taskkill", "/PID", str(pid), "/T"] + (["/F"] if force else [])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if "denied" in (r.stdout + r.stderr).lower():
                denied = True
        except Exception:
            pass
    return denied


def _steam_shutdown(pids):
    import psutil
    for pid in pids:
        try:
            p = psutil.Process(pid)
            if p.name().lower() == "steam.exe":
                subprocess.Popen([p.exe(), "-shutdown"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                return True
        except Exception:
            continue
    return False


def _wait_gone(pids, windows, secs):
    """Poll until the processes have exited (or, for window-only targets, the windows are gone)."""
    end = time.time() + secs
    while time.time() < end:
        if pids and not _alive(pids):
            return True
        if not pids and not _open_windows(windows):
            return True
        time.sleep(0.25)
    return False


def _open_windows(windows):
    hs = {h for h, _, _, _ in _windows()}
    return [(h, t) for h, t in windows if h in hs]


def _windows_of(pids):
    return [(h, t) for h, t, pid, _ in _windows() if pid in pids]


def close(name, force=False, confirm=None, wait=7.0):
    """One app. Returns a sentence starting with: Closed / Force-closed / ... isn't running / Several apps match /
    ... is asking / ... is running as administrator / ... is still running."""
    import tools
    t, suggest = find(name)
    if t is None:
        tail = f" Running now: {', '.join(suggest)}." if suggest else ""
        return f"{name.strip()} isn't running.{tail}"
    if t.label == "?":
        return f"Several apps match '{name}': {', '.join(suggest)}. Which one?"
    label = t.label
    if force and t.pids:
        if confirm is not None and not confirm(f"Force-close {label}", "Any unsaved work in it will be lost.",
                                               "force_close"):
            return tools.DENIED
        denied = _taskkill(t.pids, force=True)
        if _wait_gone(t.pids, [], 4):
            return f"Force-closed {label}."
        return (f"{label} is running as administrator, so Windows won't let me close it. Close it yourself "
                "(or from Task Manager)." if denied else f"{label} is still running even after forcing it.")

    if t.tabs and not t.pids and not t.windows:
        return _close_tabs(t.tabs)
    posted = [_post_close(h) for h, _ in t.windows]   # like clicking X on each window
    if posted and not any(posted):
        return (f"{label} is running as administrator, so Windows won't let me close it. Close it yourself "
                "(or from Task Manager).")
    if not t.pids:                                 # Store apps, folder windows, one window of a bigger app
        if _wait_gone([], t.windows, wait):
            what = t.windows[0][1] if len(t.windows) == 1 and not t.explorer_only else label
            return f"Closed {what}."
        left = _open_windows(t.windows)
        return f"{label} is asking something before it closes ('{left[0][1]}'). Answer it, or ask me to force close."

    had_windows = bool(t.windows)
    if _wait_gone(t.pids, t.windows, wait if had_windows else 0.5):
        return f"Closed {label}."
    alive = _alive(t.pids)
    left = _windows_of(alive)
    if left:                                       # a window is still up: usually "save changes?"
        return (f"{label} is asking something before it closes ('{left[0][1]}'), probably about unsaved work. "
                "Answer it, or ask me to force close (that loses unsaved work).")
    # no windows left, but it's still running: in the tray, or a background app
    if t.tray_ok or had_windows:
        how = "quit it from the tray too"
        if _steam_shutdown(alive) and _wait_gone(alive, [], 10):
            return f"Closed {label} (Steam shut itself down properly)."
        denied = _taskkill(alive, force=False)
        if not _wait_gone(alive, [], 3):
            denied = _taskkill(_alive(alive), force=True) or denied
        if _wait_gone(alive, [], 4):
            return f"Closed {label} (it was still running in the tray, so I {how})."
        if denied:
            return (f"{label} is running as administrator, so Windows won't let me close it. Close it yourself "
                    "(or from Task Manager).")
        return f"{label} closed its windows but is still running in the background. Ask me to force close it."
    denied = _taskkill(alive, force=False)          # a background app with no window: ask nicely once
    if _wait_gone(alive, [], 4):
        return f"Closed {label}."
    if denied:
        return f"{label} is running as administrator, so Windows won't let me close it."
    return (f"{label} is running in the background with no window and didn't close when asked. Force closing it "
            "needs your OK; ask me to force close it if you're sure.")


def _close_tabs(tabs):
    """Close the showing tab in each browser window (Ctrl+W), checking the title first so we never close the wrong one."""
    import pyautogui
    import tools
    done = []
    for h, title in tabs[:3]:
        w = next((x for x in tools._windows() if getattr(x, "_hWnd", None) == h), None)
        if w is None:
            continue
        tools._GUARD["id"] += 1
        tools._activate(w)
        if not tools._wait_front(w, timeout=2.0) or (tools._wtitle(h) or "").strip() != title:
            continue
        pyautogui.hotkey("ctrl", "w")
        time.sleep(0.4)
        done.append(re.sub(r"\s+[-\u2013\u2014|]\s+(Google Chrome|Microsoft\u200b? Edge|Mozilla Firefox|Brave|Opera|Vivaldi).*$", "", title))
    if not done:
        return "Couldn't get to that tab to close it (the browser didn't come to the front)."
    return "Closed the " + " and ".join(f"'{d}'" for d in done) + " tab" + ("s" if len(done) > 1 else "") + "."


def close_many(names, force=False, confirm=None):
    """'Discord, Steam and Chrome' -> each one, one line each."""
    parts = [p for p in re.split(r"\s*(?:,|\band\b|&|\+)\s*", str(names or "")) if p.strip()]
    if len(parts) <= 1:
        return close(names, force, confirm)
    return " ".join(close(p, force, confirm) for p in parts)


def running_apps(limit=25):
    """What's open: apps with windows (and tray apps people care about), with memory. For 'what's running'."""
    import psutil
    me = _self_pids()
    with_win = []
    for h, title, pid, pn in _windows():
        if pid in me or not pn or pn in PROTECTED:
            continue
        n = (title or "Store app") if pn == UWP_HOST else _nice(pn)
        if n not in with_win:
            with_win.append(n)
    mem = {}
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            n = _nice((p.info["name"] or "").lower())
            mem[n] = mem.get(n, 0) + (p.info["memory_info"].rss if p.info["memory_info"] else 0)
        except Exception:
            continue
    tray_names = {_nice(e) for k in TRAY for e in _exes_for(k)}
    tray = sorted(n for n in mem if n in tray_names and n not in with_win)
    rows = sorted(with_win, key=lambda n: -mem.get(n, 0))[:limit]
    fmt = lambda n: f"{n} ({mem[n] / 1e6:.0f} MB)" if mem.get(n) else n
    out = "Open apps: " + (", ".join(fmt(n) for n in rows) if rows else "none") + "."
    if tray:
        out += " In the tray: " + ", ".join(fmt(n) for n in tray[:12]) + "."
    return out
