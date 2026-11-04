"""
The desktop characters, from the main app's side. The figures themselves live in their own process
(buddies_qt.py); this starts it when "Show them on the desktop" is on, tells it what's going on (who's talking,
listening, the voice envelope, the options), and handles the bits that need the main app:

  * opening apps: when he opens one, the figure starts reaching out right away, this watches for the app's window
    to show up, then sends its position so the entrance plays exactly over it (or calls it off after 8 seconds)
  * "Just him" mode: the main window stays hidden; when he needs to show you something (an approval card, or you
    Ctrl+double-click him) he throws it open the same way
  * clones, and the merged one (the secret code sets the "merged" option)
"""
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time

import config
import prefs

PASS_OPTS = ("desktop_who", "desktop_size", "roam", "perch", "peek", "nap", "dance", "hover_fade", "merged")
WATCHED = ("desktop", "hud_mode", "summon_fx", "clones") + PASS_OPTS
HUD_TITLE = "J.A.R.V.I.S."
IS_WINDOWS = sys.platform == "win32"


def available():
    try:
        import importlib.util
        return importlib.util.find_spec("PySide6.QtWebEngineWidgets") is not None
    except Exception:
        return False


class Host:
    def __init__(self, core):
        self.core = core
        self.proc = None
        self.conn = None
        self.srv = None
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self._acts = {}
        self._n = 0
        self._stopping = False
        self._restarts = []

    # ------------------------------------------------------------ lifecycle
    def start(self):
        for k in WATCHED:
            prefs.on_change(k, self._opt)
        if prefs.get("desktop"):
            self.launch()
            if prefs.get("hud_mode") == "character":
                self._hide_hud()                 # "Just him": start out on the desktop, no window
        import tools
        tools.set_summon_hook(self.summon)
        try:
            import pointer
            pointer.set_display(self.pointer)
        except Exception:
            pass
        return self

    def pointer(self, x, y, kind):
        """His own pointer, drawn on the desktop while he clicks for you."""
        if self.conn is not None:
            self._send({"t": "pointer", "at": [int(x), int(y)], "kind": kind})
            time.sleep(0.35)                    # let it glide there before the click lands

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def launch(self):
        if self.running() or not IS_WINDOWS:
            return
        if not available():
            self.core.emit({"type": "toast", "text": "The desktop characters need an update that includes them "
                                                     "(PySide6 isn't in this build)."})
            return
        self.ready.clear()
        self.srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(1)
        port = self.srv.getsockname()[1]
        self.token = secrets.token_hex(16)
        ui = str(config.RES_DIR / "ui")
        if config.FROZEN:
            cmd = [sys.executable, "--buddies", str(port), self.token, ui]
        else:
            cmd = [sys.executable, str(config.BASE_DIR / "buddies_qt.py"), str(port), self.token, ui]
        log = open(config.JARVIS_DIR / "logs" / "buddies.log", "a", encoding="utf-8", errors="replace") \
            if (config.JARVIS_DIR / "logs").is_dir() else subprocess.DEVNULL
        self.proc = subprocess.Popen(cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                     creationflags=0x08000000 if IS_WINDOWS else 0)
        threading.Thread(target=self._accept, daemon=True, name="buddies-accept").start()
        threading.Thread(target=self._watch_proc, args=(self.proc,), daemon=True, name="buddies-proc").start()

    def _accept(self):
        srv = self.srv
        srv.settimeout(40)
        try:
            conn, _ = srv.accept()
        except OSError:
            print("[buddies] the figures never connected")
            return
        finally:
            try:
                srv.close()
            except OSError:
                pass
        conn.settimeout(None)
        f = conn.makefile("r", encoding="utf-8")
        try:
            hello = json.loads(f.readline() or "{}")
        except ValueError:
            hello = {}
        if hello.get("token") != self.token:          # someone else on this PC knocking: not ours
            conn.close()
            return
        self.conn = conn
        self._send({"t": "init", "opts": {k: prefs.get(k) for k in PASS_OPTS}, "persona": self.core.persona_key,
                    "duo": bool(getattr(self.core, "duo", False)), "state": getattr(self.core, "state", "idle"),
                    "pos": prefs.get("desktop_pos")})
        self._send({"t": "state", "state": getattr(self.core, "state", "idle")})
        for line in f:
            try:
                self._from_child(json.loads(line))
            except ValueError:
                pass
        self.conn = None

    def _watch_proc(self, proc):
        proc.wait()
        if self._stopping or proc is not self.proc:
            return
        self.ready.clear()
        now = time.time()
        self._restarts = [t for t in self._restarts if now - t < 300] + [now]
        if len(self._restarts) > 3:
            print("[buddies] the figures keep crashing; leaving them off until the next start")
            self.core.emit({"type": "toast", "text": "The desktop characters keep crashing, so they're off for now "
                                                     "(the log has buddies.log)."})
            return
        if prefs.get("desktop"):
            time.sleep(2)
            self.launch()

    def stop(self, keep_pref=True):
        self._stopping = True
        self._send({"t": "quit"})
        p = self.proc
        self.proc = None
        if p is not None:
            try:
                p.wait(3)
            except Exception:
                p.kill()
        self._stopping = False

    def _send(self, obj):
        c = self.conn
        if c is None:
            return False
        try:
            with self.lock:
                c.sendall((json.dumps(obj) + "\n").encode())
            return True
        except OSError:
            return False

    # ------------------------------------------------------------ options
    def _opt(self, key, value):
        if key == "desktop":
            if value:
                self.launch()
                if prefs.get("hud_mode") == "character":
                    self._hide_hud()
            else:
                self.stop()
                self._show_hud()
            return
        if key == "hud_mode":
            if value == "character" and prefs.get("desktop"):
                self._hide_hud()
            elif value == "window":
                self._show_hud()
            return
        if key in PASS_OPTS:
            self._send({"t": "opts", "opts": {k: prefs.get(k) for k in PASS_OPTS}})

    def just_him(self):
        return bool(prefs.get("desktop") and prefs.get("hud_mode") == "character" and self.running())

    def _hide_hud(self):
        fn = getattr(self.core, "on_hide", None)
        if fn:
            threading.Timer(1.5, fn).start()

    def _show_hud(self):
        fn = getattr(self.core, "on_restore", None)
        if fn:
            fn()

    # ------------------------------------------------------------ what's going on
    def feed(self, ev):
        if self.conn is None:
            return
        t = ev.get("type")
        if t == "state":
            self._send({"t": "state", "state": ev.get("state")})
        elif t == "voice_env":
            self._send({"t": "env", "env": ev.get("env"), "step": ev.get("step"), "delay": ev.get("delay", 0),
                        "who": ev.get("who") or self.core.persona_key})
        elif t == "level":
            self._send({"t": "mic", "v": ev.get("v", 0)})
        elif t == "persona":
            self._send({"t": "persona", "key": ev.get("key")})
        elif t == "duo":
            self._send({"t": "duo", "on": ev.get("on")})
        elif t == "confirm" and self.just_him() and not self._hud_visible():
            self.throw_open()                         # an approval has to be seen: throw his window open

    def _from_child(self, m):
        t = m.get("t")
        if t == "ready":
            self.ready.set()
        elif t == "moved":
            prefs.set("desktop_pos", m.get("pos"))
        elif t == "open_window":
            if self._hud_visible():
                return
            self.throw_open() if prefs.get("summon_fx") else self._show_hud()
        elif t in ("act_done", "act_skip"):
            a = self._acts.pop(m.get("id"), None)
            if a and a.get("on_skip") and t == "act_skip":
                a["on_skip"]()

    # ------------------------------------------------------------ opening things with an entrance
    def summon(self, target, kind, who=None):
        """Called by tools.open_thing just before it opens something. Returns a token whose done(result) is called
        after; the window that shows up gets the entrance. None if there's nothing to animate."""
        if not (self.conn and prefs.get("summon_fx") and prefs.get("desktop")) or kind == "settings":
            return None
        self._n += 1
        aid = f"a{self._n}"
        before = _top_windows()
        self._acts[aid] = {"t": time.time()}
        self._send({"t": "act_start", "who": who or self.core.persona_key, "id": aid})
        return _Summon(self, aid, before)

    def throw_open(self):
        """'Just him' mode: the figure throws his window open."""
        rect = _hud_rect()
        if not rect:
            return self._show_hud()
        self._n += 1
        aid = f"a{self._n}"
        self._acts[aid] = {"t": time.time(), "on_skip": self._show_hud}
        self._send({"t": "act_start", "who": self.core.persona_key, "id": aid})

        def go():
            time.sleep(0.45)
            self._send({"t": "act_go", "id": aid, "rect": rect})
            time.sleep(0.2)                            # the drapes/light are over the spot: now it appears under them
            self._show_hud()

        threading.Thread(target=go, daemon=True).start()

    def _hud_visible(self):
        if not IS_WINDOWS:
            return True
        try:
            import ctypes
            u = ctypes.windll.user32
            h = u.FindWindowW(None, HUD_TITLE)
            return bool(h) and bool(u.IsWindowVisible(h)) and not u.IsIconic(h)
        except Exception:
            return True

    def command(self, action, value=None):
        if not self.conn:
            return "The desktop characters aren't running."
        if action == "clone":
            if not prefs.get("clones"):
                return "Clones are switched off. Turn on Clones in Options first."
            try:
                n = int(float(value or 3))
            except (TypeError, ValueError):
                n = 3
            n = max(1, min(5, n))
            self._send({"t": "clone", "n": n})
            return f"{n} clone{'s' if n != 1 else ''} out on the desktop for a bit."
        if action == "clones_away":
            self._send({"t": "clones_away"})
            return "Clones gone."
        return "Unknown."


class _Summon:
    """Waits for the opened app's window (new, or brought to the front) and sends where it is."""

    def __init__(self, host, aid, before):
        self.host, self.aid, self.before = host, aid, before

    def done(self, result):
        threading.Thread(target=self._find, args=(str(result or ""),), daemon=True, name="summon-find").start()

    def _find(self, result):
        failed = any(w in result.lower() for w in ("couldn't", "could not", "not found", "failed", "no app"))
        end = time.time() + (0.5 if failed else 8)
        fg0 = _fg()
        while time.time() < end:
            rect = None
            now = _top_windows()
            new = [h for h in now if h not in self.before]
            if new:
                rect = _rect(new[0])
            else:
                fg = _fg()
                if fg and fg != fg0 and fg in now:       # an app that was already open came to the front
                    rect = _rect(fg)
            if rect and rect[2] - rect[0] > 120 and rect[3] - rect[1] > 80:
                self.host._send({"t": "act_go", "id": self.aid, "rect": list(rect)})
                return
            time.sleep(0.15)
        self.host._send({"t": "act_cancel", "id": self.aid})


# ---------------------------------------------------------------- Windows helpers
def _user32():
    import ctypes
    return ctypes.windll.user32


def _fg():
    if not IS_WINDOWS:
        return None
    try:
        return int(_user32().GetForegroundWindow() or 0) or None
    except Exception:
        return None


def _top_windows():
    """Visible, titled, top-level app windows (not tool windows), as a set of handles."""
    if not IS_WINDOWS:
        return set()
    import ctypes
    from ctypes import wintypes as wt
    u = _user32()
    out = set()
    me = os.getpid()

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(h, _):
        try:
            if not u.IsWindowVisible(h) or u.IsIconic(h) or u.GetWindowTextLengthW(h) == 0:
                return True
            if u.GetWindowLongW(h, -20) & 0x80:          # WS_EX_TOOLWINDOW
                return True
            pid = wt.DWORD()
            u.GetWindowThreadProcessId(h, ctypes.byref(pid))
            if pid.value != me:
                out.add(int(h))
        except Exception:
            pass
        return True

    try:
        u.EnumWindows(cb, 0)
    except Exception:
        pass
    return out


def _rect(h):
    import ctypes
    from ctypes import wintypes as wt
    r = wt.RECT()
    try:
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(wt.HWND(h), 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
            _user32().GetWindowRect(wt.HWND(h), ctypes.byref(r))
    except Exception:
        return None
    return (r.left, r.top, r.right, r.bottom)


def _hud_rect():
    """Where his window is (or will be when it's restored)."""
    if not IS_WINDOWS:
        return None
    import ctypes
    from ctypes import wintypes as wt
    u = _user32()
    h = u.FindWindowW(None, HUD_TITLE)
    if not h:
        return None

    class WP(ctypes.Structure):
        _fields_ = [("length", wt.UINT), ("flags", wt.UINT), ("showCmd", wt.UINT), ("ptMin", wt.POINT),
                    ("ptMax", wt.POINT), ("rc", wt.RECT)]
    wp = WP()
    wp.length = ctypes.sizeof(WP)
    if u.GetWindowPlacement(h, ctypes.byref(wp)):
        r = wp.rc
        return [r.left, r.top, r.right, r.bottom]
    return list(_rect(h) or ()) or None
