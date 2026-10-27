"""
Everything calendar, in one place, used by full Jarvis (the calendar tool, spoken alerts, the briefing) and by
calendar mode (the light window). Jarvis's own events + your connected calendars + alerts + reminders.

Where new events go (Settings > Calendar > "Add new events to"):
  jarvis        Jarvis's own calendar (this PC)
  caldav        your CalDAV calendar (iCloud, Fastmail, Yahoo, Nextcloud...): added there directly
  google        Google Calendar: opens the event filled in and presses Save, after you OK it
  outlook       Outlook.com, the same way          outlook_work: Outlook for work or school
  windows       Outlook desktop / the Windows Calendar app, through a calendar file
For google / outlook / windows he also keeps a copy here, so the alert still comes even if it never syncs back.
"""
import os
import threading
from datetime import date, datetime, time, timedelta

import cal_store as cs
import cal_sync
import config

TARGETS = {"jarvis": "Jarvis's calendar", "caldav": None, "google": "Google Calendar", "outlook": "Outlook",
           "outlook_work": "Outlook (work)", "windows": "your calendar app"}


def default_target():
    t = (os.environ.get("JARVIS_CAL_DEFAULT") or "jarvis").strip().lower()
    return t if t in TARGETS else "jarvis"


def alert_minutes():
    try:
        return max(0, int(float(os.environ.get("JARVIS_CAL_ALERT") or 10)))
    except ValueError:
        return 10


class CalendarService:
    def __init__(self, reminders, on_alert=None, confirm=None, on_change=None):
        """reminders: a cal_store.ReminderManager. on_alert(text, kind, data). confirm(title, detail, category) -> bool.
        on_change(): something changed (refresh the screen)."""
        self.store = cs.Store(config.JARVIS_DIR / "calendar.json")
        self.sources = cal_sync.Sources(config.CACHE_DIR)
        self.reminders = reminders
        self.on_alert = on_alert or (lambda text, kind, data: None)
        self.confirm = confirm or (lambda title, detail, category=None: False)
        # alerts look at what's VISIBLE: a copy sent to Google that synced back alerts once, not twice
        self.alerts = cs.Alerts(_View(self), config.JARVIS_DIR / "calendar_alerts.json", alert_minutes())
        self.on_change = on_change
        self.store.listeners.append(self._changed)
        self.sources.on_change = self._changed
        self._stop = threading.Event()

    def _changed(self):
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                pass

    # ---------------------------------------------------------------- running
    def start(self):
        self.sources.start()

        def loop():
            while not self._stop.wait(10):
                try:
                    for ev, s, m in self.alerts.check():
                        self.on_alert(cs.alert_line(ev, s, m), "event", {"event": ev, "start": cs.iso(s)})
                except Exception as e:
                    print(f"[calendar] alert error: {e}")
        threading.Thread(target=loop, daemon=True, name="calendar-alerts").start()

    def stop(self):
        self._stop.set()
        self.sources.stop()

    # ---------------------------------------------------------------- reading
    def _local_visible(self):
        ext = self.sources.all_events()
        keys = {(e["title"].strip().lower(), e["start"]) for e in ext}
        out = []
        for ev in self.store.events:
            if ev.get("pushed_to") and (ev["title"].strip().lower(), ev["start"]) in keys:
                continue                                 # it synced back from Google/Outlook: show that one only
            out.append(ev)
        return out, ext

    def between(self, a, b):
        local, ext = self._local_visible()
        out = []
        for ev in local + ext:
            for s in cs.occurrences(ev, a, b):
                out.append((ev, s))
        out.sort(key=lambda x: (not x[0].get("all_day"), x[1], x[0]["title"].lower()))
        return out

    def day(self, d):
        a = datetime.combine(d, time())
        return self.between(a, a + timedelta(days=1))

    def get(self, eid):
        ev = self.store.get(eid)
        if ev:
            return ev
        return next((e for e in self.sources.all_events() if e["id"] == eid), None)

    def label(self, ev):
        if ev.get("calendar_name"):
            return ev["calendar_name"]
        if ev.get("pushed_to"):
            return TARGETS.get(ev["pushed_to"]) or ev["pushed_to"]
        return "Jarvis"

    def line(self, ev, s, today=None):
        cal = self.label(ev)
        return f"{ev['id']}: {cs.describe(ev, s, today)}" + ("" if cal == "Jarvis" else f" [{cal}]")

    # ---------------------------------------------------------------- range words
    @staticmethod
    def span(when="today", now=None):
        """'today', 'tomorrow', 'this week', 'next week', 'weekend', 'month', '2026-11-03', 'next 7 days' -> (a, b, label)."""
        now = now or datetime.now()
        t0 = datetime.combine(now.date(), time())
        w = str(when or "today").strip().lower()
        if w in ("today", ""):
            return t0, t0 + timedelta(days=1), "today"
        if w == "tomorrow":
            return t0 + timedelta(days=1), t0 + timedelta(days=2), "tomorrow"
        if w in ("week", "this week"):
            return t0, t0 + timedelta(days=7 - now.weekday()), "this week"
        if w == "next week":
            a = t0 + timedelta(days=7 - now.weekday())
            return a, a + timedelta(days=7), "next week"
        if w in ("weekend", "this weekend"):
            a = t0 + timedelta(days=(5 - now.weekday()) % 7)
            return a, a + timedelta(days=2), "this weekend"
        if w in ("month", "this month"):
            nm = (t0.replace(day=1) + timedelta(days=32)).replace(day=1)
            return t0, nm, "the rest of this month"
        if w.startswith("next") and "day" in w:
            n = int("".join(ch for ch in w if ch.isdigit()) or 7)
            return t0, t0 + timedelta(days=n), f"the next {n} days"
        try:
            d = cs.to_dt(w)
            return d, d + timedelta(days=1), cs.nice_day(d, now.date())
        except ValueError:
            p = cs.parse(w, now)
            if p:
                d = cs.to_dt(p["start"]).replace(hour=0, minute=0)
                return d, d + timedelta(days=1), cs.nice_day(d, now.date())
        return t0, t0 + timedelta(days=1), "today"

    def agenda(self, when="today"):
        a, b, label = self.span(when)
        items = self.between(a, b)
        if not items:
            return f"Nothing on the calendar {label}."
        today = date.today()
        return f"{label.capitalize()}:\n" + "\n".join(self.line(ev, s, today) for ev, s in items[:60])

    def find(self, query):
        local, ext = self._local_visible()
        now = datetime.now()
        hits = []
        for ev, s in self.between(now - timedelta(days=30), now + timedelta(days=365)):
            q = str(query or "").lower().strip()
            if not q or q in ev["title"].lower() or q in (ev.get("location") or "").lower() or q in (ev.get("notes") or "").lower():
                hits.append((ev, s))
        hits.sort(key=lambda x: (x[1] < now, abs((x[1] - now).total_seconds())))
        seen, out = set(), []
        for ev, s in hits:                               # a repeating event once, at its next time
            if ev["id"] in seen:
                continue
            seen.add(ev["id"])
            out.append((ev, s))
        if not out:
            return f"Nothing on the calendar matching '{query}'."
        return "\n".join(self.line(ev, s) for ev, s in out[:15])

    def free(self, when="today", minutes=60, start_hour=8, end_hour=22):
        a, b, label = self.span(when)
        minutes = max(5, int(minutes or 60))
        out = []
        day = a
        while day < b:
            lo, hi = day.replace(hour=start_hour), day.replace(hour=end_hour)
            if lo < datetime.now() < hi:
                lo = datetime.now().replace(second=0, microsecond=0)
                lo += timedelta(minutes=(15 - lo.minute % 15) % 15)
            busy = sorted((s, s + (cs.to_dt(ev["end"]) - cs.to_dt(ev["start"])))
                          for ev, s in self.between(day, day + timedelta(days=1)) if not ev.get("all_day"))
            cur = lo
            for s, e in busy:
                if s - cur >= timedelta(minutes=minutes):
                    out.append((cur, min(s, hi)))
                cur = max(cur, e)
            if hi - cur >= timedelta(minutes=minutes):
                out.append((cur, hi))
            day += timedelta(days=1)
        out = [(s, e) for s, e in out if e > s]
        if not out:
            return f"No free {minutes}-minute gaps {label} between {start_hour}:00 and {end_hour}:00."
        return f"Free {label} ({minutes}+ min): " + "; ".join(
            f"{cs.nice_day(s)} {cs.nice_time(s)} to {cs.nice_time(e)}" for s, e in out[:12])

    # ---------------------------------------------------------------- changing
    def add(self, title, start, end=None, duration_minutes=None, all_day=False, location="", notes="", repeat=None,
            remind=None, calendar=None):
        target = (calendar or default_target()).strip().lower()
        target = {"local": "jarvis", "here": "jarvis", "icloud": "caldav", "fastmail": "caldav", "yahoo": "caldav",
                  "nextcloud": "caldav", "outlook.com": "outlook", "work": "outlook_work", "desktop": "windows"}.get(target, target)
        if target not in TARGETS:
            return f"I don't know a calendar called '{calendar}'. Options: " + ", ".join(TARGETS) + "."
        s = cs.to_dt(start)
        if end is None and duration_minutes and not all_day:
            end = s + timedelta(minutes=float(duration_minutes))
        if isinstance(remind, (int, float)):
            remind = [int(remind)]
        rep = cs.clean_repeat(repeat)
        clash = "" if all_day else self._clash(s, cs.to_dt(end) if end else s + timedelta(hours=1))
        if target == "caldav":
            if not self.sources.caldav_set():
                return "No CalDAV calendar is set up (Settings > Calendar). I can add it to Jarvis's calendar instead."
            draft = _draft(title, s, end, all_day, location, notes, rep, remind)
            label = self.sources.caldav_label()
            if not self.confirm(f"Add to your {label} calendar", cs.describe(draft), "calendar"):
                return "DENIED"
            try:
                self.sources.caldav_add(draft)
            except Exception as e:
                return f"{label} refused it: {str(e)[:200]}. Nothing was added."
            return f"Added to {label}: {cs.describe(draft)}.{clash}"
        ev = self.store.add(title, s, end, all_day, location, notes, rep, remind,
                            extra={"pushed_to": target} if target != "jarvis" else None)
        if target == "jarvis":
            return f"Added: {cs.describe(ev)} (id {ev['id']}).{clash}"
        return self._push(ev, target) + clash

    def _push(self, ev, target):
        """Google / Outlook on the web, or the desktop calendar app."""
        import tools
        name = TARGETS[target]
        if not self.confirm(f"Add to {name}", cs.describe(ev) + f"\n\nI'll open it in {name} already filled in and "
                                                            "press Save.", "calendar"):
            self.store.delete(ev["id"])
            return "DENIED"
        if target == "windows":
            p = cal_sync.ics_file(ev, config.CACHE_DIR / "calendar")
            try:
                os.startfile(str(p))                      # opens in Outlook / the Calendar app
            except Exception as e:
                return f"Added to Jarvis's calendar, but couldn't open your calendar app ({type(e).__name__})."
            return (f"Added: {cs.describe(ev)}. It's open in your calendar app; if it shows the event, press Save "
                    "and Close there. (Jarvis keeps a copy for the alert.)")
        url = cal_sync.google_url(ev) if target == "google" else cal_sync.outlook_url(ev, work=target == "outlook_work")
        tools.open_url(url, front=True)
        done, how = cal_sync.press_save("google" if target == "google" else "outlook")
        if done:
            return f"Added to {name}: {cs.describe(ev)}."
        return (f"{name} is open with the event filled in, but I {how}. Press Save there. "
                "(Jarvis keeps a copy, so you still get the alert.)")

    def _clash(self, s, e):
        hits = [ev["title"] for ev, os_ in self.between(s - timedelta(hours=12), e)
                if not ev.get("all_day") and os_ < e and os_ + (cs.to_dt(ev["end"]) - cs.to_dt(ev["start"])) > s]
        return f" Heads up: it overlaps {', '.join(hits[:3])}." if hits else ""

    def edit(self, eid, **changes):
        ev = self.get(eid)
        if ev is None:
            return f"No event with id {eid}. Find it first."
        if ev.get("readonly"):
            return (f"That one's from {self.label(ev)}, which I can only read. Change it there (I can open it), or "
                    "connect it with CalDAV in Settings for two-way access.")
        if str(eid).startswith("x:caldav:"):
            new = dict(ev)
            for k, v in changes.items():
                if v is not None:
                    new[k] = cs.iso(cs.to_dt(v), new.get("all_day")) if k in ("start", "end") else v
            if not self.confirm(f"Change it in {self.label(ev)}", cs.describe(new), "calendar"):
                return "DENIED"
            try:
                self.sources.caldav_add(new)              # same UID: replaces it on the server
            except Exception as e:
                return f"{self.label(ev)} refused the change: {str(e)[:200]}"
            return f"Changed: {cs.describe(new)}."
        if changes.get("duration_minutes") and not changes.get("end"):
            s = cs.to_dt(changes.get("start") or ev["start"])
            changes["end"] = s + timedelta(minutes=float(changes.pop("duration_minutes")))
        changes.pop("duration_minutes", None)
        if changes.get("start") and not changes.get("end"):
            dur = cs.to_dt(ev["end"]) - cs.to_dt(ev["start"])
            changes["end"] = cs.to_dt(changes["start"]) + dur     # moving keeps the length
        if isinstance(changes.get("remind"), (int, float)):
            changes["remind"] = [int(changes["remind"])]
        new = self.store.update(eid, **changes)
        return f"Changed: {cs.describe(new)}." + (" (It's only changed here; update it in "
                                                  f"{self.label(ev)} too.)" if ev.get("pushed_to") else "")

    def delete(self, eid, only=None):
        ev = self.get(eid)
        if ev is None:
            return f"No event with id {eid}."
        if ev.get("readonly"):
            return f"That one's from {self.label(ev)}, which I can only read. Delete it there."
        if str(eid).startswith("x:caldav:"):
            if not self.confirm(f"Delete from {self.label(ev)}", cs.describe(ev), "calendar"):
                return "DENIED"
            try:
                self.sources.caldav_delete(ev["uid"])
            except Exception as e:
                return f"{self.label(ev)} refused: {str(e)[:200]}"
            return f"Deleted {ev['title']} from {self.label(ev)}."
        gone = self.store.delete(eid, only=only)
        if only and gone.get("repeat"):
            return f"Skipped {gone['title']} on {cs.nice_day(cs.to_dt(only))}; the rest of the series stays."
        return f"Deleted {gone['title']}." + (f" (It's only removed here; delete it in {self.label(gone)} too.)"
                                              if gone.get("pushed_to") else "")

    def status(self):
        lines = [f"Jarvis's calendar: {len(self.store.events)} events. New events go to: "
                 f"{TARGETS.get(default_target()) or self.sources.caldav_label()}."]
        for src, label in self.sources.names():
            lines.append(f"{label}: {self.sources.status.get(src, 'not synced yet')}" +
                         (" (two-way)" if src == "caldav" else " (read-only link)"))
        if len(lines) == 1:
            lines.append("No other calendars connected. In Settings > Calendar: paste Google's or Outlook's private "
                         "calendar link to see them here, or connect iCloud/Fastmail/Yahoo with CalDAV for two-way.")
        return " ".join(lines)

    # ---------------------------------------------------------------- briefing / quick answers
    def today_line(self):
        items = self.day(date.today())
        now = datetime.now()
        left = [(ev, s) for ev, s in items if ev.get("all_day") or s >= now - timedelta(minutes=10)]
        if not left:
            return ""
        parts = [ev["title"] if ev.get("all_day") else f"{ev['title']} at {cs.nice_time(s)}" for ev, s in left[:5]]
        more = f" and {len(left) - 5} more" if len(left) > 5 else ""
        return "On the calendar today: " + ", ".join(parts) + more + "."


class _View:
    """What the alerts look at: the same events the user sees."""
    def __init__(self, svc):
        self.svc = svc

    def between(self, a, b, extra=()):
        return self.svc.between(a, b)


def _draft(title, s, end, all_day, location, notes, rep, remind):
    import uuid
    e = cs.to_dt(end) if end else (s if all_day else s + timedelta(hours=1))
    return {"id": "draft", "uid": uuid.uuid4().hex + "@jarvis", "title": str(title).strip() or "Event",
            "start": cs.iso(s, all_day), "end": cs.iso(e, all_day), "all_day": bool(all_day),
            "location": location or "", "notes": notes or "", "repeat": rep, "remind": remind}
