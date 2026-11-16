"""
What he pulls up on the desktop while he answers (ui/desk_pulls.js draws them): a stock with its live chart, the
weather with radar, your day as a timeline, the sources he read, your PC opened up, a preview of a file he just
made, your network, a briefing when a game starts, and trackers (scores, downloads, flights).

Each panel is an event: {"type": "pull", "id", "kind", "data", "ttl", "focus", "live", "where"}. Live ones are
refreshed here (stocks every minute for ten minutes, trackers until they finish), and the page re-arms their timer on
each update. Where each kind sits (left / right / centre / second monitor) is remembered in desk_layout.json.

Settings > His desktop > "Pull things up while he answers" (JUNO_PULLS) turns the automatic ones off; asking for one
("show me my PC") still works.
"""
import json
import os
import re
import socket
import subprocess
import threading
import time
from datetime import datetime, date, timedelta

import config

_CORE = None
_LIVE = {}            # id -> {"fn": callable returning data or None (done), "every": s, "until": t, "next": t, "ttl": s}
_LOCK = threading.Lock()
KINDS = ("stock", "weather", "calendar", "sources", "pc", "file", "network", "briefing", "tracker")
WHERE = ("left", "right", "center", "second")
_WORDS = {"stocks": "stock", "stock": "stock", "market": "stock", "weather": "weather", "radar": "weather",
          "calendar": "calendar", "day": "calendar", "schedule": "calendar", "sources": "sources", "search": "sources",
          "pc": "pc", "computer": "pc", "hardware": "pc", "file": "file", "files": "file", "documents": "file",
          "network": "network", "wifi": "network", "briefing": "briefing", "game": "briefing", "tracker": "tracker",
          "trackers": "tracker", "score": "tracker", "scores": "tracker", "download": "tracker", "flight": "tracker"}


def on():
    return os.environ.get("JUNO_PULLS", "true").lower() != "false"


def _emit(ev):
    core = _CORE
    if core is None or getattr(core, "desk", None) is None:
        return False
    try:
        core.emit(ev)
        return True
    except Exception as e:
        print(f"[pulls] {e}")
        return False


LAST = {"at": 0.0, "focus": False}


def recent(secs=600):
    return time.time() - LAST["at"] < secs


def pull(kind, data, id=None, title=None, ttl=120, focus=False, live=False, where=None, auto=True):
    """Put a panel up. auto=True: only if the setting allows unprompted panels."""
    if auto and not on():
        return False
    LAST["at"] = time.time()
    LAST["focus"] = LAST["focus"] or bool(focus)
    return _emit({"type": "pull", "id": id or kind, "kind": kind, "data": data, "title": title, "ttl": ttl,
                  "focus": bool(focus), "live": bool(live), "where": where})


def update(id, data, ttl=120):
    return _emit({"type": "pull_update", "id": id, "data": data, "ttl": ttl})


def keep_live(id, fn, every, for_secs, ttl=120):
    with _LOCK:
        _LIVE[id] = {"fn": fn, "every": every, "until": time.time() + for_secs, "next": time.time() + every, "ttl": ttl}


def stop_live(id=None, kind=None):
    with _LOCK:
        for k in list(_LIVE):
            if id is None and kind is None or k == id or (kind and k.startswith(kind)):
                _LIVE.pop(k, None)


def clear(kind=None):
    if not kind:
        LAST.update(at=0.0, focus=False)
    stop_live(kind=kind) if kind else stop_live()
    _emit({"type": "pull_clear", **({"kind": kind} if kind else {})})


def focus(kind=None, off=False):
    LAST["focus"] = not off
    _emit({"type": "pull_focus", "off": off, **({"kind": kind} if kind else {})})


# ------------------------------------------------------------------ where things go ("put the stocks on my second monitor")
def _layout_file():
    return config.JARVIS_DIR / "desk_layout.json"


def layout():
    try:
        return json.loads(_layout_file().read_text(encoding="utf-8"))
    except Exception:
        return {}


def move(what, where):
    kind = _WORDS.get((what or "").lower().strip(), (what or "").lower().strip())
    where = {"middle": "center", "centre": "center", "other monitor": "second", "other screen": "second",
             "second screen": "second", "second monitor": "second"}.get((where or "").lower().strip(), (where or "").lower().strip())
    if where not in WHERE:
        return f"Where? Left, right, the middle, or your second monitor."
    if kind in ("widgets", "widget"):
        if _CORE is None:
            return "Not available."
        _CORE.set_widgets({"JUNO_DESK_WIDGETS_WHERE": {"center": "right"}.get(where, where)})
        return f"Widgets moved to the {where}."
    if kind not in KINDS:
        return f"I don't have a panel called {what}. I've got: stocks, weather, calendar, sources, PC, files, network, briefing, trackers."
    lay = layout()
    lay[kind] = where
    try:
        _layout_file().write_text(json.dumps(lay), encoding="utf-8")
    except Exception as e:
        print(f"[pulls] layout: {e}")
    _emit({"type": "pull_layout", "map": lay})
    return f"Done: {kind} panels go {'on your second monitor' if where == 'second' else 'in the middle' if where == 'center' else 'on the ' + where} from now on."


# ------------------------------------------------------------------ 1. stocks
def stock(sym, rng="1d", take=None, focus_it=False, auto=True):
    import stocks
    data = stock_data(sym, rng)
    if not data:
        return None
    if take:
        data["take"] = take
    pid = f"stock-{data['sym']}"
    if pull("stock", data, id=pid, title=data["name"][:28], ttl=600, live=True, focus=focus_it, auto=auto):
        import livefeed
        livefeed.watch([data["sym"]], secs=600)          # every price change, streamed, while it's up
        keep_live(pid, lambda: stock_data(sym, rng), every=300, for_secs=600, ttl=600)   # day range, chart shape
    return data


def stock_data(sym, rng="1d"):
    import stocks
    try:
        q = stocks.quote(sym)
        c = stocks.chart(sym, rng if rng in stocks.RANGES else "1d")
        closes = [x for x in (((c.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []) if x is not None]
        if len(closes) > 160:
            step = len(closes) / 160
            closes = [closes[int(i * step)] for i in range(160)] + [closes[-1]]
    except Exception as e:
        print(f"[pulls] stock {sym}: {e}")
        return None
    return {"sym": q["symbol"], "name": q["name"], "price": q["price"], "change": q["change"], "pct": q["pct"],
            "prev": q["prev"] if rng == "1d" else (closes[0] if closes else None), "closes": closes, "range": rng,
            "day_low": q["day_low"], "day_high": q["day_high"], "low52": q["low52"], "high52": q["high52"],
            "state": q.get("state") or "", "cur": q["currency"]}


# ------------------------------------------------------------------ weather (+ radar)
RAIN_API = "https://api.rainviewer.com/public/weather-maps.json"


def _tile(lat, lon, z):
    import math
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def radar(lat, lon, z=6, n=3):
    """A 3x3 block of map tiles round you, with the latest rain radar frame over them."""
    import briefing
    try:
        m = briefing._get(RAIN_API, {}, timeout=6).json()
        frames = ((m.get("radar") or {}).get("past") or [])[-8:] + ((m.get("radar") or {}).get("nowcast") or [])[:2]
        host = m.get("host") or "https://tilecache.rainviewer.com"
    except Exception as e:
        print(f"[pulls] radar: {e}")
        frames, host = [], "https://tilecache.rainviewer.com"
    fx, fy = _tile(lat, lon, z)
    cx, cy = int(fx), int(fy)
    tiles = []
    for dy in range(-(n // 2), n // 2 + 1):
        for dx in range(-(n // 2), n // 2 + 1):
            x, y = (cx + dx) % (2 ** z), cy + dy
            t = {"base": f"https://{'abcd'[(x + y) % 4]}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
                 "frames": [f"{host}{fr['path']}/256/{z}/{x}/{y}/2/1_1.png" for fr in frames]}
            tiles.append(t)
    return {"n": n, "tiles": tiles, "px": (fx - cx + n // 2) / n, "py": (fy - cy + n // 2) / n,
            "times": [datetime.fromtimestamp(fr["time"]).strftime("%H:%M") for fr in frames],
            "now_from": len([f for f in frames if f.get("time", 0) <= time.time()])}


def weather(place=None, focus_it=False, auto=True):
    import glass_kinds
    try:
        w = glass_kinds.weather(_CORE, place)
        lat, lon, name = glass_kinds._place(_CORE, place)
    except Exception as e:
        return f"Couldn't get the weather ({type(e).__name__})."
    def build():
        w2 = glass_kinds.weather(_CORE, place)
        return {"place": w2["place"], "now": w2["now"], "feels": w2["feels"], "label": w2["label"],
                "hours": [{"t": x["h"].replace(" AM", "a").replace(" PM", "p"), "temp": x["t"], "rain": x["rain"]} for x in w2["hours"][:12]],
                "radar": radar(lat, lon)}
    data = build()
    if pull("weather", data, id="weather", title="Weather", ttl=600, focus=focus_it, live=True, auto=auto):
        keep_live("weather", build, every=600, for_secs=1800, ttl=600)     # new radar frames every 10 minutes
    rain = max((x["rain"] for x in w["hours"][:6]), default=0)
    return (f"{w['place']}: {w['now']}{w['unit']}, {w['label']}, feels {w['feels']}. High {w['high']}, low {w['low']}. "
            f"Rain chance next 6 hours up to {rain}%." + " (Radar is up on their desktop.)")


# ------------------------------------------------------------------ your day
def calendar(focus_it=False, auto=True):
    evs = []
    cal = getattr(_CORE, "calendar", None)
    if cal is not None:
        try:
            for ev, s in cal.day(date.today())[:12]:
                if ev.get("all_day"):
                    continue
                e = ev.get("end")
                try:
                    e = datetime.fromisoformat(str(e)) if e else s + timedelta(minutes=int(ev.get("minutes") or 45))
                except ValueError:
                    e = s + timedelta(minutes=45)
                evs.append({"start": s.strftime("%H:%M"), "end": e.strftime("%H:%M"), "title": ev.get("title", ""),
                            "where": ev.get("location", "")})
        except Exception as e:
            print(f"[pulls] calendar: {e}")
    try:
        import tools
        for r in tools.REMINDERS.items:
            due = datetime.fromisoformat(str(r["due"]))
            if due.date() == date.today():
                evs.append({"start": due.strftime("%H:%M"), "end": "", "title": "⏰ " + r["message"]})
    except Exception:
        pass
    evs.sort(key=lambda x: x["start"])
    pull("calendar", {"day": datetime.now().strftime("%A %d").replace(" 0", " "), "now": datetime.now().strftime("%H:%M"),
                      "events": evs}, id="calendar", title="Today", ttl=120, focus=focus_it, auto=auto)
    return evs


# ------------------------------------------------------------------ sources he read (brain.py calls this after a web search)
def sources(query, items):
    seen, out = set(), []
    for it in items:
        url = it.get("url") or ""
        m = re.match(r"https?://(?:www\.)?([^/]+)", url)
        dom = m.group(1) if m else ""
        if not dom or url in seen:
            continue
        seen.add(url)
        out.append({"domain": dom, "title": (it.get("title") or "")[:120]})
    if len(out) >= 2:
        pull("sources", {"query": (query or "")[:120], "items": out[:6]}, id="sources", title="Sources", ttl=90)


# ------------------------------------------------------------------ 2. your PC, opened up
_HW = {}


def hardware():
    """What's inside this PC (asked once per run: it takes a second or two)."""
    if _HW:
        return _HW
    import platform
    import psutil
    hw = {"name": socket.gethostname(), "ram": f"{round(psutil.virtual_memory().total / 2**30)} GB",
          "os": f"{platform.system()} {platform.release()}", "ram_sticks": 2, "cpu": platform.processor()}
    if os.name == "nt":
        ps = ("$c=Get-CimInstance Win32_Processor|Select -First 1 Name,NumberOfCores;"
              "$g=Get-CimInstance Win32_VideoController|Select Name,AdapterRAM;"
              "$m=@(Get-CimInstance Win32_PhysicalMemory).Count;"
              "$o=Get-CimInstance Win32_OperatingSystem|Select Caption,BuildNumber;"
              "$v=(Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion').DisplayVersion;"
              "@{cpu=$c;gpu=$g;sticks=$m;os=$o;ver=$v}|ConvertTo-Json -Depth 3 -Compress")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=20,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            j = json.loads(r.stdout or "{}")
            c = j.get("cpu") or {}
            hw["cpu"] = f"{(c.get('Name') or '').strip()} ({c.get('NumberOfCores')} cores)" if c.get("Name") else hw["cpu"]
            g = j.get("gpu") or []
            g = g if isinstance(g, list) else [g]
            g = [x for x in g if x.get("Name") and "basic" not in x["Name"].lower()]
            if g:
                best = max(g, key=lambda x: x.get("AdapterRAM") or 0)
                hw["gpu"] = best["Name"]
            hw["ram_sticks"] = int(j.get("sticks") or 2)
            o = j.get("os") or {}
            if o.get("Caption"):
                hw["os"] = o["Caption"].replace("Microsoft ", "") + (f" {j['ver']}" if j.get("ver") else "")
        except Exception as e:
            print(f"[pulls] hardware: {e}")
        try:
            r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode == 0 and r.stdout.strip():
                n, mem = [x.strip() for x in r.stdout.splitlines()[0].split(",")]
                hw["gpu"] = f"{n}, {round(int(mem) / 1024)} GB"
        except Exception:
            pass
    _HW.update(hw)
    return _HW


def drives():
    import psutil
    out = []
    for p in psutil.disk_partitions(all=False):
        if "cdrom" in p.opts or not p.fstype:
            continue
        try:
            u = psutil.disk_usage(p.mountpoint)
        except OSError:
            continue
        out.append({"name": p.mountpoint.rstrip("\\/") or p.mountpoint, "total": u.total / 2**30, "free": u.free / 2**30})
    return out[:4]


def pc(focus_it=False, auto=False):
    hw = dict(hardware())
    hw["drives"] = drives()
    pull("pc", hw, id="pc", title="Your PC", ttl=180, focus=focus_it, live=True, auto=auto)
    return (f"{hw.get('name')}: {hw.get('cpu')}; graphics {hw.get('gpu', 'unknown')}; {hw.get('ram')} memory "
            f"({hw.get('ram_sticks')} sticks); {hw.get('os')}. Drives: " +
            ", ".join(f"{d['name']} {d['free']:.0f} of {d['total']:.0f} GB free" for d in hw["drives"]) +
            ". (It's up on their desktop with live load and temperatures.)")


# ------------------------------------------------------------------ 3. a file he made
def file(path, kind, spec=None, text=None):
    data = {"path": str(path), "kind": kind}
    if spec is not None:
        data["spec"] = spec
    if text is not None:
        data["text"] = text[:3000]
    pull("file", data, id="file", title="Made", ttl=90)


# ------------------------------------------------------------------ 5. pre-game briefing (gamemode.py calls this)
def game_briefing(name):
    if not on() or not getattr(config, "GAME_BRIEFING", True):
        return
    def work():
        data = {"game": name}
        try:
            import gamemode
            w, l = gamemode.WATCH.record() if gamemode.WATCH else (0, 0)
            if w or l:
                data["record"] = {"w": w, "l": l, "streak": ""}
        except Exception:
            pass
        try:
            import steam
            fr = steam.friends_list()
            data["friends"] = [f for f in fr if f.get("game")][:5]
            app = steam.appid_for(name)
            if app:
                items = steam.news(app, 2)
                if items:
                    it = items[0]
                    days = int((time.time() - it.get("date", time.time())) / 86400)
                    body = re.sub(r"\[[^\]]+\]|<[^>]+>|\{[^}]+\}", " ", it.get("contents", ""))
                    lines = [x.strip(" -•*") for x in re.split(r"[\r\n]+", body) if 8 < len(x.strip()) < 110][:3]
                    data["patch"] = {"title": f"{it.get('title', '')[:60]}, {days} day{'s' if days != 1 else ''} ago", "lines": lines}
        except Exception as e:
            print(f"[pulls] briefing steam: {e}")
        if re.search(r"dead by daylight|\bdbd\b", name, re.I):
            try:
                import dbdqueue
                txt, _ = dbdqueue.queue_text()
                lines = [l for l in txt.splitlines() if re.search(r"\d+\s*(m|min|s|sec)\b", l, re.I)][:4]
                if lines:
                    data["queue"] = lines
            except Exception:
                pass
        if len(data) > 1:
            pull("briefing", data, id="briefing", title="Briefing", ttl=90, where="right")
    threading.Thread(target=work, daemon=True, name="game-briefing").start()


# ------------------------------------------------------------------ the live loop
class Loop:
    def __init__(self):
        self._stop = threading.Event()

    def start(self):
        threading.Thread(target=self._run, daemon=True, name="pulls").start()
        return self

    def _run(self):
        self._stop.wait(8)
        if layout():
            _emit({"type": "pull_layout", "map": layout()})
        while not self._stop.wait(1):
            now = time.time()
            with _LOCK:
                due = [(k, v) for k, v in _LIVE.items() if v["next"] <= now]
            for k, v in due:
                if now > v["until"]:
                    stop_live(k)
                    continue
                try:
                    d = v["fn"]()
                except Exception as e:
                    print(f"[pulls] refresh {k}: {e}")
                    d = None
                if d is None:
                    stop_live(k)
                    continue
                update(k, d, v["ttl"])
                if isinstance(d, dict) and d.get("done"):
                    stop_live(k)
                    continue
                with _LOCK:
                    if k in _LIVE:
                        _LIVE[k]["next"] = time.time() + v["every"]


def start(core):
    global _CORE
    _CORE = core
    try:
        import livefeed
        livefeed.start(core.emit)
    except Exception as e:
        print(f"[live] off: {e}")
    return Loop().start()
