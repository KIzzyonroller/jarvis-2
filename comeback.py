"""
"Where did I leave off": after a real break, a short spoken catch-up the moment you're back at the PC.

  * what you were in before you left (activity memory: the app and file/page)
  * the last thing you asked him, if it was recent
  * what's coming up soon (reminders, calendar in the next couple of hours)

Built from what's on this PC, no AI call, so it's instant and free. Also fires "when I get back" triggers.
Settings > Conversation > While you're away. Never during quiet hours, while muted, or straight into a game or call.
"""
import os
import threading
import time
from datetime import datetime, timedelta

import config

CORE = None


def _mins():
    try:
        return int(os.environ.get("JARVIS_WELCOME_BACK", "20") or 0)
    except ValueError:
        return 20


def _before(core, left_at):
    """(app, short title) you were in before the break, from activity memory."""
    act = getattr(core, "activity", None)
    if act is None:
        return None
    import activity
    try:
        rows = [r for r in act.sessions(datetime.fromtimestamp(left_at - 3600), datetime.fromtimestamp(left_at))
                if not r.get("idle") and r["e"] - r["s"] >= 20]
    except Exception:
        return None
    if not rows:
        return None
    r = rows[-1]
    return r["app"], activity.short_title(r["title"], r["app"])


def _last_ask(core, left_at):
    h = getattr(core, "history", None)
    if h is None:
        return None
    try:
        rows = h.search("", days=1, who="You", limit=25)
    except Exception:
        return None
    for r in rows:
        if left_at - 3 * 3600 < r["ts"] <= left_at + 30 and len(r["text"]) > 8:
            return r["text"]
    return None


def _soon():
    out = []
    try:
        import tools
        now = datetime.now()
        for r in tools.REMINDERS.items:
            due = datetime.fromisoformat(r["due"])
            if now <= due <= now + timedelta(hours=3):
                out.append(f"{r['message']} at {due:%I:%M %p}".replace(" 0", " "))
    except Exception:
        pass
    return out[:2]


def summary(core, left_at, away_mins):
    parts, cards = [], []
    b = _before(core, left_at)
    if b:
        app, title = b
        parts.append(f"you were in {app}" + (f" on {title}" if title and title.lower() != app.lower() else ""))
        cards.append({"time": "Before", "text": f"{app}" + (f": {title}" if title else "")})
    ask = _last_ask(core, left_at)
    if ask:
        short = ask if len(ask) < 70 else ask[:67].rsplit(" ", 1)[0] + "..."
        parts.append(f"and the last thing you asked me was \"{short}\"")
        cards.append({"time": "Asked", "text": short})
    soon = _soon()
    if soon:
        parts.append("coming up: " + "; ".join(soon))
        cards += [{"time": "Soon", "text": s} for s in soon]
    if not parts:
        return None, None
    span = f"{away_mins / 60:.1f} hours".replace(".0 ", " ") if away_mins >= 90 else f"{round(away_mins)} minutes"
    line = f"Welcome back. Before you left, " + ", ".join(parts) + "."
    if not b and not ask:
        line = "Welcome back. " + parts[0][0].upper() + parts[0][1:] + "."
    return line, {"title": f"Away {span}", "list": cards}


def _loop():
    import proactive
    away_since = None
    time.sleep(60)
    while True:
        time.sleep(3)
        try:
            idle = proactive._idle_seconds()
        except Exception:
            continue
        mins = _mins()
        if idle >= max(mins, 5) * 60:
            if away_since is None:
                away_since = time.time() - idle
            continue
        if away_since is None or idle > 10:
            continue
        left, away_since = away_since, None
        away = (time.time() - left) / 60
        core = CORE
        try:
            import triggers
            triggers.on_back(away)
        except Exception as e:
            print(f"[welcome back] triggers: {e}")
        if not mins or away < mins:
            continue
        time.sleep(4)                                   # let them sit down and look first
        import moments
        if moments._busy_or_away(core, (0, 60)):
            continue
        line, card = summary(core, left, away)
        if line:
            print(f"[welcome back] {line}")
            core.events.put(("moment", {"line": line, "cards": [card]}))


def start(core):
    global CORE
    CORE = core
    threading.Thread(target=_loop, daemon=True, name="welcome-back").start()
