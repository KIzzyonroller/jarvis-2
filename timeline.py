"""
Memory timeline: "what was I doing on this day last year?", "what did I do last Tuesday?", "what happened on March 3rd?"

Pieced together from everything he keeps for a day:
  * what you talked about (conversation history)
  * which apps and windows you used (activity memory)
  * games you played and results (play log)
  * your journal entry
  * birthdays that day, and his Sunday letter if there was one
Only what was really recorded: if he wasn't running that day, or a memory was switched off, he says so.
"""
import calendar
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import config

WEEKDAYS = {d.lower(): i for i, d in enumerate(calendar.day_name)}
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})


def parse_day(text, today=None):
    """'this day last year', 'yesterday', 'last tuesday', '3 days ago', 'a month ago', 'march 3rd', '2025-11-21'."""
    today = today or date.today()
    t = (text or "").lower().strip().rstrip("?.")
    t = re.sub(r"\b(on|the|of)\b", " ", t)
    t = " ".join(t.split())
    if not t or t in ("today", "this day"):
        return today
    if "yesterday" in t:
        return today - timedelta(days=1)
    m = re.search(r"(\d+|a|an|one|two|three|four|five|six|seven)\s+(day|week|month|year)s?\s+ago", t)
    if m:
        n = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}.get(m.group(1))
        n = n or int(m.group(1))
        unit = m.group(2)
        if unit == "day":
            return today - timedelta(days=n)
        if unit == "week":
            return today - timedelta(weeks=n)
        if unit == "month":
            return _months_back(today, n)
        return _years_back(today, n)
    if re.search(r"this day last year|a year ago today|one year ago|this time last year", t):
        return _years_back(today, 1)
    if re.search(r"this day last month|a month ago today", t):
        return _months_back(today, 1)
    m = re.search(r"last (monday|tuesday|wednesday|thursday|friday|saturday|sunday)", t)
    if m:
        back = (today.weekday() - WEEKDAYS[m.group(1)]) % 7 or 7
        return today - timedelta(days=back)
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?", t) or \
        re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)(?:,?\s+(\d{4}))?", t)
    if m:
        a, b, y = m.group(1), m.group(2), m.group(3)
        mon, day = (MONTHS.get(a), int(b)) if a in MONTHS else (MONTHS.get(b), int(a)) if b in MONTHS else (None, None)
        if mon:
            yr = int(y) if y else today.year
            d = date(yr, mon, min(day, calendar.monthrange(yr, mon)[1]))
            if not y and d > today:
                d = date(yr - 1, mon, min(day, calendar.monthrange(yr - 1, mon)[1]))
            return d
    return None


def _months_back(d, n):
    y, mo = d.year, d.month - n
    while mo < 1:
        mo += 12
        y -= 1
    return date(y, mo, min(d.day, calendar.monthrange(y, mo)[1]))


def _years_back(d, n):
    try:
        return d.replace(year=d.year - n)
    except ValueError:
        return d.replace(year=d.year - n, day=28)


def gather(core, day):
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    out = {"day": day.isoformat(), "talk": [], "apps": [], "games": [], "journal": "", "notes": []}
    h = getattr(core, "history", None) if core is not None else None
    if h is not None:
        try:
            rows = h.db.execute("SELECT ts, who, text FROM messages WHERE ts >= ? AND ts < ? ORDER BY ts",
                                (start.timestamp(), end.timestamp())).fetchall()
            out["talk"] = [(datetime.fromtimestamp(ts).strftime("%H:%M"), who, text[:200]) for ts, who, text in rows
                           if who.lower() in ("you", "user")][:60]
        except Exception as e:
            out["notes"].append(f"(conversation history unreadable: {e})")
    act = getattr(core, "activity", None) if core is not None else None
    if act is not None:
        try:
            import activity
            ss = [s for s in act.sessions(start, end) if not s.get("idle")]
            tot = {}
            first = {}
            for s in ss:
                tot[s["app"]] = tot.get(s["app"], 0) + (s["e"] - s["s"])
                first.setdefault(s["app"], s["s"])
            out["apps"] = [(a, round(v / 60), datetime.fromtimestamp(first[a]).strftime("%H:%M"))
                           for a, v in sorted(tot.items(), key=lambda x: -x[1])[:8] if v >= 120]
            titles = [activity.short_title(s["title"], s["app"]) for s in ss if s["e"] - s["s"] >= 300]
            out["titles"] = list(dict.fromkeys(t for t in titles if t))[:10]
        except Exception as e:
            out["notes"].append(f"(activity memory unreadable: {e})")
    try:
        import gamemode
        for r in gamemode._read_play():
            if start.timestamp() <= r["t"] < end.timestamp():
                if "minutes" in r:
                    out["games"].append(f"{r['game']} for {round(r['minutes'])} min")
                elif r.get("result"):
                    out["games"].append(f"{r['result']} in {r.get('game') or 'a game'}")
    except Exception:
        pass
    try:
        j = (config.JARVIS_DIR / "Jarvis Journal.txt").read_text(encoding="utf-8", errors="replace")
        m = re.search(rf"^.*{day:%Y-%m-%d}.*$\n((?:.+\n?)+?)(?=^\S.*\d{{4}}-\d{{2}}-\d{{2}}|\Z)", j, re.M)
        if m:
            out["journal"] = m.group(0).strip()[:800]
    except Exception:
        pass
    try:
        import birthdays
        out["birthdays"] = [b["name"] for b in birthdays._load() if b.get("month") == day.month and b.get("day") == day.day]
    except Exception:
        out["birthdays"] = []
    return out


def recall(core, when_text):
    day = parse_day(when_text)
    if not day:
        return "Which day? Like 'last Tuesday', 'this day last year', 'March 3rd' or '3 weeks ago'."
    if day > date.today():
        return "That's in the future; I only remember what's happened."
    g = gather(core, day)
    label = day.strftime("%A, %B ") + str(day.day) + (f", {day.year}" if day.year != date.today().year else "")
    has = g["talk"] or g["apps"] or g["games"] or g["journal"]
    if not has:
        return (f"I've got nothing for {label}. Either I wasn't running that day or those memories didn't exist yet "
                f"(activity memory keeps a limited number of days). Don't make anything up; say that.")
    try:
        import pulls
        rows = [{"time": t, "text": x} for t, _, x in g["talk"][:6]]
        rows += [{"time": f, "text": f"{a}, {m} min"} for a, m, f in g["apps"][:4]]
        rows += [{"time": "", "text": x} for x in g["games"][:3]]
        pulls.pull("briefing", {"game": label, "friends": [], "queue": [f"{r['time']}  {r['text']}".strip() for r in rows][:10]},
                   id="timeline", title="That day", ttl=180, auto=False)
    except Exception:
        pass
    lines = [f"{label}:"]
    if g["apps"]:
        lines.append("PC: " + ", ".join(f"{a} {m} min (from {f})" for a, m, f in g["apps"]))
    if g.get("titles"):
        lines.append("Worked on: " + "; ".join(g["titles"]))
    if g["games"]:
        lines.append("Games: " + ", ".join(g["games"]))
    if g["talk"]:
        lines.append("They said to you: " + " | ".join(f"{t} {x}" for t, _, x in g["talk"][:25]))
    if g["journal"]:
        lines.append("Journal: " + g["journal"])
    if g.get("birthdays"):
        lines.append("Birthdays that day: " + ", ".join(g["birthdays"]))
    lines += g["notes"]
    return "\n".join(lines) + "\n[Tell them about that day in a few warm sentences, like remembering it together. Only what's here.]"
