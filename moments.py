"""
Check-ins: little moments like the morning briefing, through the day. Each shows panels (on her window and on the
desktop) and she says a line or two. All in Settings > Conversation & personality > Check-ins.

  * Evening wrap-up (once a day, from the hour you pick): tomorrow's weather, what's on tomorrow (calendar and
    reminders), and where your time went today on the PC (only if Activity memory is on).
  * Rain heads-up: rain likely in the next hour or so, when it isn't raining yet. At most every 6 hours.
  * Break reminders: you've been at the PC without a real break (5+ minutes away) for the time you pick.

Song comments live in proactive.py (they're conversation starters). Like everything she starts on her own, none of
these happen while you're muted, in your quiet hours, in a fullscreen game or video, or in a call.
"""
import random
import threading
import time
from datetime import date, datetime, timedelta

import config

WRAP_AFTER = 20                                    # default hour for the evening wrap-up


def _flag(core, key, value=None):
    try:
        return core._state_flag(key) if value is None else core._state_flag(key, value)
    except Exception:
        return None


def _busy_or_away(core, idle_ok=(3, 600)):
    """True when she shouldn't speak up: muted, quiet hours, talking already, fullscreen, a call, or you're away."""
    import proactive
    if getattr(core, "muted", False) or proactive._in_quiet_hours():
        return True
    if getattr(core, "state", "idle") != "idle" or getattr(core, "_turn", None) is not None:
        return True
    try:
        idle = proactive._idle_seconds()
    except Exception:
        idle = 0
    if not idle_ok[0] <= idle <= idle_ok[1]:
        return True
    try:
        proc, title = proactive._foreground()
        if proc in proactive.CALL_APPS or proactive.CALL_TITLES.search(title or ""):
            return True
        import tools
        if tools.in_game():
            return True
    except Exception:
        pass
    return False


class Moments:
    def __init__(self, core):
        self.core = core
        self._stop = threading.Event()
        self.active_since = time.time()      # since your last real break
        self.last_break_nudge = 0.0
        self.last_rain = 0.0
        self.rain_checked = 0.0

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="check-ins").start()
        return self

    def stop(self):
        self._stop.set()

    def _loop(self):
        self._stop.wait(90)                  # let startup (and the morning briefing) finish first
        while not self._stop.wait(30):
            for check in (self._breaks, self._birthdays, self._evening, self._journal, self._rain, self._butler):
                try:
                    if check():
                        break                # one thing at a time
                except Exception as e:
                    print(f"[check-ins] {check.__name__}: {e}")

    # ------------------------------------------------------------------ breaks
    def _breaks(self):
        import proactive
        try:
            idle = proactive._idle_seconds()
        except Exception:
            return False
        now = time.time()
        if idle >= 300:                       # a real break: start counting again when you're back
            self.active_since = now
            return False
        mins = config.BREAK_EVERY
        if not mins or now - self.active_since < mins * 60 or now - self.last_break_nudge < mins * 60:
            return False
        if _busy_or_away(self.core, (2, 120)):
            return False
        self.last_break_nudge = now
        hours = (now - self.active_since) / 3600
        span = f"{hours:.1f} hours".replace(".0 ", " ") if hours >= 1 else f"{int(hours * 60)} minutes"
        line = random.choice([
            f"You've been going for {span} straight. Stretch, water, eyes off the screen for a minute?",
            f"{span[0].upper() + span[1:]} without a break. Go stand up for a sec, I'll keep everything right here.",
            f"Quick break? It's been {span}. Your back will thank you.",
        ])
        self.core.events.put(("moment", {"line": line, "cards": [
            {"title": "Break time", "big": span, "text": "at the PC without a real break"}]}))
        return True

    # ------------------------------------------------------------------ evening wrap-up
    def _evening(self):
        if not config.EVENING_WRAP:
            return False
        now = datetime.now()
        if now.hour < config.EVENING_AT or now.hour >= 24:
            return False
        today = now.strftime("%Y-%m-%d")
        if _flag(self.core, "wrapped") == today:
            return False
        if _busy_or_away(self.core, (3, 180)):
            return False
        _flag(self.core, "wrapped", today)
        self.core.events.put(("evening", None))
        return True

    # ------------------------------------------------------------------ birthdays: 3 days ahead and on the day
    def _birthdays(self):
        if not config.BIRTHDAYS:
            return False
        now = datetime.now()
        if now.hour < 9 or now.hour >= 22:
            return False
        import birthdays
        for kind, b, d in birthdays.due():
            key = f"bday:{b['name'].lower()}:{d.isoformat()}:{kind}"
            if _flag(self.core, key):
                continue
            if _busy_or_away(self.core, (2, 900)):
                return False
            _flag(self.core, key, "1")
            if kind == "today":
                line = random.choice([f"It's {b['name']}'s birthday today! Send them something.",
                                      f"Hey, today's {b['name']}'s birthday. Don't forget to say happy birthday."])
            else:
                line = (f"{b['name']}'s birthday is in three days, on {d:%A}. Want a few gift ideas?"
                        + (f" You noted: {b['note']}." if b.get("note") else ""))
            self.core.events.put(("moment", {"line": line, "cards": [{"title": "Birthday", "big": b["name"],
                                                                        "text": "today" if kind == "today" else f"{d:%A %B} {d.day}"}]}))
            return True
        return False

    # ------------------------------------------------------------------ journal: one question a night
    def _journal(self):
        if not config.JOURNAL:
            return False
        now = datetime.now()
        if not (now.hour >= config.JOURNAL_AT or now.hour < 3):     # late nights still count as "today"
            return False
        day = (now - timedelta(hours=3)).strftime("%Y-%m-%d")
        if _flag(self.core, "journal_asked") == day:
            return False
        if _busy_or_away(self.core, (3, 240)):
            return False
        try:
            import journal
            if journal.written_today():
                _flag(self.core, "journal_asked", day)
                return False
        except Exception:
            pass
        _flag(self.core, "journal_asked", day)
        self.core.events.put(("journal", None))
        return True

    # ------------------------------------------------------------------ file butler: once a week at most
    def _butler(self):
        if not config.BUTLER_NUDGE:
            return False
        now = time.time()
        if now - getattr(self, "butler_checked", 0) < 6 * 3600:
            return False
        self.butler_checked = now
        try:
            last = float(_flag(self.core, "butler_nudged") or 0)
        except (TypeError, ValueError):
            last = 0
        if now - last < 7 * 86400 or _busy_or_away(self.core, (3, 300)):
            return False
        import butler
        line, card = butler.nudge_line()
        _flag(self.core, "butler_nudged", str(now))          # checked this week either way
        if not line:
            return False
        self.core.events.put(("moment", {"line": line, "cards": [card]}))
        return True

    # ------------------------------------------------------------------ rain heads-up
    def _rain(self):
        if not config.RAIN_ALERT:
            return False
        now = time.time()
        if now - self.rain_checked < 20 * 60 or now - self.last_rain < 6 * 3600:
            return False
        self.rain_checked = now
        soon = rain_soon(self.core)
        if not soon or _busy_or_away(self.core, (2, 600)):
            return False
        self.last_rain = now
        when, prob, label = soon
        line = f"Heads up, {label} is likely around {when}, about {prob} percent. Grab a jacket if you're heading out."
        self.core.events.put(("moment", {"line": line, "cards": [
            {"title": "Rain heads-up", "big": f"{label.capitalize()} around {when}", "text": f"{prob}% chance"}]}))
        return True


# ------------------------------------------------------------------ data
def _loc(core):
    import briefing
    return briefing.location(lambda k: _flag(core, k), lambda k, v: _flag(core, k, v))


def rain_soon(core):
    """(when, probability %, 'rain'/'snow'...) if precipitation looks likely in the next ~90 minutes and it's dry now."""
    import briefing
    loc = _loc(core)
    if not loc:
        return None
    lat, lon = loc[0], loc[1]
    d = briefing._get("https://api.open-meteo.com/v1/forecast", {
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 1,
        "current": "precipitation,weather_code", "hourly": "precipitation_probability,weather_code"}).json()
    cur = d.get("current", {})
    if (cur.get("precipitation") or 0) > 0 or (cur.get("weather_code") or 0) >= 51:
        return None                                    # it's already coming down: nothing to warn about
    h = d.get("hourly", {})
    times, probs, codes = h.get("time") or [], h.get("precipitation_probability") or [], h.get("weather_code") or []
    now = datetime.now()
    for t, p, c in zip(times, probs, codes):
        at = datetime.fromisoformat(t)
        if at < now - timedelta(minutes=30):
            continue
        if at > now + timedelta(minutes=90):
            break
        if (p or 0) >= 60:
            label = briefing.WMO.get(c, "rain") if (c or 0) >= 51 else "rain"
            label = "snow" if "snow" in label else "a storm" if "thunder" in label else "rain"
            return at.strftime("%I %p").lstrip("0"), int(p), label
    return None


def tomorrow_weather(core):
    """{place, unit, high, low, code, label, rain} for tomorrow, or None."""
    import briefing
    loc = _loc(core)
    if not loc:
        return None
    lat, lon, place, cc = loc
    f = (config.COUNTRY or cc or "").upper() == "US"
    d = briefing._get("https://api.open-meteo.com/v1/forecast", {
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 2,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
        "temperature_unit": "fahrenheit" if f else "celsius"}).json().get("daily", {})
    pick = lambda k: (d.get(k) or [None, None])[1]
    if pick("temperature_2m_max") is None:
        return None
    code = pick("weather_code")
    return {"place": f"Tomorrow in {place}", "unit": "°F" if f else "°C", "now": round(pick("temperature_2m_max")),
            "feels": round(pick("temperature_2m_max")), "high": round(pick("temperature_2m_max")),
            "low": round(pick("temperature_2m_min")), "code": code, "label": briefing.WMO.get(code, ""),
            "rain": pick("precipitation_probability_max") or 0}


def tomorrow_items(core):
    """[{time, text}] from the calendar and reminders, for tomorrow."""
    out = []
    day = date.today() + timedelta(days=1)
    cal = getattr(core, "calendar", None)
    if cal is not None:
        try:
            import cal_store as cs
            for ev, s in cal.day(day)[:6]:
                out.append({"time": "All day" if ev.get("all_day") else cs.nice_time(s), "text": ev.get("title", "")})
        except Exception:
            pass
    try:
        import tools
        for r in tools.REMINDERS.items:
            due = datetime.fromisoformat(str(r["due"]))
            if due.date() == day:
                out.append({"time": due.strftime("%I:%M %p").lstrip("0"), "text": r["message"]})
    except Exception:
        pass
    return out[:6]


def today_on_pc(core):
    """[(app, minutes)] where your time went today, if Activity memory is on."""
    tr = getattr(core, "activity", None)
    if tr is None:
        return []
    try:
        from collections import defaultdict
        a = datetime.combine(date.today(), datetime.min.time()).timestamp()
        apps = defaultdict(float)
        for r in tr.sessions(a, time.time()):
            if not r.get("idle"):
                apps[r["app"]] += r["e"] - r["s"]
        return [(app, round(s / 60)) for app, s in sorted(apps.items(), key=lambda kv: -kv[1])[:4] if s >= 300]
    except Exception:
        return []


def evening(core):
    """Gather the wrap-up: (cards, facts text for her to sum up)."""
    cards, facts = [], []
    try:
        w = tomorrow_weather(core)
    except Exception as e:
        w = None
        print(f"[check-ins] weather: {e}")
    if w:
        cards.append({"title": w["place"], "weather": w})
        facts.append(f"Tomorrow: {w['label']}, high {w['high']}{w['unit']}, low {w['low']}" +
                     (f", {w['rain']}% chance of rain" if w["rain"] >= 30 else ""))
    items = tomorrow_items(core)
    cards.append({"title": "Tomorrow", "list": items, "empty": "Nothing on the calendar or reminders tomorrow."})
    facts.append("On for tomorrow: " + ("; ".join(f"{i['text']} ({i['time']})" for i in items) if items else "nothing"))
    apps = today_on_pc(core)
    if apps:
        from activity import dur
        cards.append({"title": "Today on the PC", "list": [{"time": dur(m * 60), "text": a} for a, m in apps]})
        facts.append("Where their time went today: " + ", ".join(f"{a} {m} min" for a, m in apps))
    return cards, ". ".join(facts)


def evening_line(core, facts):
    """Two or three spoken sentences from the facts (fast model), or a plain fallback."""
    import personas
    brain = getattr(core, "brain", None)
    client = getattr(brain, "client", None)
    if client is not None:
        try:
            import usage
            model = config.FAST_MODEL or config.MODEL
            msg = client.messages.create(
                model=model, max_tokens=150,
                system=personas.character(config.ADDRESS_AS) + "\nEverything you write is spoken aloud: plain words, "
                       "no lists, emoji or markdown.",
                messages=[{"role": "user", "content": f"[Evening wrap-up, you're bringing it up on your own. Facts: "
                           f"{facts}. Two or three short sentences, warm and in your own voice: tomorrow's weather, "
                           "what's on tomorrow, and a light word about their day if there's activity info. No "
                           "greeting like 'good evening' every time; vary it.]"}])
            try:
                usage.record_claude(model, msg.usage)
            except Exception:
                pass
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
            if text:
                return text
        except Exception as e:
            print(f"[check-ins] couldn't write the wrap-up: {e}")
    first = facts.split(". ")[0]
    return (first.replace("Tomorrow: ", "Tomorrow looks like ", 1) if first.startswith("Tomorrow: ") else "Here's tomorrow. " + first) + "."


MOMENTS = None


def start(core):
    global MOMENTS
    if MOMENTS is None:
        MOMENTS = Moments(core).start()
    return MOMENTS


def stop():
    if MOMENTS is not None:
        MOMENTS.stop()
