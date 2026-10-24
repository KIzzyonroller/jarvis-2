"""
"Is that app open, and has it finished loading?" before he does anything inside it.

The problem it fixes: "play X on Spotify" with Spotify closed used to launch Spotify and press buttons straight
away, while Spotify was still on its splash screen or its home page, so the click or the typing went nowhere.

  * windows_for(name)   the app's real windows right now (its own process, or a title naming it). Splash and
                        updater windows ("Discord Updater") don't count.
  * wait_ready(...)     after launching: wait for its window, then for its contents to stop changing (what a
                        screen reader sees settles down once the app has drawn its page). Gives up after a
                        timeout and says so instead of pretending.
  * ensure(name)        already open? use it. Not open (or only in the tray)? open it and wait until it's ready.
"""
import re
import sys
import time

# app -> its process names (when they don't simply match the app's name)
KNOWN = {
    "spotify": ("spotify.exe",),
    "discord": ("discord.exe", "discordptb.exe", "discordcanary.exe"),
    "apple music": ("applemusic.exe", "itunes.exe"),
    "itunes": ("itunes.exe",),
    "steam": ("steamwebhelper.exe", "steam.exe"),
    "chrome": ("chrome.exe",), "google chrome": ("chrome.exe",),
    "edge": ("msedge.exe",), "microsoft edge": ("msedge.exe",),
    "firefox": ("firefox.exe",), "brave": ("brave.exe",), "opera": ("opera.exe", "opera_gx.exe"),
    "opera gx": ("opera.exe", "opera_gx.exe"), "vivaldi": ("vivaldi.exe",),
    "vscode": ("code.exe",), "vs code": ("code.exe",), "visual studio code": ("code.exe",), "code": ("code.exe",),
    "visual studio": ("devenv.exe",),
    "whatsapp": ("whatsapp.exe", "whatsapp.root.exe"), "telegram": ("telegram.exe",), "slack": ("slack.exe",),
    "teams": ("ms-teams.exe", "teams.exe"), "microsoft teams": ("ms-teams.exe", "teams.exe"),
    "obs": ("obs64.exe", "obs32.exe"), "obs studio": ("obs64.exe", "obs32.exe"),
    "blender": ("blender.exe",), "notepad": ("notepad.exe",), "word": ("winword.exe",),
    "excel": ("excel.exe",), "powerpoint": ("powerpnt.exe",), "outlook": ("outlook.exe", "olk.exe"),
    "epic games": ("epicgameslauncher.exe",), "epic games launcher": ("epicgameslauncher.exe",),
    "battle.net": ("battle.net.exe",), "battlenet": ("battle.net.exe",), "ea": ("eadesktop.exe",),
    "ea app": ("eadesktop.exe",), "riot client": ("riotclientux.exe", "riot client.exe"),
    "unreal": ("unrealeditor.exe", "epicgameslauncher.exe"), "unreal engine": ("unrealeditor.exe",),
    "photoshop": ("photoshop.exe",), "premiere": ("adobe premiere pro.exe",), "vlc": ("vlc.exe",),
    "netflix": ("netflix.exe",), "file explorer": (), "explorer": (), "files": (),   # explorer.exe always runs
}
# link schemes that open an app (open_url makes sure the app is up before handing it the link)
SCHEMES = {
    "spotify": "spotify", "discord": "discord", "steam": "steam", "music": "apple music", "itms": "apple music",
    "itmss": "apple music", "msteams": "teams", "slack": "slack", "whatsapp": "whatsapp", "tg": "telegram",
    "vscode": "vscode", "epic": "epic games", "obsidian": "obsidian",
}
BROWSERS = {"chromehtml": "chrome", "msedgehtm": "edge", "firefoxurl": "firefox", "bravehtml": "brave",
            "operastable": "opera", "operagxstable": "opera gx", "vivaldihtm": "vivaldi"}
SPLASH_RE = re.compile(r"^(discord updater|updater|updating|loading|starting|splash|checking for updates|"
                       r"steam\s*-?\s*(login|sign in|updating)?$)", re.I)
NEVER = {"explorer.exe", "python.exe", "pythonw.exe", "jarvis.exe", "msedgewebview2.exe", "svchost.exe",
         "applicationframehost.exe", "searchhost.exe", "startmenuexperiencehost.exe", "textinputhost.exe"}
MIN_W, MIN_H = 200, 120


def _flat(s):
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def _key(name):
    return re.sub(r"\s+", " ", str(name or "").lower().strip().removesuffix(".exe")).strip()


def procs_for(name):
    """Process names that mean 'this app'. Empty tuple = can't tell from processes (go by window title)."""
    k = _key(name)
    if k in KNOWN:
        return KNOWN[k]
    f = _flat(k)
    return (f + ".exe",) if len(f) >= 3 else ()


def _proc_matches(pname, name):
    p = (pname or "").lower()
    if not p or p in NEVER:
        return False
    if p in procs_for(name):
        return True
    f = _flat(_key(name))
    base = _flat(p.removesuffix(".exe"))
    return _key(name) not in KNOWN and len(f) >= 4 and (base == f or base.startswith(f))


def _title_matches(title, name):
    """A window title that names the app: 'Spotify Premium', '#general | Server - Discord', 'Netflix'."""
    t = (title or "").lower()
    k = _key(name)
    if len(_flat(k)) < 3:
        return False
    return bool(re.search(r"(^|[\s\-|:])" + re.escape(k) + r"($|[\s\-|:])", t))


def running(name):
    """Is the app's process running at all (even with no window, in the tray)?"""
    try:
        import psutil
        return any(_proc_matches(p.info["name"], name) for p in psutil.process_iter(["name"]))
    except Exception:
        return False


def _pname(hwnd):
    try:
        import psutil
        import tools
        return psutil.Process(tools._wpid(hwnd)).name().lower()
    except Exception:
        return ""


def windows_for(name, extra_titles=()):
    """The app's real, usable windows right now (minimized ones count: they're loaded, just hidden).
    Biggest first."""
    import tools
    out = []
    for w in tools._windows():
        title = (w.title or "").strip()
        if not title or title in tools.SELF_TITLES or SPLASH_RE.match(title):
            continue
        minimized = bool(getattr(w, "isMinimized", False))
        if not minimized and (w.width < MIN_W or w.height < MIN_H):
            continue
        hwnd = getattr(w, "_hWnd", None)
        if _proc_matches(_pname(hwnd), name) or _title_matches(title, name) or any(
                _title_matches(title, t) for t in extra_titles if t):
            out.append(w)
    out.sort(key=lambda w: (bool(getattr(w, "isMinimized", False)), -(w.width * w.height)))
    return out


def has_window(name):
    """True / False, or None when it can't tell (window list unavailable)."""
    try:
        return bool(windows_for(name))
    except Exception:
        return None


def _control_count(w, limit=1500):
    """How much a screen reader can see in the window. Grows while the app loads, then holds steady."""
    import uiautomation as auto
    ctrl = auto.ControlFromHandle(getattr(w, "_hWnd", 0))
    if ctrl is None:
        return 0
    n = 0
    for _c, _d in auto.WalkControl(ctrl, maxDepth=30):
        n += 1
        if n >= limit:
            break
    return n


def _uia():
    try:
        import uiautomation  # noqa: F401
        return True
    except Exception:
        return False


class _Cpu:
    """How busy the app is (all its processes together, % of one core since the last look). Apps chew CPU while
    they load and go quiet once the page is drawn; a half-drawn loading screen can look 'still' but isn't quiet."""
    def __init__(self, w):
        self.procs = []
        try:
            import psutil
            pname = _pname(getattr(w, "_hWnd", None))
            if pname and pname not in NEVER:
                self.procs = [p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == pname]
            for p in self.procs:
                p.cpu_percent(None)                      # start the meter
        except Exception:
            self.procs = []

    def busy(self):
        total = 0.0
        for p in self.procs:
            try:
                total += p.cpu_percent(None)
            except Exception:
                pass
        return total


QUIET_CPU = 25.0      # % of one core


def settle(w, deadline, min_controls=8, appeared=None):
    """Wait until the window's contents stop changing and the app stops working hard. True if it settled
    before the deadline."""
    appeared = appeared or time.time()
    if getattr(w, "isMinimized", False):
        return True                                       # minimized = it was already running and loaded
    if not _uia():
        time.sleep(max(0.0, min(2.0, deadline - time.time())))   # can't look inside: give it a couple of seconds
        return True
    last = None
    steady = quiet_steady = 0
    cpu = _Cpu(w)
    while time.time() < deadline:
        try:
            n = _control_count(w)
        except Exception:
            n = -1
        if n < 0:                                         # this window can't be inspected: fall back to a short wait
            time.sleep(max(0.0, min(2.0, deadline - time.time())))
            return True
        quiet = cpu.busy() < QUIET_CPU
        if last is not None and n >= min_controls and abs(n - last) <= max(2, int(last * 0.04)):
            steady += 1
            quiet_steady = quiet_steady + 1 if quiet else 0
            # settled: still and quiet for two looks, or (an app that's always busy, like a launcher downloading
            # something) its screen hasn't changed for about five seconds
            if (quiet_steady >= 2 or steady >= 8) and time.time() - appeared >= 1.2:
                return True
        else:
            steady = quiet_steady = 0
        last = n
        time.sleep(0.6)
    return False


def wait_ready(name, before=(), timeout=25.0, extra_titles=()):
    """After launching: (window or None, 'ready' | 'loading' | 'no window').
    before = window handles that existed before the launch; any new window also counts as the app's."""
    import tools
    deadline = time.time() + timeout
    before = set(before or ())
    w = None
    while time.time() < deadline:
        wins = windows_for(name, extra_titles)
        if not wins and before:
            fresh = [x for x in tools._windows()
                     if getattr(x, "_hWnd", None) not in before and (x.title or "").strip() not in tools.SELF_TITLES
                     and not SPLASH_RE.match((x.title or "").strip()) and x.width >= MIN_W and x.height >= MIN_H
                     and _pname(getattr(x, "_hWnd", None)) not in NEVER]
            wins = sorted(fresh, key=lambda x: -(x.width * x.height))
        if wins:
            w = wins[0]
            break
        time.sleep(0.3)
    if w is None:
        return None, "no window"
    return w, ("ready" if settle(w, deadline, appeared=time.time()) else "loading")


def window_handles():
    try:
        import tools
        return {getattr(w, "_hWnd", None) for w in tools._windows()}
    except Exception:
        return set()


def ensure(name, front=False, timeout=25.0):
    """Make sure the app is open and loaded before acting in it. Returns (window or None, state, sentence).
    state: 'open' (was already open), 'ready' (opened it and it finished loading), 'loading' (opened, but still
    loading at the timeout), 'no window', 'failed' (couldn't open it), or 'unknown' (can't see windows here)."""
    import tools
    if not getattr(tools, "IS_WINDOWS", False):
        return None, "unknown", ""
    try:
        wins = windows_for(name)
    except Exception:                                    # can't see windows: don't guess, carry on as before
        return None, "unknown", ""
    if wins:
        w = wins[0]
        if front:
            tools._GUARD["id"] += 1
            tools._activate(w)
        return w, "open", f"{name} was already open."
    before = window_handles()
    out = tools._open_app_now(name, front=front)
    if not out.startswith("Opened"):
        return None, "failed", out
    label = re.sub(r"^Opened\s+", "", out.split(".")[0]).strip() or name
    w, state = wait_ready(name, before, timeout, extra_titles=(label,))
    if front and w is not None and not getattr(w, "isMinimized", False):
        tools._GUARD["id"] += 1
        tools._activate(w)
    return w, state, describe(label, state, timeout)


def describe(label, state, timeout=25):
    if state == "ready":
        return f"Opened {label}; it's loaded and ready."
    if state == "loading":
        return (f"Opened {label}, but it was still loading after {int(timeout)} seconds. Wait a moment and check "
                "it (screen tool) before doing anything in it.")
    if state == "no window":
        return (f"Started {label}, but no window showed up within {int(timeout)} seconds (it may have gone to the "
                "tray, or it's still starting). Check before doing anything in it.")
    return f"Opened {label}."


def default_browser():
    """'chrome', 'edge', 'firefox'... from Windows' https setting, or None."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice") as k:
            prog = winreg.QueryValueEx(k, "ProgId")[0]
    except Exception:
        return None
    p = _flat(prog)
    for k, v in BROWSERS.items():
        if p.startswith(k):
            return v
    return None


def app_for_link(url):
    """Which app a link opens: 'spotify' for spotify:..., the default browser for https://..., else None."""
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):", url or "")
    if not m:
        return None
    s = m.group(1).lower()
    if s in ("http", "https"):
        return default_browser()
    return SCHEMES.get(s)
