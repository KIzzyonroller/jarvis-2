"""
The calendar: events (one-off and repeating), alerts before they start, and the reminders list.

Light on purpose (standard library only), because calendar mode runs on just this plus a small window.

  * Events live in Documents\\Jarvis\\calendar.json. Times are local wall-clock times ("2026-10-28T15:00");
    all-day events are just dates ("2026-10-28", end = last day).
  * Repeats: daily / weekly (on chosen days) / monthly / yearly, every N, until a date or N times,
    with skipped dates ("not this Tuesday").
  * Alerts: each event can ping N minutes before (default from Settings). Alerts.check() is called every few
    seconds; a fired alert is remembered so it never fires twice, even across restarts.
  * parse(): "dentist tuesday 3pm", "gym every mon wed fri 6-7am", "mom's birthday march 3 every year",
    "call bob in 2 hours", "lunch with sam tomorrow at noon for 90 minutes" -> an event.
  * to_ics() / from_ics(): standard .ics, for calendar apps and CalDAV.
"""
import json
import re
import threading
import uuid
from calendar import monthrange
from datetime import date, datetime, time, timedelta
from pathlib import Path

DAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
DAY_WORDS = {"monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1, "wednesday": 2, "wed": 2, "thursday": 3,
             "thu": 3, "thur": 3, "thurs": 3, "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6}
MONTHS = {"january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4, "may": 5,
          "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
          "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12}
NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
             "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
             "forty five": 45, "forty-five": 45, "half": 0.5}


# ============================================================ helpers
def to_dt(s):
    """'2026-10-28T15:00' -> datetime; '2026-10-28' -> datetime at midnight."""
    if isinstance(s, datetime):
        return s
    if isinstance(s, date):
        return datetime.combine(s, time())
    s = str(s).strip().replace(" ", "T")
    dt = datetime.fromisoformat(s[:19] if "T" in s else s[:10])
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def iso(dt, all_day=False):
    return dt.strftime("%Y-%m-%d") if all_day else dt.strftime("%Y-%m-%dT%H:%M")


def nice_time(dt):
    return dt.strftime("%I:%M %p").lstrip("0").replace(":00 ", " ")


def nice_day(d, today=None):
    today = today or date.today()
    d = d.date() if isinstance(d, datetime) else d
    if d == today:
        return "today"
    if d == today + timedelta(days=1):
        return "tomorrow"
    if today < d < today + timedelta(days=7):
        return d.strftime("%A")
    return f"{d:%a %b} {d.day}" + (f", {d.year}" if d.year != today.year else "")


def describe(ev, start=None, today=None):
    """'Dentist, Tuesday 3 PM to 4 PM' / 'Mom's birthday, Mar 3 (all day, every year)'."""
    s = to_dt(start or ev["start"])
    if ev.get("all_day"):
        when = nice_day(s, today) + " (all day)"
    else:
        e = s + (to_dt(ev["end"]) - to_dt(ev["start"]))
        when = f"{nice_day(s, today)} {nice_time(s)} to {nice_time(e)}"
    rep = repeat_words(ev.get("repeat"))
    extra = []
    if rep:
        extra.append(rep)
    if ev.get("location"):
        extra.append("at " + ev["location"])
    return f"{ev['title']}, {when}" + (f" ({', '.join(extra)})" if extra else "")


def repeat_words(r):
    if not r:
        return ""
    f, n = r.get("freq"), int(r.get("interval") or 1)
    unit = {"daily": "day", "weekly": "week", "monthly": "month", "yearly": "year"}.get(f, f)
    base = f"every {unit}" if n == 1 else f"every {n} {unit}s"
    if f == "weekly" and r.get("days"):
        names = [["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][DAYS.index(d)] for d in r["days"] if d in DAYS]
        base = ("every weekday" if sorted(r["days"], key=DAYS.index) == DAYS[:5] and n == 1
                else ("every " if n == 1 else f"every {n} weeks on ") + ", ".join(names))
    if r.get("until"):
        base += f" until {nice_day(to_dt(r['until']))}"
    elif r.get("count"):
        base += f", {r['count']} times"
    return base


# ============================================================ repeating events
def occurrences(ev, a, b, limit=400):
    """Starts of ev's occurrences that overlap [a, b). Handles repeats, skipped dates and multi-day events."""
    s0 = to_dt(ev["start"])
    dur = to_dt(ev["end"]) - s0
    if ev.get("all_day"):
        dur += timedelta(days=1)                       # all-day end is the last day; make it exclusive
    skip = set(ev.get("exceptions") or [])
    r = ev.get("repeat")
    out = []

    def keep(s):
        if s < b and s + dur > a and iso(s, ev.get("all_day")) not in skip and iso(s) not in skip:
            out.append(s)

    if not r:
        keep(s0)
        return out
    f, n = r.get("freq"), max(1, int(r.get("interval") or 1))
    until = to_dt(r["until"]) + timedelta(days=1) if r.get("until") else None
    count = int(r["count"]) if r.get("count") else None
    end = min(b, until) if until else b
    made = 0
    if f == "weekly":
        days = sorted({DAYS.index(d) for d in (r.get("days") or []) if d in DAYS}) or [s0.weekday()]
        week0 = s0 - timedelta(days=s0.weekday())
        w = 0
        while True:
            base = week0 + timedelta(weeks=w * n)
            if base > end or made >= (count or 10**9) or len(out) >= limit:
                break
            for d in days:
                s = base + timedelta(days=d)
                if s < s0:
                    continue
                if (until and s >= until) or made >= (count or 10**9):
                    break
                made += 1
                keep(s)
            w += 1
        return out
    i = 0
    while made < (count or 10**9) and len(out) < limit:
        if f == "daily":
            s = s0 + timedelta(days=i * n)
        elif f == "monthly":
            m = s0.month - 1 + i * n
            y, mo = s0.year + m // 12, m % 12 + 1
            if s0.day > monthrange(y, mo)[1]:
                i += 1
                if datetime(y, mo, 1) > end:
                    break
                continue                               # no 31st this month: skip it, like phones do
            s = s0.replace(year=y, month=mo)
        elif f == "yearly":
            y = s0.year + i * n
            if s0.month == 2 and s0.day == 29 and monthrange(y, 2)[1] < 29:
                i += 1
                continue
            s = s0.replace(year=y)
        else:
            keep(s0)
            break
        if s >= end:
            break
        made += 1
        keep(s)
        i += 1
    return out


# ============================================================ the store
class Store:
    """Local events. Thread-safe; saved on every change."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.events = self._load()
        self.listeners = []                            # called after any change (refresh the screen)

    def _load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            return d.get("events", []) if isinstance(d, dict) else []
        except (OSError, ValueError):
            return []

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"events": self.events}, indent=1), encoding="utf-8")
        tmp.replace(self.path)
        for fn in list(self.listeners):
            try:
                fn()
            except Exception:
                pass

    def add(self, title, start, end=None, all_day=False, location="", notes="", repeat=None, remind=None,
            calendar="local", uid=None, extra=None):
        s = to_dt(start)
        if all_day:
            s = datetime.combine(s.date(), time())
            e = to_dt(end) if end else s
            e = datetime.combine(e.date(), time())
        else:
            e = to_dt(end) if end else s + timedelta(hours=1)
            if e <= s:
                e = s + timedelta(hours=1)
        ev = {"id": "e" + uuid.uuid4().hex[:7], "title": str(title).strip()[:200] or "Event",
              "start": iso(s, all_day), "end": iso(e, all_day), "all_day": bool(all_day),
              "location": str(location or "")[:200], "notes": str(notes or "")[:2000],
              "repeat": clean_repeat(repeat), "remind": remind if remind is not None else None,
              "calendar": calendar or "local", "uid": uid or (uuid.uuid4().hex + "@jarvis"),
              "created": datetime.now().isoformat(timespec="seconds")}
        if extra:
            ev.update(extra)
        with self.lock:
            self.events.append(ev)
            self._save()
        return ev

    def get(self, eid):
        return next((e for e in self.events if e["id"] == eid), None)

    def update(self, eid, **changes):
        with self.lock:
            ev = self.get(eid)
            if ev is None:
                return None
            for k, v in changes.items():
                if v is None:
                    continue
                if k in ("start", "end"):
                    v = iso(to_dt(v), changes.get("all_day", ev.get("all_day")))
                if k == "repeat":
                    v = clean_repeat(v)
                ev[k] = v
            if "all_day" in changes and changes["all_day"] is not None:
                ev["start"] = iso(to_dt(ev["start"]), ev["all_day"])
                ev["end"] = iso(to_dt(ev["end"]), ev["all_day"])
            if not ev.get("all_day") and to_dt(ev["end"]) <= to_dt(ev["start"]):
                ev["end"] = iso(to_dt(ev["start"]) + timedelta(hours=1))
            ev["updated"] = datetime.now().isoformat(timespec="seconds")
            self._save()
            return dict(ev)

    def delete(self, eid, only=None):
        """only = one occurrence's start (skip just that date of a repeating event)."""
        with self.lock:
            ev = self.get(eid)
            if ev is None:
                return None
            if only and ev.get("repeat"):
                ev.setdefault("exceptions", []).append(iso(to_dt(only), ev.get("all_day")))
            else:
                self.events = [e for e in self.events if e["id"] != eid]
            self._save()
            return ev

    def between(self, a, b, extra=()):
        """[(event, occurrence_start)] in [a, b), sorted. extra = events from other calendars."""
        out = []
        for ev in list(self.events) + list(extra):
            for s in occurrences(ev, a, b):
                out.append((ev, s))
        out.sort(key=lambda x: (not x[0].get("all_day"), x[1], x[0]["title"].lower()))
        return out

    def find(self, query, extra=(), days_back=30, days_ahead=365):
        q = str(query or "").lower().strip()
        now = datetime.now()
        hits = []
        for ev, s in self.between(now - timedelta(days=days_back), now + timedelta(days=days_ahead), extra):
            if not q or q in ev["title"].lower() or q in (ev.get("location") or "").lower() or q in (ev.get("notes") or "").lower():
                hits.append((ev, s))
        hits.sort(key=lambda x: (x[1] < now, abs((x[1] - now).total_seconds())))
        return hits


def clean_repeat(r):
    if not r:
        return None
    if isinstance(r, str):
        return parse_repeat(r)
    f = str(r.get("freq", "")).lower()
    if f not in ("daily", "weekly", "monthly", "yearly"):
        return None
    out = {"freq": f, "interval": max(1, int(r.get("interval") or 1))}
    days = [d.upper()[:2] for d in (r.get("days") or []) if d and d.upper()[:2] in DAYS]
    if days and f == "weekly":
        out["days"] = sorted(set(days), key=DAYS.index)
    if r.get("until"):
        out["until"] = iso(to_dt(r["until"]), True)
    elif r.get("count"):
        out["count"] = max(1, int(r["count"]))
    return out


# ============================================================ alerts
class Alerts:
    """Fires 'starting soon' alerts for event occurrences. state_path remembers what already fired."""
    STALE_MIN = 15                                     # an alert more than this late (PC was off) is skipped

    def __init__(self, store, state_path, default_minutes=10, extra=None):
        self.store = store
        self.state_path = Path(state_path)
        self.default = default_minutes
        self.extra = extra or (lambda: [])             # events from connected calendars
        self.fired = self._load()

    def _load(self):
        try:
            return set(json.loads(self.state_path.read_text(encoding="utf-8")).get("fired", []))
        except (OSError, ValueError):
            return set()

    def _save(self):
        cutoff = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        self.fired = {k for k in self.fired if k.split("|")[1][:10] >= cutoff}
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps({"fired": sorted(self.fired)}), encoding="utf-8")
        except OSError:
            pass

    def minutes_for(self, ev):
        r = ev.get("remind")
        if r is None:
            return [] if ev.get("all_day") else [self.default]
        return [int(m) for m in (r if isinstance(r, list) else [r]) if m is not None and int(m) >= 0]

    def check(self, now=None):
        """[(event, occurrence_start, minutes_before)] that are due now (each only once)."""
        now = now or datetime.now()
        try:
            extra = list(self.extra())
        except Exception:
            extra = []
        due = []
        for ev, s in self.store.between(now - timedelta(minutes=self.STALE_MIN), now + timedelta(days=2), extra):
            for m in self.minutes_for(ev):
                at = s - timedelta(minutes=m)
                if ev.get("all_day"):
                    at = s + timedelta(hours=8) - timedelta(minutes=m)     # all-day: morning of
                key = f"{ev.get('uid') or ev['id']}|{iso(s)}|{m}"
                if at <= now and key not in self.fired:
                    self.fired.add(key)
                    if (now - at).total_seconds() / 60 <= self.STALE_MIN:
                        due.append((ev, s, m))
        if due:
            self._save()
        return due


def alert_line(ev, s, m, now=None):
    now = now or datetime.now()
    if ev.get("all_day"):
        return f"Today: {ev['title']}."
    mins = round((s - now).total_seconds() / 60)
    when = "now" if mins <= 0 else (f"in {mins} minute{'s' if mins != 1 else ''}" if mins < 60
                                    else f"at {nice_time(s)}")
    return f"{ev['title']} {'is starting ' + when if mins <= 0 else 'starts ' + when}" + \
        (f", at {ev['location']}" if ev.get("location") else "") + "."


# ============================================================ reminders (the one-off "remind me" list)
class ReminderManager:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.items = self._load()
        self._stop = threading.Event()
        self.on_due = None

    def _load(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.items, indent=2), encoding="utf-8")

    def reload(self):
        with self.lock:
            self.items = self._load()

    def start(self, on_due):
        self.on_due = on_due
        threading.Thread(target=self._loop, daemon=True, name="reminders").start()

    def stop(self):
        self._stop.set()

    def check(self, now=None):
        now = now or datetime.now()
        with self.lock:
            due = [r for r in self.items if datetime.fromisoformat(r["due"]) <= now]
            if due:
                self.items = [r for r in self.items if r not in due]
                self._save()
        for r in due:
            late = (now - datetime.fromisoformat(r["due"])).total_seconds() / 60
            if self.on_due:
                self.on_due(r["message"], late)
        return due

    def _loop(self):
        while not self._stop.wait(1):
            try:
                self.check()
            except Exception as e:
                print(f"[reminders] error: {e}")

    def add(self, message, due):
        r = {"id": uuid.uuid4().hex[:6], "message": message, "due": due.isoformat(timespec="seconds")}
        with self.lock:
            self.items.append(r)
            self.items.sort(key=lambda x: x["due"])
            self._save()
        return r

    def cancel(self, query):
        q = query.lower()
        with self.lock:
            gone = [r for r in self.items if r["id"] == q or q in r["message"].lower()]
            self.items = [r for r in self.items if r not in gone]
            self._save()
        return gone


# ============================================================ understanding "dentist tuesday 3pm"
_TIME = r"(?:(?P<h>\d{1,2})(?::(?P<m>\d{2}))?\s*(?P<ap>a\.?m\.?|p\.?m\.?)?|(?P<word>noon|midday|midnight))"


def _hm(h, m, ap, word=None, hint_pm=True):
    if word:
        return (12, 0) if word in ("noon", "midday") else (0, 0)
    h, m = int(h), int(m or 0)
    if h > 23 or m > 59:
        return None
    ap = (ap or "").replace(".", "").lower()
    if ap == "pm" and h < 12:
        h += 12
    elif ap == "am" and h == 12:
        h = 0
    elif not ap and hint_pm and 1 <= h <= 7:
        h += 12                                        # "at 3" means 3 PM, not 3 in the morning
    return h, m


def parse_repeat(text):
    t = " " + str(text or "").lower() + " "
    r = None
    days = [DAYS[v] for k, v in DAY_WORDS.items() if re.search(rf"\b{k}s?\b", t)]
    if re.search(r"\bevery\s+weekday|\bweekdays\b|\bmonday (?:to|through|-) friday\b", t):
        r = {"freq": "weekly", "days": DAYS[:5]}
    elif re.search(r"\bevery\s+weekend|\bweekends\b", t):
        r = {"freq": "weekly", "days": DAYS[5:]}
    elif re.search(r"\b(every\s+day|daily|each day|every morning|every night|every evening)\b", t):
        r = {"freq": "daily"}
    elif m := re.search(r"\bevery\s+(\d+|other|two|three|four)\s+(day|week|month|year)s?\b", t):
        n = {"other": 2, "two": 2, "three": 3, "four": 4}.get(m.group(1)) or int(m.group(1))
        r = {"freq": {"day": "daily", "week": "weekly", "month": "monthly", "year": "yearly"}[m.group(2)], "interval": n}
        if r["freq"] == "weekly" and days:
            r["days"] = days
    elif re.search(r"\b(every\s+week|weekly|each week)\b", t) or (re.search(r"\bevery\b", t) and days) or \
            re.search(r"\b(mondays|tuesdays|wednesdays|thursdays|fridays|saturdays|sundays)\b", t) or len(days) >= 2:
        r = {"freq": "weekly"}
        if days:
            r["days"] = days
        if re.search(r"\bevery\s+(?:other|second|2nd)\s+(?:mon|tue|wed|thu|fri|sat|sun)", t):
            r["interval"] = 2
    elif re.search(r"\b(every\s+month|monthly|each month|of every month|of each month)\b", t):
        r = {"freq": "monthly"}
    elif re.search(r"\b(every\s+year|yearly|annually|each year)\b", t):
        r = {"freq": "yearly"}
    if r is None:
        return None
    if m := re.search(r"\bfor\s+(\d+|two|three|four|five|six|eight|ten|twelve)\s+(week|month|day|year|time)s?\b", t):
        n = NUM_WORDS.get(m.group(1)) or int(m.group(1))
        if m.group(2) == "time" or m.group(2)[0] == r["freq"][0]:
            r["count"] = int(n) * (len(r.get("days") or [1]) if m.group(2) == "week" else 1)
    return clean_repeat(r)


def parse(text, now=None, default_minutes=60):
    """Natural language -> {"title", "start", "end", "all_day", "repeat", "remind", "found"} or None if no date/time.
    found says what was understood, for showing the user before adding."""
    now = now or datetime.now()
    raw = " " + re.sub(r"\s+", " ", str(text or "")).strip() + " "
    t = raw.lower()
    used = []                                          # spans of t that were understood (removed from the title)

    def take(m):
        nonlocal t
        a, b = m.span()
        used.append((a, b))
        t = t[:a] + " " * (b - a) + t[b:]              # blank it so nothing else reads the same words again
        return m

    day = None
    start_t = end_t = None
    duration = None
    all_day = False
    remind = None

    # ---- reminders ("remind me 30 minutes before", "no reminder")
    if m := re.search(r"\b(?:with\s+)?no\s+(?:reminder|alert)s?\b", t):
        take(m)
        remind = []
    elif m := re.search(r"\b(?:remind me|with an? (?:reminder|alert)|alert me)\s*(\d+|an?|one|two|half an?)?\s*"
                        r"(minute|min|hour|hr|day)?s?\s*(?:before|early|earlier|ahead)?\b", t):
        take(m)
        n = m.group(1) or ""
        n = 0.5 if n.startswith("half") else (NUM_WORDS.get(n.strip()) or (int(n) if n.isdigit() else None))
        unit = (m.group(2) or "minute")[0]
        if n is not None:
            remind = [int(n * (60 if unit == "h" else 1440 if unit == "d" else 1))]

    # ---- repeats
    rep = parse_repeat(t)
    for pat in (r"\bof (?:every|each) month\b",
                r"\bevery\s+(?:other|\d+|two|three|four)?\s*(?:day|week|month|year|weekday|weekend|morning|night|evening)s?\b",
                r"\b(?:daily|weekly|monthly|yearly|annually|weekdays|weekends)\b",
                r"\b(?:each|every)\s+(?:day|week|month|year)\b",
                r"\bevery\s+(?:other\s+|second\s+|2nd\s+)?(?=(?:mon|tue|wed|thu|fri|sat|sun))",
                r"\bfor\s+(?:\d+|two|three|four|five|six|eight|ten|twelve)\s+(?:week|month|day|year|time)s?\b"):
        for m in re.finditer(pat, t):
            if rep:
                take(m)
    if rep and (m := re.search(r"\b(?:until|till|through)\s+([a-z]+\.?\s+\d{1,2}(?:st|nd|rd|th)?|\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b", t)):
        u = _date_from(m.group(1), now)
        if u:
            rep["until"] = iso(u, True)
            take(m)

    # ---- durations ("for 2 hours", "for an hour and a half", "for 90 minutes")
    if m := re.search(r"\bfor\s+(?:(\d+(?:\.\d+)?)|(an?|one|two|three|four|half an?))\s*(hour|hr|minute|min)s?"
                      r"(?:\s+and\s+a\s+half)?\b", t):
        take(m)
        n = float(m.group(1)) if m.group(1) else (0.5 if m.group(2).startswith("half") else NUM_WORDS.get(m.group(2), 1))
        if "and a half" in m.group(0):
            n += 0.5
        duration = timedelta(minutes=n * (60 if m.group(3).startswith("h") else 1))
    elif m := re.search(r"\bfor\s+(?:a\s+)?half\s+(?:an\s+)?hour\b", t):
        take(m)
        duration = timedelta(minutes=30)

    # ---- "in 2 hours" / "in 30 minutes" (a point in time, not a duration)
    if m := re.search(r"\bin\s+(\d+|an?|one|two|three|four|five|ten|fifteen|twenty|thirty|forty five|half an?)\s*"
                      r"(minute|min|hour|hr|day|week)s?\b", t):
        take(m)
        n = m.group(1)
        n = 0.5 if n.startswith("half") else (NUM_WORDS.get(n) or int(n))
        unit = m.group(2)[0]
        delta = timedelta(minutes=n) if unit == "m" else timedelta(hours=n) if unit == "h" else \
            timedelta(days=n) if unit == "d" else timedelta(weeks=n)
        target = now + delta
        if unit in ("m", "h"):
            day, start_t = target.date(), (target.hour, target.minute)
        else:
            day = target.date()

    # ---- time ranges ("3-4pm", "from 3 to 5pm", "10am to 11:30am") and single times
    tr = re.compile(rf"\b(?:from\s+)?(?:at\s+)?{_TIME}\s*(?:-|to|till|until|–)\s*{_TIME.replace('?P<h>', '?P<h2>').replace('?P<m>', '?P<m2>').replace('?P<ap>', '?P<ap2>').replace('?P<word>', '?P<word2>')}\b")
    for m in tr.finditer(t):
        g = m.groupdict()
        if not (g["h"] or g["word"]) or not (g["h2"] or g["word2"]):
            continue
        if not (g["ap"] or g["ap2"] or g["word"] or g["word2"] or ":" in m.group(0) or "at" in m.group(0)[:4]
                or "from" in m.group(0)):
            continue                                   # "3-4" alone could be anything
        ap1 = g["ap"] or (g["ap2"] if g["h"] and int(g["h"]) <= int(g["h2"] or 0) else None)
        a1 = _hm(g["h"], g["m"], ap1, g["word"])
        a2 = _hm(g["h2"], g["m2"], g["ap2"], g["word2"])
        if a1 and a2:
            start_t, end_t = a1, a2
            take(m)
            break
    if start_t is None:
        for m in re.finditer(rf"\b(?:at\s+|@\s*)?{_TIME}(?=\W)", t):
            g = m.groupdict()
            txt = m.group(0)
            if not g["word"] and not g["ap"] and not txt.strip().startswith(("at", "@")) and ":" not in txt:
                continue                               # a bare number isn't a time ("2 tickets")
            if any(a <= m.start() < b for a, b in used):
                continue
            hm = _hm(g["h"], g["m"], g["ap"], g["word"])
            if hm:
                start_t = hm
                take(m)
                break
    if start_t is None:
        for word, hm in (("this morning", (9, 0)), ("in the morning", (9, 0)), ("morning", (9, 0)),
                         ("this afternoon", (14, 0)), ("in the afternoon", (14, 0)), ("afternoon", (14, 0)),
                         ("this evening", (18, 0)), ("in the evening", (18, 0)), ("evening", (18, 0)),
                         ("tonight", (19, 0)), ("lunch time", (12, 0)), ("lunchtime", (12, 0))):
            if m := re.search(rf"\b{word}\b", t):
                if not (rep and rep.get("freq") == "daily" and word in ("morning", "evening")):
                    start_t = hm
                if word == "tonight":
                    day = day or now.date()
                take(m)
                break

    # ---- the day
    if day is None and rep and rep.get("days"):
        for k in sorted(DAY_WORDS, key=len, reverse=True):          # the days belong to the repeat, not the title
            for m in list(re.finditer(rf"\b{k}s?\b", t)):
                take(m)
        for m in list(re.finditer(r"\b(?:weekdays?|weekends?|and|&)\b", t)):
            take(m)
        wd = [DAYS.index(d) for d in rep["days"]]
        for i in range(8):                               # the first one that hasn't already gone by
            d = now.date() + timedelta(days=i)
            if d.weekday() in wd and (start_t is None or datetime.combine(d, time(*start_t)) > now):
                day = d
                break
    if day is None:
        day = _find_day(t, now, take)
    if day is None and rep and start_t:
        day = now.date()

    if day is None and start_t is None:
        return None
    if day is None:                                   # just a time: today, or tomorrow if it's already passed
        day = now.date() if datetime.combine(now.date(), time(*start_t)) > now else now.date() + timedelta(days=1)
    if start_t is None:
        all_day = True
    start = datetime.combine(day, time(*start_t)) if start_t else datetime.combine(day, time())
    if all_day:
        end = start
    elif end_t:
        end = datetime.combine(day, time(*end_t))
        if end <= start:
            end += timedelta(days=1)
    else:
        end = start + (duration or timedelta(minutes=default_minutes))

    # ---- what's left is the title
    keep = list(raw)
    for a, b in used:
        for i in range(a, min(b, len(keep))):
            keep[i] = " "
    title = "".join(keep)
    title = re.sub(r"(?i)^\s*(?:jarvis|ultron)[,\s]+", " ", title)
    title = re.sub(r"(?i)\b(?:please|can you|could you|add|schedule|put|create|set up|book|make|new)\b", " ", title)
    title = re.sub(r"(?i)\b(?:an? )?(?:event|appointment)\b(?:\s+(?:called|for|named))?", " ", title)
    title = re.sub(r"(?i)\b(?:to|on|in|into)\s+(?:my|the)\s+calendar\b", " ", title)
    title = re.sub(r"(?i)\b(?:called|named)\b", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" ,.-:;")
    title = re.sub(r"(?i)^(?:a|an|the|my|for|on|at|is|i have|i've got|there's)\s+", "", title)
    for _ in range(3):
        title = re.sub(r"(?i)\s+(?:on|at|for|from|this|next|the|every|and|of|,)$", "", title).strip(" ,.-:;")
    if not title:
        title = "Event"
    title = title[0].upper() + title[1:]
    if rep is None and re.search(r"(?i)\bbirthday\b|\banniversary\b", title) and all_day:
        rep = {"freq": "yearly", "interval": 1}         # birthdays come back every year
    found = []
    if day:
        found.append(nice_day(day, now.date()))
    if start_t:
        found.append(nice_time(start) + (f" to {nice_time(end)}" if not all_day else ""))
    if rep:
        found.append(repeat_words(rep))
    return {"title": title, "start": iso(start, all_day), "end": iso(end, all_day), "all_day": all_day,
            "repeat": rep, "remind": remind, "found": ", ".join(f for f in found if f)}


def _date_from(s, now):
    s = s.strip().lower().rstrip(".")
    if m := re.match(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$", s):
        a, b = int(m.group(1)), int(m.group(2))
        mo, d = (a, b) if a <= 12 else (b, a)
        y = int(m.group(3)) if m.group(3) else now.year
        y = y + 2000 if y < 100 else y
        try:
            out = date(y, mo, d)
        except ValueError:
            return None
        return out if m.group(3) or out >= now.date() else date(y + 1, mo, d)
    if m := re.match(r"([a-z]+)\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?$", s):
        mo = MONTHS.get(m.group(1))
        if not mo:
            return None
        y = int(m.group(3)) if m.group(3) else now.year
        try:
            out = date(y, mo, int(m.group(2)))
        except ValueError:
            return None
        return out if m.group(3) or out >= now.date() else date(y + 1, mo, int(m.group(2)))
    return None


def _find_day(t, now, take):
    today = now.date()
    for word, delta in (("day after tomorrow", 2), ("tomorrow", 1), ("tmrw", 1), ("tmr", 1), ("today", 0), ("tonight", 0)):
        if m := re.search(rf"\b{word}\b", t):
            take(m)
            return today + timedelta(days=delta)
    if m := re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t):
        take(m)
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    mon = "|".join(sorted(MONTHS, key=len, reverse=True))
    if m := re.search(rf"\b(?:on\s+)?(?:the\s+)?(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({mon})\.?(?:,?\s+(\d{{4}}))?\b", t):
        d = _date_from(f"{m.group(2)} {m.group(1)}" + (f" {m.group(3)}" if m.group(3) else ""), now)
        if d:
            take(m)
            return d
    if m := re.search(rf"\b(?:on\s+)?({mon})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b", t):
        d = _date_from(f"{m.group(1)} {m.group(2)}" + (f" {m.group(3)}" if m.group(3) else ""), now)
        if d:
            take(m)
            return d
    if m := re.search(r"\b(?:on\s+)?(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b", t):
        d = _date_from(m.group(1), now)
        if d:
            take(m)
            return d
    if m := re.search(r"\b(next|this|coming)?\s*(monday|mon|tuesday|tues|tue|wednesday|wed|thursday|thurs|thur|thu|friday|fri|"
                      r"saturday|sat|sunday|sun)\b", t):
        wd = DAY_WORDS[m.group(2)]
        take(m)
        if m.group(1) == "next":                       # "next Friday" = Friday of next week
            return today + timedelta(days=7 - today.weekday() + wd)
        return today + timedelta(days=(wd - today.weekday()) % 7)      # "Friday" = the coming one (today counts)
    if m := re.search(r"\bnext\s+week\b", t):
        take(m)
        return today + timedelta(days=7 - today.weekday())
    if m := re.search(r"\bnext\s+month\b", t):
        take(m)
        y, mo = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        return date(y, mo, 1)
    if m := re.search(r"\b(?:on\s+)?the\s+(\d{1,2})(?:st|nd|rd|th)\b", t):
        d = int(m.group(1))
        y, mo = today.year, today.month
        for _ in range(13):
            if d <= monthrange(y, mo)[1] and date(y, mo, d) >= today:
                take(m)
                return date(y, mo, d)
            y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
    return None


# ============================================================ .ics (calendar files, CalDAV)
def _ics_escape(s):
    return str(s or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line):
    out, b = [], line.encode("utf-8")
    while len(b) > 73:
        cut = 73
        while cut > 0 and (b[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(b[:cut].decode("utf-8"))
        b = b[cut:]
    out.append(b.decode("utf-8"))
    return "\r\n ".join(out)


def to_ics(events):
    """One or more events -> .ics text (local times with the PC's offset turned into UTC)."""
    if isinstance(events, dict):
        events = [events]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Jarvis//Calendar//EN", "CALSCALE:GREGORIAN"]
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    for ev in events:
        s, e = to_dt(ev["start"]), to_dt(ev["end"])
        lines += ["BEGIN:VEVENT", f"UID:{ev.get('uid') or ev['id'] + '@jarvis'}", f"DTSTAMP:{stamp}"]
        if ev.get("all_day"):
            lines += [f"DTSTART;VALUE=DATE:{s:%Y%m%d}", f"DTEND;VALUE=DATE:{(e + timedelta(days=1)):%Y%m%d}"]
        else:
            utc = lambda d: d.astimezone().astimezone(__import__("datetime").timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            lines += [f"DTSTART:{utc(s)}", f"DTEND:{utc(e)}"]
        lines.append(f"SUMMARY:{_ics_escape(ev['title'])}")
        if ev.get("location"):
            lines.append(f"LOCATION:{_ics_escape(ev['location'])}")
        if ev.get("notes"):
            lines.append(f"DESCRIPTION:{_ics_escape(ev['notes'])}")
        if ev.get("repeat"):
            lines.append("RRULE:" + rrule(ev["repeat"]))
        for x in ev.get("exceptions") or []:
            xd = to_dt(x)
            lines.append(f"EXDATE;VALUE=DATE:{xd:%Y%m%d}" if ev.get("all_day") else
                         f"EXDATE:{xd.astimezone().astimezone(__import__('datetime').timezone.utc):%Y%m%dT%H%M%SZ}")
        for m in Alerts(None, "", 10).minutes_for(ev) if ev.get("remind") is not None else []:
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_ics_escape(ev['title'])}",
                      f"TRIGGER:-PT{int(m)}M", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"


def rrule(r):
    parts = [f"FREQ={r['freq'].upper()}"]
    if int(r.get("interval") or 1) > 1:
        parts.append(f"INTERVAL={int(r['interval'])}")
    if r.get("days"):
        parts.append("BYDAY=" + ",".join(r["days"]))
    if r.get("until"):
        parts.append(f"UNTIL={to_dt(r['until']):%Y%m%d}T235959Z")
    elif r.get("count"):
        parts.append(f"COUNT={int(r['count'])}")
    return ";".join(parts)


def from_rrule(s):
    d = dict(p.split("=", 1) for p in str(s).split(";") if "=" in p)
    r = {"freq": d.get("FREQ", "").lower(), "interval": int(d.get("INTERVAL", 1))}
    if d.get("BYDAY"):
        r["days"] = [re.sub(r"^[+-]?\d+", "", x)[:2] for x in d["BYDAY"].split(",")]
    if d.get("UNTIL"):
        u = d["UNTIL"]
        r["until"] = f"{u[:4]}-{u[4:6]}-{u[6:8]}"
    elif d.get("COUNT"):
        r["count"] = int(d["COUNT"])
    return clean_repeat(r)
