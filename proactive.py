"""
Juno starts a conversation (Settings > Conversation & personality > "Start conversations about what I'm doing").

What she knows: only the app in front and its window title, and how long you've been in it (plus the last few
apps before that). Never the screen, never what you type. Those names go to Claude only at the moment she
decides to say something.

When she'll speak up, all of these at once:
  * the option is on, you're not muted, and it isn't your quiet hours
  * you haven't talked to her for a while, and she hasn't started one too recently (the "How often" setting)
  * you've been in the same thing a while (not just alt-tabbing)
  * you're there but paused: your last key press or mouse move was 6 to 120 seconds ago (not mid-typing, not away)
  * nothing fullscreen (games, videos), no call app in front (Zoom, Teams, Skype, Webex, a Discord call),
    and the app isn't on your "never talk about" list or your blocked apps
Then a quick, cheap model writes one or two sentences (or decides it's not worth saying anything), she says it,
and listens for your answer without needing her name.
"""
import random
import re
import sys
import threading
import time
from datetime import datetime

import config

IS_WINDOWS = sys.platform == "win32"
# How often: (min gap between check-ins in minutes, max gap, minutes in one thing first, max a day)
EVERY = {"rarely": (180, 300, 15, 3), "normal": (30, 45, 8, 12), "often": (10, 15, 4, 30)}
CALL_APPS = {"zoom.exe", "teams.exe", "ms-teams.exe", "skype.exe", "webex.exe", "webexmta.exe", "ciscowebexstart.exe"}
CALL_TITLES = re.compile(r"\b(meeting|call|voice connected|huddle|on air)\b", re.I)
PRIVATE_TITLES = re.compile(r"\b(bank|banking|password|1password|bitwarden|keepass|login|sign in|medical|incognito|inprivate)\b", re.I)
SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "MultitaskingViewFrame"}


def _idle_seconds():
    """Seconds since the last key press or mouse move anywhere."""
    import ctypes
    from ctypes import wintypes as wt

    class LII(ctypes.Structure):
        _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]
    lii = LII()
    lii.cbSize = ctypes.sizeof(LII)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
        return 0.0
    return ((ctypes.windll.kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF) / 1000.0


def _foreground():
    """(process name, window title) of the app in front, or (None, None)."""
    import ctypes
    from ctypes import wintypes as wt
    u = ctypes.windll.user32
    h = u.GetForegroundWindow()
    if not h:
        return None, None
    buf = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, buf, 256)
    if buf.value in SHELL_CLASSES:
        return None, None
    n = u.GetWindowTextLengthW(h)
    tb = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, tb, n + 1)
    pid = wt.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    try:
        import psutil
        name = psutil.Process(pid.value).name().lower()
    except Exception:
        name = ""
    return name, tb.value.strip()


def _app_label(proc, title):
    """A short readable name: "Blender (my_scene.blend)", "YouTube in Chrome"..."""
    app = re.sub(r"\.exe$", "", proc or "").replace("_", " ").strip() or "an app"
    t = re.sub(r"\s+", " ", title or "")[:90]
    return f"{app}: \"{t}\"" if t else app


def _in_quiet_hours():
    q = (config.QUIET_HOURS or "").strip()
    m = re.match(r"^(\d{1,2})\s*-\s*(\d{1,2})$", q)
    if not m:
        return False
    a, b, h = int(m.group(1)) % 24, int(m.group(2)) % 24, datetime.now().hour
    return (a <= h < b) if a < b else (h >= a or h < b)


class Proactive:
    def __init__(self, core):
        self.core = core
        self._stop = threading.Event()
        self.cur = None                 # (proc, title-ish key)
        self.cur_since = time.time()
        self.cur_label = ""
        self.recent = []                # [(label, minutes)] of the last few things
        self.last_talk = time.time()    # last time you and she talked (either way)
        self.last_check_in = 0.0
        self.next_gap = 0.0
        self.today = (datetime.now().date(), 0)

    def start(self):
        if IS_WINDOWS:
            threading.Thread(target=self._loop, daemon=True, name="proactive").start()
        return self

    def stop(self):
        self._stop.set()

    def _key(self, proc, title):
        # browsers: the page matters ("YouTube", "Reddit"); otherwise the app is enough, so a new file in the
        # same app doesn't reset the clock
        if proc in ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"):
            return proc, re.sub(r"\s+[-|—]\s+.*$", "", title or "")[:40]
        return proc, ""

    def _loop(self):
        lo, hi, _, _ = timing()
        self.next_gap = random.uniform(lo, hi) * 60
        while not self._stop.wait(5):
            try:
                self._tick()
            except Exception as e:
                print(f"[chat first] {e}")
                self._stop.wait(30)

    def _tick(self):
        core = self.core
        now = time.time()
        if getattr(core, "state", "idle") not in ("idle",) or getattr(core, "_turn", None) is not None:
            self.last_talk = now
        proc, title = _foreground()
        if proc is None:
            return
        own = any((title or "").startswith(t) for t in ("J.U.N.O.", "J.A.R.V.I.S.", "Jarvis "))
        if own:
            return
        key = self._key(proc, title)
        if key != self.cur:
            if self.cur is not None:
                mins = (now - self.cur_since) / 60
                if mins >= 1:
                    self.recent = ([(self.cur_label, round(mins))] + self.recent)[:4]
            self.cur, self.cur_since = key, now
        self.cur_label = _app_label(proc, title)
        if not config.CHAT_FIRST:
            return
        lo, hi, dwell, cap = timing()
        day = datetime.now().date()
        if self.today[0] != day:
            self.today = (day, 0)
        why_not = None
        if getattr(core, "muted", False):
            why_not = "muted"
        elif _in_quiet_hours():
            why_not = "quiet hours"
        elif self.today[1] >= cap:
            why_not = "enough for today"
        elif now - self.last_talk < max(600, self.next_gap * .5):
            why_not = "talked recently"
        elif now - self.last_check_in < self.next_gap:
            why_not = "too soon"
        elif now - self.cur_since < dwell * 60:
            why_not = "not in it long enough"
        if why_not:
            return
        idle = _idle_seconds()
        if not config.CHAT_PAUSE <= idle <= max(120, config.CHAT_PAUSE + 60):    # mid-typing, or not at the PC
            return
        if proc in CALL_APPS or CALL_TITLES.search(title or "") or PRIVATE_TITLES.search(title or ""):
            return
        try:
            import tools
            if tools.in_game():
                return
        except Exception:
            pass
        low = f"{proc} {title}".lower()
        if any(a and a in low for a in config.CHAT_NEVER + config.BLOCKED_APPS):
            return
        self.last_check_in = now
        self.next_gap = random.uniform(lo, hi) * 60
        self.today = (day, self.today[1] + 1)
        mins = round((now - self.cur_since) / 60)
        core.events.put(("chat_first", {"what": self.cur_label, "mins": mins, "recent": list(self.recent)}))


def timing():
    """(min gap, max gap in minutes, minutes in one thing first, most a day), from the settings."""
    if config.CHAT_EVERY == "custom":
        m = config.CHAT_MINUTES
        lo, hi, dwell, cap = m * .8, m * 1.2, max(3, min(15, m // 4)), max(3, int(14 * 60 / m))
    else:
        lo, hi, dwell, cap = EVERY.get(config.CHAT_EVERY, EVERY["normal"])
    if config.CHAT_DWELL:
        dwell = config.CHAT_DWELL
    if config.CHAT_MAX:
        cap = config.CHAT_MAX
    return lo, hi, dwell, cap


STYLES = {
    "questions": "Ask a curious question about what they're doing.",
    "tips": "Offer one genuinely useful tip or shortcut for what they're doing.",
    "jokes": "Make a playful joke or teasing comment about what they're doing.",
    "hype": "Hype them up and encourage them about what they're doing.",
}


def _style_note():
    s = STYLES.get(config.CHAT_STYLE, "A curious question, a useful tip, or a light comment, whatever fits best.")
    if config.CHAT_TOPICS:
        s += f" They like talking about: {config.CHAT_TOPICS} (bring it in only if it connects)."
    return s


# ------------------------------------------------------------------ the song you're playing
_SONG = {"last": 0.0, "seen": set()}


def maybe_song(core, info):
    """Called by the music player on a new song. Now and then (not every song, at most every 30 minutes) she
    says something about it. Same rules as starting a conversation: not muted, not quiet hours, no game or call."""
    if not (config.CHAT_MUSIC and config.CHAT_FIRST) or core is None:
        return
    key = (info.get("title"), info.get("artist"))
    now = time.time()
    if key in _SONG["seen"] or now - _SONG["last"] < 30 * 60 or random.random() > .35:
        _SONG["seen"].add(key)
        return
    _SONG["seen"].add(key)
    if getattr(core, "muted", False) or _in_quiet_hours():
        return
    if getattr(core, "state", "idle") != "idle" or getattr(core, "_turn", None) is not None:
        return
    try:
        proc, title = _foreground()
        import tools
        if proc in CALL_APPS or CALL_TITLES.search(title or "") or tools.in_game():
            return
    except Exception:
        pass
    _SONG["last"] = now
    core.events.put(("song_chat", dict(info)))


def song_line(core, info):
    """One or two sentences about the song, or None. Uses the fast model."""
    import personas
    import usage
    client = getattr(getattr(core, "brain", None), "client", None)
    if client is None:
        return None
    ask = (f"[You're starting a chat on your own: they just started playing \"{info.get('title')}\" by "
           f"{info.get('artist') or 'an unknown artist'}. One or two short sentences about it in your own voice: a fun "
           "fact, how it makes you feel, or a question about their taste. Don't claim facts you're unsure of. "
           "If you don't know the song, just react to the vibe or ask about it. Reply SKIP if it'd be awkward.]")
    model = config.FAST_MODEL or config.MODEL
    try:
        msg = client.messages.create(model=model, max_tokens=110,
                                     system=personas.character(config.ADDRESS_AS) + "\nEverything you write is spoken "
                                            "aloud: plain words, no lists, emoji or markdown.",
                                     messages=[{"role": "user", "content": ask}])
        try:
            usage.record_claude(model, msg.usage)
        except Exception:
            pass
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    except Exception as e:
        print(f"[song chat] {e}")
        return None
    if not text or text.upper().startswith("SKIP"):
        return None
    return text, ask


def opener(core, info):
    """One or two sentences to start a conversation, or None if it isn't worth it. Uses the fast model, no tools."""
    import personas
    import usage
    brain = getattr(core, "brain", None)
    client = getattr(brain, "client", None)
    if client is None:
        return None
    before = "; ".join(f"{label} ({m} min)" for label, m in info.get("recent", [])) or "nothing notable"
    now = datetime.now().strftime("%A %I:%M %p").lstrip("0")
    ask = (f"[You're about to start a conversation on your own; the user didn't say anything. They've been in "
           f"{info['what']} for about {info['mins']} minutes. Before that: {before}. It's {now}. "
           "Say one or two short sentences to start a natural, friendly chat about what they're doing, in your own "
           f"voice. {_style_note()} You only know the app and window title "
           "(never claim you saw their screen). If it'd be awkward, pointless or private, reply exactly SKIP.]")
    model = config.FAST_MODEL or config.MODEL
    try:
        msg = client.messages.create(
            model=model, max_tokens=120,
            system=personas.character(config.ADDRESS_AS) + "\nEverything you write is spoken aloud: plain words, "
                   "no lists, emoji or markdown.",
            messages=[{"role": "user", "content": ask}])
        try:
            usage.record_claude(model, msg.usage)
        except Exception:
            pass
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    except Exception as e:
        print(f"[chat first] couldn't write an opener: {e}")
        return None
    if not text or text.upper().startswith("SKIP"):
        print(f"[chat first] nothing worth saying about {info['what']}")
        return None
    return text, ask
