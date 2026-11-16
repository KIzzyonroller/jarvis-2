"""
The desktop scene's live details: real things written into the still picture, refreshed every few minutes. Nothing
animates; a label just reads differently the next time you look.

  bench    "listening core, rev. 28" (his real version), "the old bearing squeaked. replaced 11/14" (his last
           update), "Checked: <what he calls you>"
  station  "ORBIT 214" (days you've had him), "NIGHTSIDE IN 2:41" / "DAYSIDE IN 9:05" (your real sunset/sunrise)
  archive  "The catalogue: 37 cards, 4 routines, kept since March" (what he remembers about you)
  signal   "CH2 HOUSE 18°C  CH3 NETWORK 23 ms" (outside temperature, internet latency)
  chart    the four places are named after the apps you've used most this week (needs activity memory on;
           otherwise Render Ridge, Queue Basin, Mount Inbox, Patchnote Shoals)
"""
import re
import socket
import threading
import time
from datetime import datetime, timedelta

import config

EVERY = 5 * 60
SHAPES = ["{} Ridge", "{} Basin", "Mount {}", "{} Shoals"]
SKIP_APPS = re.compile(r"^(explorer|jarvis|jarvis desktop|windows|search|start|lockapp|task ?manager|settings|"
                       r"shellexperiencehost|applicationframehost|textinputhost)$", re.I)


def _since_first_run():
    """Days since he was first set up (the oldest thing in his folder)."""
    try:
        times = [p.stat().st_ctime for p in config.JARVIS_DIR.iterdir()]
        return max(1, int((time.time() - min(times)) / 86400) + 1) if times else 1, min(times) if times else time.time()
    except Exception:
        return 1, time.time()


def _version_bits():
    try:
        v = (config.RES_DIR / "VERSION").read_text(encoding="utf-8").strip()
        when = datetime.fromtimestamp((config.RES_DIR / "VERSION").stat().st_mtime)
    except Exception:
        return "?", None
    return v.split(".")[-1], when


def _sun(core):
    """The next sunset and sunrise, plus the temperature outside, from open-meteo (asked every 30 minutes)."""
    import briefing
    import moments
    if time.time() - _SUN.get("at", 0) > 1800:
        loc = moments._loc(core)
        if not loc:
            return None
        f = (config.COUNTRY or loc[3] or "").upper() == "US"
        j = briefing._get("https://api.open-meteo.com/v1/forecast", {
            "latitude": loc[0], "longitude": loc[1], "timezone": "auto", "forecast_days": 2,
            "daily": "sunrise,sunset", "current": "temperature_2m",
            "temperature_unit": "fahrenheit" if f else "celsius"}).json()
        d = j.get("daily") or {}
        _SUN.update(at=time.time(), rise=[datetime.fromisoformat(x) for x in d.get("sunrise", [])],
                    set=[datetime.fromisoformat(x) for x in d.get("sunset", [])],
                    temp=(j.get("current") or {}).get("temperature_2m"), unit="F" if f else "C")
    now = datetime.now()
    nxt_set = next((t for t in _SUN.get("set", []) if t > now), None)
    nxt_rise = next((t for t in _SUN.get("rise", []) if t > now), None)
    return nxt_set, nxt_rise


_SUN = {}


def _hm(td):
    m = max(0, int(td.total_seconds() // 60))
    return f"{m // 60}:{m % 60:02d}"


def _latency():
    """One TCP handshake to Cloudflare, in milliseconds. Not a ping (no admin rights needed), close enough."""
    t = time.perf_counter()
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=2):
            return round((time.perf_counter() - t) * 1000)
    except OSError:
        return None


def _top_apps(n=4):
    import tools
    tr = getattr(tools, "_ACTIVITY", None)
    if tr is None or not getattr(tr, "running", False):
        return []
    tally = {}
    now = datetime.now()
    for r in tr.sessions(now - timedelta(days=7), now):
        app = (r.get("app") or "").strip()
        if not app or SKIP_APPS.match(app):
            continue
        tally[app] = tally.get(app, 0) + (r["e"] - r["s"])
    names = sorted(tally, key=lambda a: -tally[a])[:n]
    return [re.sub(r"\.exe$", "", a, flags=re.I).strip().title()[:18] for a in names]


def gather(core):
    import tools
    out = {}
    days, born = _since_first_run()
    rev, updated = _version_bits()
    out["bench"] = {"rev": rev, "address": (config.ADDRESS_AS or "you"),
                    "fix": f"last tune-up installed {updated:%m/%d}" if updated else "the old bearing squeaked. replaced 11/05"}
    st = {"days": f"{days:,}"}
    try:
        s = _sun(core)
        if s:
            nxt_set, nxt_rise = s
            now = datetime.now()
            if nxt_set and (not nxt_rise or nxt_set < nxt_rise):
                st["night"] = f" · NIGHTSIDE IN {_hm(nxt_set - now)}"
            elif nxt_rise:
                st["night"] = f" · DAYSIDE IN {_hm(nxt_rise - now)}"
    except Exception as e:
        print(f"[desk facts] sun: {type(e).__name__}")
    out["station"] = st
    try:
        mem, rts = len(tools.memories()), len(tools.routines() or {})
    except Exception:
        mem, rts = 0, 0
    out["archive"] = {"memories": mem, "routines": rts, "since": datetime.fromtimestamp(born).strftime("%B %Y")}
    sig = {}
    if _SUN.get("temp") is not None:
        sig["house"] = f"{round(_SUN['temp'])}°{_SUN.get('unit', '')}"
    ms = _latency()
    sig["net"] = f"{ms} ms" if ms is not None else "OFFLINE"
    out["signal"] = sig
    apps = _top_apps()
    if len(apps) == 4:
        out["chart"] = {f"p{i + 1}": SHAPES[i].format(a) for i, a in enumerate(apps)}
    return out


class DeskFacts:
    def __init__(self, core):
        self.core = core
        self._stop = threading.Event()

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="desk-facts").start()
        return self

    def stop(self):
        self._stop.set()

    def _loop(self):
        self._stop.wait(20)
        while not self._stop.is_set():
            if getattr(self.core, "desk", None) is not None:
                try:
                    self.core.emit({"type": "desk_facts", "facts": gather(self.core)})
                except Exception as e:
                    print(f"[desk facts] {type(e).__name__}: {e}")
            self._stop.wait(EVERY)


def start(core):
    return DeskFacts(core).start()
