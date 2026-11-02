"""
The secret companion: a small figure of Ultron (her, here) who lives in the corner of your desktop and reacts
when he listens, thinks and talks. She's built from this app's own Ultron look: red crystal shards, the dark
eye with the glowing slit, the broken polygon halo.

Unlocking her is the secret: say (or type) "up up down down left right left right B A start". Say it again to
send her away. On the HUD keyboard, the classic arrow-key version works too. She stays on across restarts.

Built to stay out of your way:
  * Small (about 150 x 190), bottom-right above the taskbar. Drag her anywhere; she remembers.
  * She can never take focus or show up in the taskbar or Alt+Tab (same tricks as the corner widget).
  * Double-click her to tuck her away; she comes back the next time he talks.
  * She hides on her own while a full-screen game or video is in front.
  * Light on the PC: she animates at about 30 frames a second only while he's listening, thinking or talking,
    about 6 while idle, and not at all while she's hidden.
"""
import sys
import threading
import time

import config

TITLE = "Jarvis Companion"
W, H = 150, 190
MARGIN = 10
PARK = -30000
PASS = {"state", "voice", "persona", "level", "duo"}
IS_WINDOWS = sys.platform == "win32"


def _u():
    import mini
    return mini._u()


class Companion:
    def __init__(self, emitter_cls):
        self.em = emitter_cls()
        self.window = None
        self.hwnd = 0
        self.on = False              # unlocked and wanted
        self.shown = False           # actually on screen right now
        self.tucked = False          # double-clicked away until he next talks
        self.pos = None
        self.snap = {}
        self._voice_t = 0.0
        self._stop = threading.Event()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ events
    def feed(self, ev):
        t = ev.get("type")
        if t not in PASS:
            return
        if t == "voice":
            now = time.time()
            if now - self._voice_t < 0.05:
                return
            self._voice_t = now
        if t in ("persona", "state", "duo"):
            with self._lock:
                self.snap[t] = ev
        if t == "state" and self.tucked and ev.get("state") in ("listening", "speaking"):
            self.tucked = False                      # he's talking to you: she comes back
            self._refresh()
        if self.shown:
            self.em(ev)

    # ------------------------------------------------------------------ window
    def create(self, webview):
        self.bridge = CompanionBridge(self)
        kw = dict(url=str(config.RES_DIR / "ui" / "companion.html"), js_api=self.bridge, width=W, height=H,
                  x=PARK, y=PARK, frameless=True, easy_drag=False, on_top=True, resizable=False,
                  background_color="#07080b")
        try:
            self.window = webview.create_window(TITLE, focus=False, shadow=False, **kw)
        except TypeError:
            self.window = webview.create_window(TITLE, **kw)
        self.em.window = self.window
        return self.window

    def _handle(self):
        if self.hwnd or not IS_WINDOWS:
            return self.hwnd
        try:
            self.hwnd = _u().FindWindowW(None, TITLE) or 0
        except Exception:
            self.hwnd = 0
        if self.hwnd:
            self._style()
        return self.hwnd

    def _style(self):
        import ctypes
        u = _u()
        GWL_EXSTYLE, NOACTIVATE, TOOLWINDOW, APPWINDOW = -20, 0x08000000, 0x80, 0x40000
        try:
            ex = u.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            ex = ((ex | NOACTIVATE | TOOLWINDOW) & ~APPWINDOW & ~0x00080000) & 0xFFFFFFFF
            u.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex - (1 << 32) if ex >= 1 << 31 else ex)
            u.SetWindowPos(self.hwnd, None, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0004 | 0x0010 | 0x0020)
            u.ShowWindowAsync(self.hwnd, 0)
            u.ShowWindowAsync(self.hwnd, 4)
        except Exception as e:
            print(f"[companion] style failed: {e}")
        try:
            pref = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(self.hwnd, 33, ctypes.byref(pref), 4)
        except Exception:
            pass

    def _rect(self):
        import ctypes
        from ctypes import wintypes as wt
        u = ctypes.windll.user32
        try:
            s = (_u().GetDpiForWindow(self.hwnd) or 96) / 96
        except Exception:
            s = 1.0
        w, h = int(W * s), int(H * s)
        if self.pos:
            vx, vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
            vw, vh = u.GetSystemMetrics(78), u.GetSystemMetrics(79)
            x, y = self.pos
            if vx <= x <= vx + vw - 40 and vy <= y <= vy + vh - 40:
                return x, y, w, h
        r = wt.RECT()
        u.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)
        m = int(MARGIN * s)
        return r.right - w - m, r.bottom - h - m, w, h

    def _place(self):
        x, y, w, h = self._rect()
        _u().SetWindowPos(self.hwnd, -1, x, y, w, h, 0x0010 | 0x4000)

    def _park(self):
        _u().SetWindowPos(self.hwnd, None, PARK, PARK, 0, 0, 0x0001 | 0x0004 | 0x0010 | 0x4000)

    def _remember_pos(self):
        import ctypes
        from ctypes import wintypes as wt
        r = wt.RECT()
        if self.hwnd and _u().GetWindowRect(self.hwnd, ctypes.byref(r)) and r.left > PARK + 1000:
            self.pos = (r.left, r.top)

    def settle(self, main_title, start_on=False):
        """After launch: find and style the window, park it, and start the watcher. start_on = unlocked before."""
        import tools
        if not IS_WINDOWS:
            return
        time.sleep(0.6)
        for _ in range(100):
            if self._handle():
                break
            time.sleep(0.1)
        else:
            print("[companion] window never appeared")
            self.window = None
            return
        self._park()
        for _ in range(20):                      # creating it mustn't steal focus from the main window
            time.sleep(0.15)
            if tools._fg() == self.hwnd:
                main = _u().FindWindowW(None, main_title)
                if main:
                    tools._force_foreground(main)
                break
        self.on = bool(start_on)
        threading.Thread(target=self._watch, daemon=True, name="companion").start()
        self._refresh()

    def _want_visible(self):
        if not (self.on and not self.tucked and self.window):
            return False
        try:
            import tools
            if config.GAME_MODE and tools.fullscreen_app():
                return False
        except Exception:
            pass
        return True

    def _refresh(self):
        if not self.hwnd:
            return
        want = self._want_visible()
        try:
            if want and not self.shown:
                with self._lock:
                    snap = [self.snap[k] for k in ("persona", "duo", "state") if k in self.snap]
                self.shown = True
                self.em({"type": "sync", "events": snap})
                self.em({"type": "window", "visible": True})
                self._place()
            elif not want and self.shown:
                self.shown = False
                self.em({"type": "window", "visible": False})
                self._remember_pos()
                self._park()
        except Exception as e:
            print(f"[companion] {e}")

    def _watch(self):
        """Every couple of seconds: is a full-screen game in front? Is focus stuck on her? (Cheap checks.)"""
        import tools
        last = 0
        while not self._stop.wait(1.5):
            self._refresh()
            try:
                fg = tools._fg()
                if fg and fg == self.hwnd and last:
                    tools._force_foreground(last)
                elif fg and tools._is_user_app(fg):
                    last = fg
            except Exception:
                pass

    def toggle(self, on=None):
        """The secret code. Returns True if she's on now."""
        self.on = (not self.on) if on is None else bool(on)
        self.tucked = False
        self._refresh()
        return self.on

    def tuck(self):
        self.tucked = True
        self._refresh()

    def close(self):
        self._stop.set()
        self.em.close()
        try:
            if self.window:
                self.window.destroy()
        except Exception:
            pass


class CompanionBridge:
    """window.pywebview.api.* for her page."""

    def __init__(self, comp):
        self._c = comp

    def ready(self):
        self._c.em.mark_ready()
        return True

    def tuck(self):
        threading.Thread(target=self._c.tuck, daemon=True).start()

    def drag_start(self):
        self._c._remember_pos()
        self._c._drag0 = self._c.pos

    def drag_to(self, dx, dy):
        c = self._c
        if not (c.hwnd and getattr(c, "_drag0", None)):
            return
        x0, y0 = c._drag0
        _u().SetWindowPos(c.hwnd, None, int(x0 + dx), int(y0 + dy), 0, 0, 0x0001 | 0x0004 | 0x0010 | 0x4000)

    def drag_end(self):
        self._c._remember_pos()
        self._c._drag0 = None


# ======================================================================== the secret code
import re  # noqa: E402

_WORD = {"bee": "b", "be": "b", "bea": "b", "ay": "a", "eh": "a", "hey": "a", "uh": "a", "ba": "b a", "bay": "b a",
         "lift": "left", "write": "right", "rite": "right", "wright": "right", "dawn": "down", "start": "start"}


def is_code(text):
    """'up up down down left right left right B A start', however speech recognition spells it."""
    words = [_WORD.get(w, w) for w in re.findall(r"[a-z]+", (text or "").lower())]
    s = " ".join(words)
    s = re.sub(r"\b(jarvis|ultron|hey|okay|ok|um|uh)\b", " ", s)
    s = " ".join(s.split())
    return bool(re.search(r"\bup up down down left right left right b ?a( start)?\b", s)) and "start" in s.split()[-3:]
