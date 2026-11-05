"""
Screen watching: while you're talking to him, Jarvis keeps a live view of your screen in memory, so looking costs
him nothing and he can already see what you mean when you ask.

Why it's faster (the picture itself was never the slow part, it takes about a tenth of a second):
  * Every look used to be an extra trip to Claude: he answered "let me look", got the picture, then answered.
    When what you say is about the screen ("what's this error", "what am I looking at", "read this"), the picture
    now goes along with your words, so Claude answers in one trip. That's usually 1 to 3 seconds saved.
  * After a click he waits only until the screen stops changing (often 0.2 s), not a fixed 0.6 s.
  * If he looks again and nothing changed, he's told so instead of being sent the same picture again.
  * The latest frame is already in memory, so a look doesn't have to capture first.

Privacy: frames stay in memory, are never written to disk, and only reach Claude the same way a normal look
does: when you ask about the screen, or when he needs to look to do something for you. It only watches while
you're talking to him (and a minute and a half after), and never while a fullscreen game or video is in front.
"""
import re
import sys
import threading
import time

import config

IS_WINDOWS = sys.platform == "win32"
FPS = 3                    # plenty to know what's there and when it settles
AWAKE_FOR = 90             # keep watching this long after the last time you talked to him

# Things you say that are about what's on the screen. Kept tight: a false match sends a picture for nothing.
ABOUT_SCREEN = re.compile(
    r"\b(on (my|the|this) (screen|monitor|display)|what('s| is) (this|that|on)|what am i (looking|seeing)|"
    r"(look|looking) at (this|that|my|the)|can you see|do you see|what do you see|read (this|that|it|me)|"
    r"this (error|message|window|page|game|app|code|popup|pop-up|chart|graph|picture|image|video|tab|screen|website|site|menu|button)|"
    r"what does (it|this|that) say|what('s| is) wrong (here|with this)|help me with this|"
    r"(which|what) (button|option|one) (do|should) i)\b", re.I)
WHOLE = re.compile(r"\b(both (screens|monitors)|all (my )?(screens|monitors)|everything on)\b", re.I)


class ScreenWatch:
    def __init__(self, core=None):
        self.core = core
        self.frame = None          # PIL image of every monitor, newest
        self.frame_t = 0.0
        self.changed_t = 0.0       # when the picture last changed noticeably
        self._small = None
        self._last_active = 0.0
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._tl = threading.local()       # mss can't be shared between threads

    def start(self):
        if not IS_WINDOWS:
            return self
        threading.Thread(target=self._loop, daemon=True, name="screen-watch").start()
        return self

    def stop(self):
        self._stop.set()

    # ------------------------------------------------------------------ capture
    def _capture(self):
        from PIL import Image
        m = getattr(self._tl, "mss", None)
        if m is None:
            try:
                import mss
                m = mss.mss()
            except Exception:
                m = False
            self._tl.mss = m
        if m:
            try:
                shot = m.grab(m.monitors[0])          # monitor 0 = every monitor together
                return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            except Exception:
                pass
        from PIL import ImageGrab
        return ImageGrab.grab(all_screens=True)

    def _awake(self):
        st = getattr(self.core, "state", "idle") if self.core else "idle"
        now = time.time()
        if st in ("listening", "thinking", "speaking", "awaiting", "dictating"):
            self._last_active = now
        return now - self._last_active < AWAKE_FOR

    def _fullscreen(self):
        try:
            import livedesk
            return livedesk._fullscreen_in_front()
        except Exception:
            return False

    def _loop(self):
        while not self._stop.wait(1 / FPS):
            if not self._awake() or self._fullscreen():
                if self.frame is not None and time.time() - self.frame_t > 5:
                    with self._lock:
                        self.frame = None              # don't hold on to an old picture of your screen
                continue
            try:
                self.grab_now()
            except Exception as e:
                print(f"[screen watch] {e}")
                time.sleep(2)

    def grab_now(self):
        img = self._capture()
        small = img.convert("L").resize((96, 54))
        now = time.time()
        with self._lock:
            if self._small is None or _diff(small, self._small) > 2.0:
                self.changed_t = now
            self._small, self.frame, self.frame_t = small, img, now
        return img

    # ------------------------------------------------------------------ used by the screen tools
    def latest(self, max_age=0.4):
        """The newest frame if it's fresh enough, else a new capture."""
        with self._lock:
            if self.frame is not None and time.time() - self.frame_t <= max_age:
                return self.frame
        return self.grab_now()

    def wait_still(self, min_wait=0.15, max_wait=1.6, quiet=0.3):
        """After a click or key press: wait until the screen has stopped changing (a page loading, a menu opening)."""
        start = time.time()
        time.sleep(min_wait)
        while time.time() - start < max_wait:
            self.grab_now()
            if time.time() - self.changed_t >= quiet:
                return
            time.sleep(0.1)


def _diff(a, b):
    """Average brightness change between two tiny greyscale pictures (0 to 255)."""
    pa, pb = a.tobytes(), b.tobytes()
    return sum(abs(x - y) for x, y in zip(pa, pb)) / max(1, len(pa))


WATCH = None


def get():
    return WATCH


def start(core):
    global WATCH
    if WATCH is None and config.SCREEN_WATCH and IS_WINDOWS:
        WATCH = ScreenWatch(core).start()
    return WATCH


def about_screen(text):
    """Is what they said about the screen? Then the target to show: 'all' or 'active'."""
    if not text or not (ABOUT_SCREEN.search(text) or WHOLE.search(text)):
        return None
    return "all" if WHOLE.search(text) else "active"
