"""
Your other calendars, next to Jarvis's own.

  * Read-only feeds: the private ".ics" link Google Calendar, Outlook and iCloud give you
      Google: Settings > (your calendar) > Integrate calendar > "Secret address in iCal format"
      Outlook.com: Settings > Calendar > Shared calendars > Publish a calendar > ICS link
      iCloud: Calendar app > share calendar > Public calendar > copy link
    He fetches them every 15 minutes (and keeps the last copy for when you're offline).
  * Two-way (CalDAV): iCloud, Fastmail, Yahoo, Nextcloud and most other non-Google calendars. Server, username and
    an app password (never your normal password). He reads and adds, changes and deletes events there directly.
  * Google Calendar / Outlook on the web: adding opens the event already filled in and presses Save for you
    (after you OK it). Their full official access needs you to register an app with Google or Microsoft (Google
    also reviews it), which this avoids.
  * Outlook desktop / the Windows Calendar app: a calendar file opens in your default calendar app.
"""
import json
import os
import re
import threading
import time
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import cal_store as cs

FEEDS = {"google": ("GOOGLE_CAL_ICS", "Google Calendar"), "outlook": ("OUTLOOK_CAL_ICS", "Outlook"),
         "other": ("OTHER_CAL_ICS", "Other calendar")}
REFRESH_SECS = 15 * 60
WINDOW_BACK, WINDOW_AHEAD = 30, 400                 # days of other calendars kept in memory


def _env(k):
    return (os.environ.get(k) or "").strip()


def _local(dt):
    """icalendar values (date, naive or aware datetime) -> naive local datetime."""
    if isinstance(dt, datetime):
        return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt
    return datetime.combine(dt, datetime.min.time())


def flatten(ics_text, label, src, a, b, writable=False):
    """Every occurrence in [a, b) of every event in an .ics text -> flat Jarvis events."""
    import icalendar
    import recurring_ical_events
    cal = icalendar.Calendar.from_ical(ics_text)
    out = []
    for comp in recurring_ical_events.of(cal, skip_bad_series=True).between(a, b):
        try:
            st = comp.get("DTSTART").dt
            en = comp.get("DTEND").dt if comp.get("DTEND") else None
            all_day = not isinstance(st, datetime)
            s = _local(st)
            if en is None:
                dur = comp.get("DURATION").dt if comp.get("DURATION") else timedelta(days=1 if all_day else 0, hours=0 if all_day else 1)
                e = s + dur
            else:
                e = _local(en)
            if all_day:
                e = e - timedelta(days=1) if e > s else s          # .ics all-day end is exclusive; ours is the last day
            uid = str(comp.get("UID") or f"{label}-{s}")
            alarms = [int(-a.get("TRIGGER").dt.total_seconds() // 60) for a in comp.walk("VALARM")
                      if a.get("TRIGGER") is not None and isinstance(a.get("TRIGGER").dt, timedelta)]
            out.append({"id": f"x:{src}:{uid}:{cs.iso(s)}", "uid": uid, "title": str(comp.get("SUMMARY") or "(no title)"),
                        "start": cs.iso(s, all_day), "end": cs.iso(e, all_day), "all_day": all_day,
                        "location": str(comp.get("LOCATION") or ""), "notes": str(comp.get("DESCRIPTION") or "")[:500],
                        "repeat": None, "remind": [m for m in alarms if m >= 0] or None, "calendar": src,
                        "calendar_name": label, "readonly": not writable})
        except Exception:
            continue
    return out


class Sources:
    """Holds the events of connected calendars, refreshed in the background."""

    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self.lock = threading.Lock()
        self.events = {}                    # src -> [flat events]
        self.status = {}                    # src -> sentence
        self.fetched = {}                   # src -> time
        self._dav = None
        self._stop = threading.Event()
        self.on_change = None
        self._load_cache()

    # ---------------------------------------------------------------- what's set up
    @staticmethod
    def feeds():
        out = []
        for src, (key, label) in FEEDS.items():
            v = _env(key)
            for i, url in enumerate(u for u in re.split(r"[\s,]+", v) if u):
                out.append((src if i == 0 else f"{src}{i + 1}", label, url.replace("webcal://", "https://", 1)))
        return out

    @staticmethod
    def caldav_set():
        return bool(_env("CALDAV_URL") and _env("CALDAV_USER") and _env("CALDAV_PASSWORD"))

    def names(self):
        out = [(src, label) for src, label, _ in self.feeds()]
        if self.caldav_set():
            out.append(("caldav", self.caldav_label()))
        return out

    @staticmethod
    def caldav_label():
        u = _env("CALDAV_URL").lower()
        for k, v in (("icloud", "iCloud"), ("fastmail", "Fastmail"), ("yahoo", "Yahoo"), ("nextcloud", "Nextcloud"),
                     ("zoho", "Zoho"), ("gmx", "GMX")):
            if k in u:
                return v
        return "CalDAV calendar"

    # ---------------------------------------------------------------- cache
    def _cache_path(self):
        return self.cache_dir / "calendars.json"

    def _load_cache(self):
        try:
            d = json.loads(self._cache_path().read_text(encoding="utf-8"))
            self.events = {k: v for k, v in d.get("events", {}).items()}
            self.status = {k: "from the last sync (offline copy)" for k in self.events}
        except (OSError, ValueError):
            pass

    def _save_cache(self):
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._cache_path().write_text(json.dumps({"events": self.events}), encoding="utf-8")
        except OSError:
            pass

    # ---------------------------------------------------------------- fetching
    def refresh(self, force=False):
        now = datetime.now()
        a, b = now - timedelta(days=WINDOW_BACK), now + timedelta(days=WINDOW_AHEAD)
        live = {src for src, _ in self.names()}
        changed = False
        for src, label, url in self.feeds():
            if not force and time.time() - self.fetched.get(src, 0) < REFRESH_SECS:
                continue
            self.fetched[src] = time.time()
            try:
                import requests
                r = requests.get(url, timeout=20, headers={"User-Agent": "Jarvis calendar"})
                if r.status_code in (401, 403, 404):
                    raise RuntimeError(f"the link was refused ({r.status_code}); it may have been reset. Copy it again")
                r.raise_for_status()
                evs = flatten(r.content, label, src, a, b)
                with self.lock:
                    self.events[src] = evs
                    self.status[src] = f"{len(evs)} events, updated {datetime.now():%I:%M %p}".replace(" 0", " ")
                changed = True
            except Exception as e:
                self.status[src] = f"couldn't update: {str(e)[:120]}"
        if self.caldav_set() and (force or time.time() - self.fetched.get("caldav", 0) >= REFRESH_SECS):
            self.fetched["caldav"] = time.time()
            try:
                evs = self._caldav_fetch(a, b)
                with self.lock:
                    self.events["caldav"] = evs
                    self.status["caldav"] = f"{len(evs)} events, updated {datetime.now():%I:%M %p}".replace(" 0", " ")
                changed = True
            except Exception as e:
                self.status["caldav"] = f"couldn't update: {str(e)[:120]}"
        with self.lock:
            for src in [s for s in self.events if s not in live]:          # removed in Settings
                self.events.pop(src, None)
                self.status.pop(src, None)
                changed = True
        if changed:
            self._save_cache()
            if self.on_change:
                try:
                    self.on_change()
                except Exception:
                    pass
        return changed

    def start(self):
        def loop():
            while not self._stop.is_set():
                try:
                    self.refresh()
                except Exception as e:
                    print(f"[calendar] sync error: {e}")
                self._stop.wait(60)
        threading.Thread(target=loop, daemon=True, name="calendar-sync").start()

    def stop(self):
        self._stop.set()

    def all_events(self):
        with self.lock:
            return [e for evs in self.events.values() for e in evs]

    # ---------------------------------------------------------------- CalDAV (two-way)
    def _calendar(self):
        if self._dav is not None:
            return self._dav
        import caldav
        client = caldav.DAVClient(url=_env("CALDAV_URL"), username=_env("CALDAV_USER"), password=_env("CALDAV_PASSWORD"),
                                  timeout=20)
        cals = client.principal().calendars()
        if not cals:
            raise RuntimeError("that account has no calendars")
        want = _env("CALDAV_CALENDAR").lower()
        pick = next((c for c in cals if want and want in str(getattr(c, "name", "") or "").lower()), None)
        if pick is None:
            pick = next((c for c in cals if "remind" not in str(getattr(c, "name", "") or "").lower()), cals[0])
        self._dav = pick
        return pick

    def _caldav_fetch(self, a, b):
        cal = self._calendar()
        label = self.caldav_label()
        out = []
        for obj in cal.search(start=a, end=b, event=True):
            data = obj.data if isinstance(obj.data, (str, bytes)) else str(obj.data)
            out += flatten(data, label, "caldav", a, b, writable=True)
        return out

    def caldav_add(self, ev):
        cal = self._calendar()
        cal.save_event(cs.to_ics(ev))
        self.fetched["caldav"] = 0
        threading.Thread(target=self.refresh, daemon=True).start()

    def caldav_delete(self, uid):
        cal = self._calendar()
        cal.event_by_uid(uid).delete()
        self.fetched["caldav"] = 0
        threading.Thread(target=self.refresh, daemon=True).start()

    def caldav_calendars(self):
        import caldav
        client = caldav.DAVClient(url=_env("CALDAV_URL"), username=_env("CALDAV_USER"), password=_env("CALDAV_PASSWORD"),
                                  timeout=20)
        return [str(getattr(c, "name", "") or "?") for c in client.principal().calendars()]


# ============================================================ Google / Outlook on the web, desktop apps
def google_url(ev):
    s, e = cs.to_dt(ev["start"]), cs.to_dt(ev["end"])
    if ev.get("all_day"):
        dates = f"{s:%Y%m%d}/{(e + timedelta(days=1)):%Y%m%d}"
    else:
        dates = f"{s:%Y%m%dT%H%M%S}/{e:%Y%m%dT%H%M%S}"     # local wall time: Google uses the calendar's time zone
    q = {"action": "TEMPLATE", "text": ev["title"], "dates": dates}
    if ev.get("notes"):
        q["details"] = ev["notes"]
    if ev.get("location"):
        q["location"] = ev["location"]
    if ev.get("repeat"):
        q["recur"] = "RRULE:" + cs.rrule(ev["repeat"])
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(q)


def outlook_url(ev, work=False):
    s, e = cs.to_dt(ev["start"]), cs.to_dt(ev["end"])
    base = "https://outlook.office.com" if work else "https://outlook.live.com"
    q = {"path": "/calendar/action/compose", "rru": "addevent", "subject": ev["title"],
         "startdt": s.strftime("%Y-%m-%dT%H:%M:%S") if not ev.get("all_day") else s.strftime("%Y-%m-%d"),
         "enddt": e.strftime("%Y-%m-%dT%H:%M:%S") if not ev.get("all_day") else (e + timedelta(days=1)).strftime("%Y-%m-%d"),
         "allday": "true" if ev.get("all_day") else "false"}
    if ev.get("notes"):
        q["body"] = ev["notes"]
    if ev.get("location"):
        q["location"] = ev["location"]
    return f"{base}/calendar/0/deeplink/compose?" + urllib.parse.urlencode(q)


def open_url_for_day(app, d):
    d = d if isinstance(d, date) else date.today()
    return {"google": f"https://calendar.google.com/calendar/r/day/{d.year}/{d.month}/{d.day}",
            "outlook": "https://outlook.live.com/calendar/0/view/day",
            "outlook_work": "https://outlook.office.com/calendar/view/day",
            "windows": "outlookcal:"}.get(app)


def press_save(site, timeout=20):
    """After the prefilled Google/Outlook page opens in the browser: find its Save button and press it, the way a
    screen reader would. (done, sentence)."""
    import media_buttons
    if not media_buttons.available():
        return False, "pressing buttons isn't available on this PC"
    import uiautomation as auto  # noqa: F401
    title_re = {"google": r"google calendar|calendar", "outlook": r"outlook|calendar|mail"}[site]
    media_buttons.APPS["web " + site + " calendar"] = {
        "exe": ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe"), "title": title_re}
    end = time.time() + timeout
    while time.time() < end:
        wins = media_buttons._windows("web " + site + " calendar")
        for w in wins:
            for b in media_buttons._buttons(w):
                if re.fullmatch(r"(?i)\s*save\s*", b.Name or ""):
                    if media_buttons._press(b):
                        time.sleep(1.5)
                        return True, "pressed Save"
        time.sleep(0.7)
    return False, "couldn't find its Save button (it may still be loading, or you need to sign in)"


def ics_file(ev, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w\- ]+", "", ev["title"])[:40].strip() or "event"
    p = folder / f"{safe}.ics"
    p.write_text(cs.to_ics(ev), encoding="utf-8")
    return p
