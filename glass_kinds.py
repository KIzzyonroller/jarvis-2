"""
Glass mode's richer cards: the data behind each kind, and what the page may ask the PC to do when you pinch a
control on one. glass.py serves them; the page (ui/glass.html) draws them and handles your hands.

  Live:        timer, stopwatch, stats (CPU, RAM, GPU), nowplaying (with buttons), weather (hourly strip),
               calendar (today, counting down to the next thing), progress, feed (Discord and alerts)
  Interactive: checklist (remembered), sliders (volume, brightness), launcher (your apps), sticky (a note that
               stays), approval (her yes/no questions, made automatically), windows (your open windows)
  Visual:      chart (bar or line), map (a place, OpenStreetMap), youtube (pinch to play), photos (a folder of
               pictures to flick through), model (a .glb / .gltf 3D model you can spin)

What the page can ask for is narrow on purpose: only things on a card that's actually up (an app from that
launcher, a window from that list, a video from that card), plus media keys, volume and brightness.
"""
import json
import re
import secrets
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import config

IS_WINDOWS = sys.platform == "win32"
STORE = config.JARVIS_DIR / "glass.json"         # checklists, sticky notes and pinned cards, between sessions
MODEL_EXT = {".glb", ".gltf"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
DEFAULT_APPS = ["Chrome", "Discord", "Spotify", "Steam", "Blender", "File Explorer", "Notepad", "Calculator"]
KINDS = {"game", "timer", "stopwatch", "stats", "nowplaying", "weather", "calendar", "progress", "checklist", "sliders",
         "launcher", "sticky", "chart", "map", "youtube", "photos", "model", "windows", "feed"}


# ------------------------------------------------------------------ remembered things
def load():
    try:
        d = json.loads(STORE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save(d):
    try:
        STORE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STORE.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1), encoding="utf-8")
        tmp.replace(STORE)
    except Exception as e:
        print(f"[glass] couldn't save: {e}")


# ------------------------------------------------------------------ building each kind
def _secs(text):
    """'5 minutes', '1h30m', '90', '2:30' -> seconds."""
    s = str(text or "").strip().lower()
    if not s:
        return 0
    m = re.fullmatch(r"(\d+):(\d{1,2})(?::(\d{1,2}))?", s)
    if m:
        a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
        return a * 3600 + b * 60 + c if m.group(3) else a * 60 + b
    total = 0
    for n, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(h|hr|hour|hours|m|min|mins|minute|minutes|s|sec|secs|second|seconds)?", s):
        n = float(n)
        total += n * (3600 if unit and unit.startswith("h") else 1 if unit and unit.startswith("s") else 60)
    return int(total)


def _place(core, place):
    """(lat, lon, name) for a place name, or her usual location."""
    import briefing
    if place:
        r = briefing._get("https://geocoding-api.open-meteo.com/v1/search", {"name": place, "count": 1}).json()
        hit = (r.get("results") or [None])[0]
        if not hit:
            raise ValueError(f"Couldn't find a place called {place}.")
        return hit["latitude"], hit["longitude"], ", ".join(x for x in (hit.get("name"), hit.get("admin1") or hit.get("country")) if x)
    import moments
    loc = moments._loc(core)
    if not loc:
        raise ValueError("I don't know where you are: set your city in Settings.")
    return loc[0], loc[1], loc[2]


def weather(core, place=None):
    import briefing
    lat, lon, name = _place(core, place)
    f = (config.COUNTRY or "").upper() == "US"
    d = briefing._get("https://api.open-meteo.com/v1/forecast", {
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 2,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,weather_code,precipitation_probability",
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit" if f else "celsius"}, timeout=6).json()
    cur, h, dl = d.get("current", {}), d.get("hourly", {}), d.get("daily", {})
    now = datetime.now()
    hours = []
    for t, temp, code, rain in zip(h.get("time", []), h.get("temperature_2m", []), h.get("weather_code", []),
                                   h.get("precipitation_probability", [])):
        at = datetime.fromisoformat(t)
        if at >= now.replace(minute=0, second=0, microsecond=0) and len(hours) < 24:
            hours.append({"h": at.strftime("%I %p").lstrip("0"), "t": round(temp), "code": code, "rain": rain or 0})
    return {"place": name, "unit": "°F" if f else "°C", "now": round(cur.get("temperature_2m", 0)),
            "feels": round(cur.get("apparent_temperature", 0)), "code": cur.get("weather_code", 0),
            "label": briefing.WMO.get(cur.get("weather_code"), ""), "wind": round(cur.get("wind_speed_10m", 0)),
            "high": round((dl.get("temperature_2m_max") or [0])[0]), "low": round((dl.get("temperature_2m_min") or [0])[0]),
            "hours": hours}


def calendar(core):
    """Today's events and reminders, with times the page counts down to."""
    out = []
    cal = getattr(core, "calendar", None)
    if cal is not None:
        try:
            import cal_store as cs
            for ev, s in cal.day(date.today())[:10]:
                out.append({"at": s.timestamp() * 1000, "time": "All day" if ev.get("all_day") else cs.nice_time(s),
                            "text": ev.get("title", ""), "all_day": bool(ev.get("all_day"))})
        except Exception as e:
            print(f"[glass] calendar: {e}")
    try:
        import tools
        for r in tools.REMINDERS.items:
            due = datetime.fromisoformat(str(r["due"]))
            if due.date() == date.today():
                out.append({"at": due.timestamp() * 1000, "time": due.strftime("%I:%M %p").lstrip("0"), "text": r["message"]})
    except Exception:
        pass
    out.sort(key=lambda x: (not x.get("all_day"), x["at"]))
    return {"items": out, "day": datetime.now().strftime("%A, %B %d").replace(" 0", " ")}


def game_data(name):
    """Your notes and quick timers for a game (glass.json > games), made by voice."""
    g = load().get("games", {}).get(name.lower(), {})
    return {"name": name, "notes": list(g.get("notes", []))[:12], "timers": list(g.get("timers", []))[:8]}


def game_edit(name, note=None, timer=None, seconds=None, remove=None):
    """Add a note or a quick timer to a game, or remove one (by text or label). Returns the new data."""
    st = load()
    g = st.setdefault("games", {}).setdefault(name.lower(), {"notes": [], "timers": []})
    if note:
        g["notes"] = [n for n in g["notes"] if n.lower() != note.lower()] + [str(note)[:160]]
    if timer and seconds:
        g["timers"] = [t for t in g["timers"] if t["label"].lower() != timer.lower()] + [{"label": str(timer)[:30], "secs": int(seconds)}]
    if remove:
        r = remove.lower()
        g["notes"] = [n for n in g["notes"] if r not in n.lower()]
        g["timers"] = [t for t in g["timers"] if r not in t["label"].lower()]
    save(st)
    return game_data(name)


def launcher(core, apps=None):
    apps = [str(a).strip()[:40] for a in (apps or []) if str(a).strip()][:12]
    if not apps:
        tr = getattr(core, "activity", None)            # your most used apps this week, if activity memory is on
        try:
            if tr is not None:
                from collections import Counter
                c = Counter()
                for r in tr.sessions(time.time() - 7 * 86400, time.time()):
                    if not r.get("idle"):
                        c[r["app"]] += r["e"] - r["s"]
                apps = [a for a, _ in c.most_common(8)]
        except Exception:
            apps = []
    return {"apps": apps or DEFAULT_APPS}


def windows():
    if not IS_WINDOWS:
        return {"wins": []}
    import tools
    seen, wins = set(), []
    for w in tools._windows():
        h = int(getattr(w, "_hWnd", 0) or 0)
        if h and w.title not in seen and not w.title.startswith(("J.U.N.O.", "J.A.R.V.I.S.", "U.L.T.R.O.N.")) and "Glass" not in w.title:
            seen.add(w.title)
            wins.append({"h": h, "title": w.title[:80], "min": bool(getattr(w, "isMinimized", False))})
    return {"wins": wins[:14]}


def youtube(query=None, video=None):
    import youtube as yt
    if video:
        m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", str(video)) or re.fullmatch(r"([\w-]{11})", str(video))
        if not m:
            raise ValueError("That isn't a YouTube link.")
        return {"videos": [{"id": m.group(1), "title": "", "channel": "", "length": ""}]}
    res = yt.search(query, limit=6)
    return {"videos": [{k: v.get(k, "") for k in ("id", "title", "channel", "length")} for v in res[:6]]}


def map_card(core, place=None, zoom=13):
    lat, lon, name = _place(core, place)
    return {"lat": lat, "lon": lon, "zoom": max(3, min(17, int(zoom or 13))), "place": name}


def chart(labels, values, chart_type="bar", unit=""):
    labels = [str(x)[:24] for x in (labels or [])][:24]
    vals = []
    for v in (values or [])[:len(labels) or 24]:
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            vals.append(0.0)
    if not vals:
        raise ValueError("A chart needs some values.")
    labels = (labels + [""] * len(vals))[:len(vals)]
    return {"labels": labels, "values": vals, "type": "line" if str(chart_type).lower() == "line" else "bar",
            "unit": str(unit or "")[:12]}


def photos(hub, folder):
    import tools
    p = tools._resolve(str(folder or ""), config.HOME)
    if not tools._readable(p):
        raise ValueError("That folder is somewhere I'm not allowed to look.")
    if not p.is_dir():
        raise ValueError(f"There's no folder at {p}.")
    files = sorted((f for f in p.iterdir() if f.suffix.lower() in IMAGE_EXT and f.is_file()),
                   key=lambda f: f.stat().st_mtime, reverse=True)[:40]
    if not files:
        raise ValueError("No pictures in that folder.")
    return {"images": [hub.register(f) for f in files], "folder": p.name}


def model(hub, file):
    import tools
    p = tools._resolve(str(file or ""), config.HOME)
    if p.suffix.lower() not in MODEL_EXT:
        raise ValueError("3D models have to be .glb or .gltf (in Blender: File > Export > glTF 2.0).")
    if not tools._readable(p):
        raise ValueError("That file is somewhere I'm not allowed to look.")
    if not p.is_file():
        raise ValueError(f"There's no file at {p}.")
    if p.stat().st_size > 80 * 2**20:
        raise ValueError("That model is too big for the glass (over 80 MB).")
    return {"url": hub.register(p), "name": p.stem}


def build(hub, core, kind, args):
    """The data for a new card of this kind, or raises ValueError with a plain reason."""
    a = args or {}
    if kind == "timer":
        sv = a.get("seconds")
        secs = int(float(sv)) if isinstance(sv, (int, float)) or re.fullmatch(r"\d+(\.\d+)?", str(sv or "").strip()) else \
            _secs(sv or a.get("body") or a.get("value"))
        if secs <= 0:
            raise ValueError("How long? Give the timer seconds, like 300 or '5 minutes'.")
        return {"total": secs, "end": (time.time() + secs) * 1000, "label": a.get("title") or "Timer"}
    if kind == "stopwatch":
        return {"start": time.time() * 1000}
    if kind == "game":
        name = (a.get("title") or "").strip()
        if not name:
            import gamemode
            name = gamemode.playing() or ""
        if not name:
            raise ValueError("Which game? (Not playing one right now.)")
        return game_data(name)
    if kind in ("stats", "nowplaying", "sliders", "feed"):
        d = {}
        if kind == "sliders":
            import tools
            v = tools.volume_state() if IS_WINDOWS else None
            d = {"volume": v[0] if v else 50, "brightness": _brightness()}
        if kind == "nowplaying":
            d = nowplaying(core) or {}
        return d
    if kind == "weather":
        return weather(core, a.get("place"))
    if kind == "calendar":
        return calendar(core)
    if kind == "progress":
        return {"value": float(a.get("value") or 0), "max": float(a.get("max") or 100) or 100}
    if kind == "checklist":
        title = (a.get("title") or "Checklist").strip()
        mem = load().get("lists", {}).get(title.lower())
        items = a.get("items") or []
        if mem and not items:
            return {"items": mem}
        done = {i["t"]: i["done"] for i in (mem or [])}
        return {"items": [{"t": str(t)[:200], "done": bool(done.get(str(t)[:200]))} for t in items][:20]}
    if kind == "launcher":
        return launcher(core, a.get("items"))
    if kind == "sticky":
        return {"text": str(a.get("body") or a.get("title") or "")[:600]}
    if kind == "chart":
        return chart(a.get("items") or a.get("labels"), a.get("values"), a.get("chart_type"), a.get("unit"))
    if kind == "map":
        return map_card(core, a.get("place") or a.get("body"), a.get("zoom"))
    if kind == "youtube":
        return youtube(a.get("query") or a.get("body") or a.get("title"), a.get("video"))
    if kind == "photos":
        return photos(hub, a.get("folder") or a.get("file"))
    if kind == "model":
        return model(hub, a.get("file"))
    if kind == "windows":
        return windows()
    raise ValueError(f"Unknown card kind {kind}.")


def _brightness():
    try:
        import screen_brightness_control as sbc
        b = sbc.get_brightness()
        return int(b[0] if isinstance(b, list) else b)
    except Exception:
        return None


def nowplaying(core):
    m = getattr(core, "music", None)
    t = getattr(m, "track", None) if m else None
    if t and t.get("title"):
        pos = t.get("pos", 0) + ((time.time() - t.get("at", time.time())) if t.get("playing") else 0)
        return {"title": t.get("title"), "artist": t.get("artist", ""), "playing": bool(t.get("playing")),
                "pos": round(pos, 1), "dur": t.get("dur", 0), "app": t.get("app", "")}
    try:
        import netflix
        for s in netflix.media_sessions() or []:
            return {"title": s.get("title", ""), "artist": s.get("artist", ""), "playing": bool(s.get("playing")),
                    "pos": 0, "dur": 0, "app": s.get("app", "")}
    except Exception:
        pass
    return None


def gpu():
    """NVIDIA GPU use, temperature and memory via nvidia-smi (other GPUs: None)."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total,name",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=3,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip().splitlines()
        u, t, mu, mt, name = [x.strip() for x in out[0].split(",")][:5]
        return {"gpu": float(u), "gpu_temp": float(t), "vram": round(float(mu) / 1024, 1),
                "vram_total": round(float(mt) / 1024, 1), "gpu_name": name}
    except Exception:
        return None


# ------------------------------------------------------------------ what a pinch on a card can do
def act(hub, core, d):
    """The page asks for something because you pinched a control. Returns (ok, message)."""
    do = str(d.get("do") or "")
    card = hub.cards.get(_int(d.get("card")))
    import tools
    if do == "desk_fallback":
        if not hub.on_desktop():
            return False, ""
        hub.desk_fallback(str(d.get("why") or "")[:80])
        return True, ""
    if do == "media":
        what = {"toggle": "toggle", "next": "next", "prev": "prev"}.get(d.get("what"))
        if not what:
            return False, "bad"
        m = getattr(core, "music", None)
        if m is not None and getattr(m, "track", None):
            m.cmds.put((what,))
        elif IS_WINDOWS:
            tools.media_control({"toggle": "play_pause", "next": "next", "prev": "previous"}[what])
        return True, ""
    if do == "volume":
        tools.set_volume(level=max(0, min(100, float(d.get("v", 50)))))
        return True, ""
    if do == "brightness":
        tools.brightness(max(0, min(100, float(d.get("v", 50)))))
        return True, ""
    if do == "launch":
        app = str(d.get("app") or "")
        if not card or card["kind"] != "launcher" or app not in card["data"].get("apps", []):
            return False, "not on the launcher"
        tools.open_app(app, front=True, wait=False)
        return True, f"Opening {app}."
    if do == "window":
        h = _int(d.get("h"))
        if not card or card["kind"] != "windows" or h not in {w["h"] for w in card["data"].get("wins", [])}:
            return False, "not on the list"
        return _window(h, str(d.get("what") or "focus"))
    if do == "windows_refresh":
        if card and card["kind"] == "windows":
            card["data"] = windows()
            hub._push({"type": "update", "id": card["id"], "data": card["data"]})
        return True, ""
    if do == "youtube":
        vid = str(d.get("id") or "")
        if not card or card["kind"] != "youtube" or vid not in {v["id"] for v in card["data"].get("videos", [])}:
            return False, "not on the card"
        tools.open_url(f"https://www.youtube.com/watch?v={vid}", front=True)
        return True, "Playing it on your PC."
    if do == "check":
        if not card or card["kind"] != "checklist":
            return False, "no list"
        i = _int(d.get("i"))
        items = card["data"]["items"]
        if i is None or not 0 <= i < len(items):
            return False, "no item"
        items[i]["done"] = bool(d.get("done"))
        st = load()
        st.setdefault("lists", {})[(card["title"] or "Checklist").lower()] = items
        save(st)
        return True, ""
    if do == "confirm":
        ok = core is not None and core.resolve_confirm(d.get("id"), bool(d.get("yes")))
        return bool(ok), ""
    if do == "say":                             # a gesture answered her (thumbs, a number, read this out)
        text = str(d.get("text") or "").strip()[:300]
        if text and core is not None:
            core.submit(text, source="glass")
        return True, ""
    if do == "screenshot":
        c, err = hub.put("Your screen", image="screenshot", stage=True)
        return c is not None, err or ""
    if do == "restore":
        return hub.restore(d.get("card"))
    if do == "pin":
        return hub.pin(_int(d.get("card")), bool(d.get("on")))
    if do == "sticky_done":
        if card and card["kind"] == "sticky":
            hub.remove(card["id"])
        return True, ""
    return False, "unknown"


def _window(h, what):
    import ctypes
    u = ctypes.windll.user32
    if not u.IsWindow(h):
        return False, "That window's gone."
    if what == "focus":
        if u.IsIconic(h):
            u.ShowWindow(h, 9)                          # SW_RESTORE
        import tools
        tools._force_foreground(h)
        return True, ""
    if what == "close":
        u.PostMessageW(h, 0x0010, 0, 0)                 # WM_CLOSE: the app asks to save if it needs to
        return True, ""
    if what == "monitor":                               # over to the other monitor (Win+Shift+arrow)
        import tools
        tools._force_foreground(h)
        time.sleep(.15)
        import pyautogui
        pyautogui.hotkey("win", "shift", "right")
        return True, ""
    return False, "bad"


def _int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def new_token():
    return secrets.token_urlsafe(8)
