"""
His screensaver: after a while with no mouse or keyboard, his world fills the main screen, with the small things in it
moving (ambient.js), a slow drift across the picture, a clock, your next event and the weather. Any key, click or
mouse move puts it away.

Settings > His desktop > Screensaver (off, or 5 to 30 minutes). "Jarvis, start your screensaver" shows it now.

It stays out of the way. It won't come up while:
  - a game is running (gamemode.py), or Windows says something is fullscreen, presenting or in quiet hours
    (SHQueryUserNotificationState, the same check Windows uses before showing you a notification)
  - something is holding the display on, which is what video players and browsers playing a video do
    (the system's execution state has ES_DISPLAY_REQUIRED)
  - he's talking, listening or waiting on you to approve something

How it closes: it remembers the last-input tick Windows had when it opened and checks a few times a second. The
moment that tick moves (you touched anything), it's gone. A click or key on the page itself does the same.
Nothing is recorded; it's a window and a timer.
"""
import sys
import threading
import time

import config

TITLE = "Jarvis Screensaver"
IS_WINDOWS = sys.platform == "win32"


def _last_input_tick():
    """Windows' tick count at the last mouse or keyboard input, or None off Windows."""
    if not IS_WINDOWS:
        return None
    import ctypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    li = LASTINPUTINFO()
    li.cbSize = ctypes.sizeof(li)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
        return None
    return li.dwTime


def idle_secs():
    t = _last_input_tick()
    if t is None:
        return 0.0
    import ctypes
    return ((ctypes.windll.kernel32.GetTickCount() - t) & 0xFFFFFFFF) / 1000.0


def _windows_busy():
    """True when Windows itself says not to interrupt: fullscreen app, presentation, quiet time, or a video."""
    if not IS_WINDOWS:
        return True
    import ctypes
    try:
        state = ctypes.c_int(0)
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0 and state.value != 5:
            return True                                    # 5 = QUNS_ACCEPTS_NOTIFICATIONS; anything else is busy
    except Exception:
        pass
    try:
        es = ctypes.c_ulong(0)                              # SystemExecutionState = 16
        if ctypes.windll.powrprof.CallNtPowerInformation(16, None, 0, ctypes.byref(es), ctypes.sizeof(es)) == 0:
            if es.value & 0x2:                              # ES_DISPLAY_REQUIRED: something wants the screen on
                return True
    except Exception:
        pass
    return False


def ok_to_show(core=None):
    try:
        import gamemode
        if gamemode.playing():
            return False
    except Exception:
        pass
    if core is not None and (getattr(core, "_pending", None) or getattr(core, "state", "idle") not in ("idle", "booting")):
        return False                                       # waiting on your approval, or in the middle of talking
    return not _windows_busy()


_WX = {}


def info(core=None):
    """What the page shows: the scene, the clock style, your next event and the weather (cached half an hour)."""
    out = {"scene": config.DESK_SCENE, "h12": (config.COUNTRY or "US").upper() in ("US", "CA", "AU", "PH", "IN"),
           "motion": config.WORLD_MOTION}
    try:
        import deskfacts
        out["light"] = deskfacts.world_light()
    except Exception:
        out["light"] = {}
    if core is not None:
        try:
            import glass_kinds
            now = time.time() * 1000
            nxt = next((x for x in glass_kinds.calendar(core)["items"] if x.get("all_day") or x["at"] > now), None)
            if nxt:
                out["next"] = f"{nxt['time']}  {nxt['text']}"[:80]
        except Exception as e:
            print(f"[saver] calendar: {type(e).__name__}")
        try:
            if time.time() - _WX.get("at", 0) > 1800:
                import glass_kinds
                w = glass_kinds.weather(core)
                _WX.update(at=time.time(), line=f"{w['now']}{w['unit']}  {w['label']}".strip())
            out["weather"] = _WX.get("line", "")
        except Exception as e:
            print(f"[saver] weather: {type(e).__name__}")
    return out


class SaverBridge:
    def __init__(self, saver):
        self._s = saver

    def info(self):
        return info(self._s.core)

    def wake(self):
        self._s.close()
        return True


class Saver:
    def __init__(self, core, webview):
        self.core, self.webview = core, webview
        self.win = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._opened_tick = None
        self._opened_at = 0.0
        self._last_close = 0.0

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="saver").start()
        return self

    def stop(self):
        self._stop.set()
        self.close()

    def _loop(self):
        while not self._stop.wait(0.3 if self.win else 5):
            try:
                if self.win:
                    t = _last_input_tick()
                    if t is not None and t != self._opened_tick and time.time() - self._opened_at > 1.0:
                        self.close()
                    continue
                mins = config.SAVER_MIN
                if not mins or time.time() - self._last_close < 60:
                    continue
                if idle_secs() >= mins * 60 and ok_to_show(self.core):
                    self.show()
            except Exception as e:
                print(f"[saver] {type(e).__name__}: {e}")

    def show(self):
        with self._lock:
            if self.win or not IS_WINDOWS:
                return False
            self._opened_tick = _last_input_tick()
            self._opened_at = time.time()
            try:
                self.win = self.webview.create_window(
                    TITLE, url=str(config.RES_DIR / "ui" / "saver.html"), js_api=SaverBridge(self),
                    fullscreen=True, on_top=True, frameless=True, background_color="#000000")
            except Exception as e:
                print(f"[saver] couldn't open: {e}")
                self.win = None
                return False
        return True

    def show_now(self):
        """Asked for by voice: wait a moment so the words that asked for it don't close it again."""
        def go():
            time.sleep(2.5)
            self.show()
        threading.Thread(target=go, daemon=True).start()

    def close(self):
        with self._lock:
            w, self.win = self.win, None
            self._last_close = time.time()
        if w is not None:
            try:
                w.destroy()
            except Exception as e:
                print(f"[saver] close: {e}")


SAVER = None


def start(core, webview):
    global SAVER
    if not IS_WINDOWS:
        return None
    SAVER = Saver(core, webview).start()
    return SAVER


def tool(action="show"):
    if SAVER is None:
        return "The screensaver only runs on Windows, with the app open."
    if action == "show":
        SAVER.show_now()
        return "Screensaver in a moment. Touch anything to put it away."
    if action == "status":
        m = config.SAVER_MIN
        return f"It comes up after {m} minutes idle." if m else "It's off. Turn it on in Settings > His desktop > Screensaver."
    return "action must be show or status."
