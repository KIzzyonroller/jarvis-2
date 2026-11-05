"""
Widgets on her desktop: the live cards from glass mode, always on the wallpaper. PC stats (processor, memory,
graphics card, temperature, network), now playing, the weather, today's calendar, sticky notes / checklists / timers
from glass mode, and Discord messages as they come in.

The wallpaper takes no clicks, so these are to look at. Settings > Appearance & animations > Desktop widgets picks
which ones show and on which side or monitor. Nothing is collected while a fullscreen game or video is in front.

Most numbers come from things the app already measures (the 'telemetry' event every 2 s, Discord events); this adds
the graphics card (nvidia-smi), what's playing, the weather (Open-Meteo, every 20 min), today's calendar and the
glass-mode notes, and pushes them to ui/desk_widgets.js.
"""
import threading
import time

import config

KINDS = ("stats", "music", "weather", "calendar", "notes", "discord")


def enabled():
    """Which widgets are on, from Settings."""
    if not config.DESK_WIDGETS:
        return []
    return [k for k in KINDS if config.DESK_WIDGET_ON.get(k, True)]


def config_event():
    return {"type": "widgets", "on": enabled(), "where": config.DESK_WIDGETS_WHERE}


class DeskWidgets:
    def __init__(self, desk, core):
        self.desk, self.core = desk, core
        self._stop = threading.Event()
        self._due = {}
        self._last = {}

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="desk-widgets").start()
        return self

    def stop(self):
        self._stop.set()

    def refresh(self):
        """Settings changed: tell the page, and fetch anything newly switched on straight away."""
        self._due.clear()
        self._last.clear()
        self.desk.feed(config_event())

    def _every(self, key, secs):
        now = time.time()
        if now >= self._due.get(key, 0):
            self._due[key] = now + secs
            return True
        return False

    def _send(self, ev, key):
        """Only when something changed (no point redrawing the same weather every 2 seconds)."""
        if self._last.get(key) == ev:
            return
        self._last[key] = ev
        self.desk.feed(ev)

    def _loop(self):
        import glass_kinds
        self._stop.wait(8)                          # let the desktop and her intro come up first
        self.desk.feed(config_event())
        while not self._stop.wait(2):
            on = enabled()
            if not on or not getattr(self.desk, "attached", False) or getattr(self.desk, "paused", False):
                continue
            try:
                if "stats" in on and self._every("gpu", 4):
                    g = glass_kinds.gpu()
                    if g:
                        self._send(dict(g, type="w_gpu"), "gpu")
                if "music" in on:
                    self._send({"type": "w_np", "data": glass_kinds.nowplaying(self.core)}, "np")
                if "weather" in on and self._every("weather", 20 * 60):
                    try:
                        self._send({"type": "w_weather", "data": glass_kinds.weather(self.core)}, "weather")
                    except Exception as e:
                        self._due["weather"] = time.time() + 120          # offline? try again in a couple of minutes
                        print(f"[widgets] weather: {e}")
                if "calendar" in on and self._every("cal", 5 * 60):
                    self._send({"type": "w_cal", "data": glass_kinds.calendar(self.core)}, "cal")
                if "notes" in on and self._every("notes", 6):
                    self._send({"type": "w_notes", "data": self._notes()}, "notes")
            except Exception as e:
                print(f"[widgets] {e}")

    def _notes(self):
        """Sticky notes and checklists saved by glass mode, and any timers running on the glass."""
        import glass_kinds
        st = glass_kinds.load()
        notes = [{"title": n.get("title") or "Note", "text": n.get("text", "")} for n in st.get("notes", [])][-4:]
        lists = [{"title": t.title(), "items": items[:8]} for t, items in list(st.get("lists", {}).items())[-2:]]
        timers = []
        hub = getattr(self.core, "glass", None)
        if hub is not None:
            try:
                with hub.lock:
                    for c in hub.cards.values():
                        if c.get("kind") == "timer":
                            d = c.get("data") or {}
                            timers.append({"label": c.get("title") or "Timer", "end": d.get("end"), "total": d.get("total")})
            except Exception:
                pass
        return {"notes": notes, "lists": lists, "timers": timers}


WIDGETS = None


def start(desk, core):
    global WIDGETS
    if WIDGETS is None and desk is not None:
        WIDGETS = DeskWidgets(desk, core).start()
    return WIDGETS
