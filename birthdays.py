"""
Birthday radar: birthdays you mention ("Kai's birthday is March 3rd") are kept in birthdays.json in her data folder,
and she reminds you 3 days ahead (time to get something) and on the day. "Whose birthday is coming up?" lists the
next few. Edit or remove by voice ("forget Kai's birthday").
"""
import json
from datetime import date

import config

FILE = "birthdays.json"
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]


def _load():
    try:
        return json.loads((config.JARVIS_DIR / FILE).read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items):
    config.JARVIS_DIR.mkdir(parents=True, exist_ok=True)
    (config.JARVIS_DIR / FILE).write_text(json.dumps(items, indent=1), encoding="utf-8")


def _next(b, today=None):
    today = today or date.today()
    for y in (today.year, today.year + 1):
        try:
            d = date(y, b["month"], b["day"])
        except ValueError:                   # Feb 29 in a normal year
            d = date(y, 3, 1)
        if d >= today:
            return d
    return None


def add(name, month, day, year=None, note=None):
    name = " ".join(str(name or "").split())[:60]
    if isinstance(month, str):
        m = month.strip().lower()
        month = MONTHS.index(next(x for x in MONTHS if x.startswith(m[:3]))) + 1 if not m.isdigit() else int(m)
    month, day = int(month), int(day)
    if not name or not (1 <= month <= 12 and 1 <= day <= 31):
        return "Need a name, a month and a day."
    items = [b for b in _load() if b["name"].lower() != name.lower()]
    items.append({"name": name, "month": month, "day": day, "year": int(year) if year else None, "note": (note or "")[:200]})
    _save(items)
    return f"Got it: {name}, {MONTHS[month - 1].title()} {day}. I'll remind you three days before and on the day."


def remove(name):
    items = _load()
    keep = [b for b in items if name.lower() not in b["name"].lower()]
    _save(keep)
    return "Forgotten." if len(keep) < len(items) else f"I don't have a birthday for {name}."


def upcoming(n=6):
    items = _load()
    if not items:
        return "No birthdays saved yet. Tell me one, like \"Kai's birthday is March 3rd\"."
    today = date.today()
    rows = sorted(((_next(b), b) for b in items), key=lambda x: x[0])[:n]
    out = []
    for d, b in rows:
        days = (d - today).days
        when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days ({d:%A %B} {d.day})"
        age = f", turning {d.year - b['year']}" if b.get("year") else ""
        out.append(f"{b['name']}: {when}{age}" + (f" - {b['note']}" if b.get("note") else ""))
    return "\n".join(out)


def due(today=None):
    """[(kind, birthday, date)] for reminders today: 'soon' (3 days ahead) and 'today'."""
    today = today or date.today()
    out = []
    for b in _load():
        d = _next(b, today)
        if d is None:
            continue
        days = (d - today).days
        if days == 0:
            out.append(("today", b, d))
        elif days == 3:
            out.append(("soon", b, d))
    return out
