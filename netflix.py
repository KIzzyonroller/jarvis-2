"""
Netflix: open it the way you ask (website or the Windows app), and keep a log of what you watch.

Netflix has no public API, so the log comes from two places:
  * Live, on this PC: every 20 seconds he looks at what Windows says is playing (the same info as the media
    controls in the volume pop-up) and which windows are open. That gives WHEN and HOW LONG you watched, and
    via web or app. Netflix often doesn't tell Windows the show's name, so the title can be missing here.
  * Your viewing history from Netflix: Netflix > Account > your profile > Viewing activity > "Download all".
    Leave the NetflixViewingHistory.csv in Downloads and he imports it by himself (titles and dates).
Ask "what did I watch on Netflix this week?" and he puts both together. Everything stays in
Documents\\Jarvis\\watch_log.json on this PC.
"""
import asyncio
import csv
import json
import re
import threading
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import config

WEB = "https://www.netflix.com"
POLL = 20                     # seconds between looks
END_AFTER = 120               # a session ends after this long with no Netflix
MIN_MINUTES = 3               # shorter than this isn't "watching" (trailers, browsing)
GENERIC = {"", "netflix", "netflix app"}
_LOCK = threading.Lock()


def _log_path():
    return config.JARVIS_DIR / "watch_log.json"


def _load():
    try:
        d = json.loads(_log_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    d.setdefault("sessions", [])
    d.setdefault("history", [])
    d.setdefault("imported", {})
    return d


def _save(d):
    p = _log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


# =================================================================== opening it
def app_installed():
    import tools
    try:
        return bool(tools._best_match("netflix", tools._start_apps().keys()) or
                    tools._best_match("netflix", tools._shortcuts().keys()))
    except Exception:
        return False


def open_netflix(query=None, where="auto"):
    """where: web, app, or auto (the app if it's installed and there's nothing to search, else the website)."""
    import tools
    q = (query or "").strip()
    w = (where or "auto").lower()
    if w == "auto":
        w = config.NETFLIX_DEFAULT if config.NETFLIX_DEFAULT in ("web", "app") else ("app" if app_installed() and not q else "web")
    if w == "app":
        if not app_installed():
            return "The Netflix app isn't installed (it's in the Microsoft Store). Say 'on the web' and I'll use the website."
        out = tools.open_app("netflix", front=True)
        if q:
            out += f" The app can't be searched from outside, so search for {q} in it, or ask me to use the website."
        return out
    url = f"{WEB}/search?q={urllib.parse.quote(q)}" if q else f"{WEB}/browse"
    return tools.open_url(url, front=True) + (f" Showing Netflix results for {q}; pick one to start it." if q else "")


# =================================================================== what's on right now
def media_sessions():
    """What Windows' media controls know: [{app, title, artist, playing}]. Empty if unavailable."""
    try:
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
    except Exception:
        return []

    async def go():
        mgr = await Manager.request_async()
        out = []
        for s in mgr.get_sessions():
            try:
                playing = int(s.get_playback_info().playback_status) == 4          # 4 = Playing
            except Exception:
                playing = False
            title = artist = ""
            try:
                props = await s.try_get_media_properties_async()
                title, artist = props.title or "", props.artist or ""
            except Exception:
                pass
            out.append({"app": s.source_app_user_model_id or "", "title": title, "artist": artist, "playing": playing})
        return out
    try:
        return asyncio.run(go())
    except Exception:
        return []


def window_titles():
    try:
        import pygetwindow as gw
        return [(w.title or "").strip() for w in gw.getAllWindows() if (w.title or "").strip()]
    except Exception:
        return []


BROWSERS = ("chrome", "msedge", "firefox", "brave", "opera", "vivaldi")


def detect(sessions=None, titles=None):
    """Is Netflix on right now? Returns {"via": "app"|"web", "title": str|None, "sure": bool} or None.
    sure = Windows says something is actually playing (not just Netflix sitting open on the home screen)."""
    sessions = media_sessions() if sessions is None else sessions
    titles = window_titles() if titles is None else titles
    for s in sessions:
        if "netflix" in s["app"].lower():
            if not s["playing"]:
                return None
            return {"via": "app", "title": _clean_title(s["title"], s["artist"]), "sure": True}
    for s in sessions:                                   # a browser playing something with Netflix in its window
        if s["playing"] and any(b in s["app"].lower() for b in BROWSERS):
            if "netflix" in (s["title"] + " " + s["artist"]).lower() or any(re.search(r"\bnetflix\b", t, re.I) for t in titles):
                t = _clean_title(s["title"], s["artist"])
                return {"via": "web", "title": t, "sure": True}
    if not sessions:                                     # media info unavailable: fall back to window titles
        for t in titles:
            if re.search(r"\bnetflix\b", t, re.I):
                via = "web" if re.search(r"(chrome|edge|firefox|brave|opera|vivaldi)\s*$", t, re.I) else "app"
                return {"via": via, "title": None, "sure": False}
    return None


def _clean_title(title, artist=""):
    t = re.sub(r"\s*[-|]\s*Netflix\s*$", "", (title or "").strip(), flags=re.I)
    if t.lower() in GENERIC:
        t = ""
    if artist and artist.lower() not in GENERIC and artist.lower() not in t.lower():
        t = f"{artist}: {t}" if t else artist
    return t or None


class WatchTracker:
    def __init__(self, on_finished=None, log=print):
        self.on_finished = on_finished or (lambda s: None)
        self.log = log
        self.current = None
        self._stop = threading.Event()

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="netflix-watch").start()

    def stop(self):
        self._stop.set()
        self._close()

    def _loop(self):
        while not self._stop.wait(POLL):
            try:
                self.tick()
            except Exception as e:
                self.log(f"[netflix] {type(e).__name__}: {e}")
            try:
                import_downloads()
            except Exception:
                pass

    def tick(self, now=None, found="detect"):
        now = now or time.time()
        hit = detect() if found == "detect" else found
        cur = self.current
        if hit:
            if cur is None:
                self.current = {"start": now, "last": now, "via": hit["via"], "titles": [], "sure": hit["sure"]}
                cur = self.current
            cur["last"] = now
            cur["sure"] = cur["sure"] or hit["sure"]
            if hit["title"] and (not cur["titles"] or cur["titles"][-1] != hit["title"]):
                cur["titles"].append(hit["title"])
        elif cur is not None and now - cur["last"] > END_AFTER:
            self._close()

    def _close(self):
        cur, self.current = self.current, None
        if not cur:
            return
        minutes = round((cur["last"] - cur["start"]) / 60)
        if minutes < MIN_MINUTES:
            return
        s = {"start": datetime.fromtimestamp(cur["start"]).isoformat(timespec="minutes"), "minutes": minutes,
             "via": cur["via"], "titles": cur["titles"][:6], "sure": cur["sure"]}
        with _LOCK:
            d = _load()
            d["sessions"] = (d["sessions"] + [s])[-1000:]
            _save(d)
        self.on_finished(s)


# =================================================================== Netflix's own viewing history (CSV)
def import_csv(path):
    """NetflixViewingHistory.csv: columns Title, Date (in your Netflix region's date format)."""
    path = Path(path)
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            title, date = (r.get("Title") or "").strip(), (r.get("Date") or "").strip()
            when = _parse_date(date)
            if title and when:
                rows.append({"title": title, "date": when})
    if not rows:
        return 0
    with _LOCK:
        d = _load()
        have = {(h["title"], h["date"]) for h in d["history"]}
        new = [r for r in rows if (r["title"], r["date"]) not in have]
        d["history"] = sorted(d["history"] + new, key=lambda h: h["date"])[-5000:]
        d["imported"][path.name] = path.stat().st_mtime
        _save(d)
    return len(new)


def _parse_date(s):
    for fmt in ("%m/%d/%y", "%d/%m/%y", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%y", "%d.%m.%Y"):
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if dt <= datetime.now() + timedelta(days=1):
            return dt.date().isoformat()
    return None


def import_downloads():
    """Pick up a new NetflixViewingHistory*.csv from Downloads by itself. Returns how many titles were added."""
    dl = config.HOME / "Downloads"
    total = 0
    try:
        files = sorted(dl.glob("NetflixViewingHistory*.csv"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return 0
    d = _load()
    for p in files:
        if d["imported"].get(p.name) == p.stat().st_mtime:
            continue
        try:
            total += import_csv(p)
        except Exception:
            continue
    return total


# =================================================================== answering "what did I watch?"
def recent(days=7, query=""):
    days = max(1, int(float(days or 7)))
    cutoff = datetime.now() - timedelta(days=days)
    d = _load()
    q = (query or "").lower().strip()
    hist = [h for h in d["history"] if h["date"] >= cutoff.date().isoformat() and (not q or q in h["title"].lower())]
    sess = [s for s in d["sessions"] if s["start"] >= cutoff.isoformat(timespec="minutes")
            and (not q or any(q in t.lower() for t in s["titles"]))]
    if not hist and not sess:
        where = "" if d["history"] else (" I don't have your Netflix viewing history yet: on netflix.com, Account > "
                                          "your profile > Viewing activity > Download all, and leave the file in Downloads.")
        return f"Nothing logged from Netflix in the last {days} days" + (f" matching {query}" if q else "") + "." + where
    out = []
    if hist:
        out.append("From Netflix's viewing history (titles, by day):")
        for h in hist[-25:][::-1]:
            out.append(f"- {h['date']}: {h['title']}")
    if sess:
        out.append("Watched on this PC (from what was playing):")
        for s in sess[-15:][::-1]:
            when = datetime.fromisoformat(s["start"]).strftime("%a %b %d, %I:%M %p")
            what = "; ".join(s["titles"]) or "title unknown"
            out.append(f"- {when}, {s['minutes']} min on the {s['via']}: {what}" + ("" if s["sure"] else " (Netflix was open)"))
    if not d["history"]:
        out.append("(For exact titles, download your Viewing activity from Netflix into Downloads.)")
    return "\n".join(out)


def now_watching():
    hit = detect()
    if not hit:
        return "Nothing's playing on Netflix on this PC right now."
    return f"Netflix is on, in the {hit['via']}" + (f": {hit['title']}." if hit["title"] else ", but it isn't saying what's on.")
