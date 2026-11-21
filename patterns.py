"""
Learned suggestions: he notices your habits and offers to automate them, once each.

  "You've asked for the market and the weather around 8 every weekday this week. Want me to just tell you every
   weekday at 8?"
  "Every time you open Dead by Daylight you ask for your DBD playlist. Want me to put it on automatically?"

How: once a day he looks at the last 3 weeks of what you asked him (conversation history) and which apps you
opened (activity memory). A habit has to show up on at least 4 different days before he says anything. He
asks once per habit, never mid-game or mid-call, at most one suggestion a day, and "no" means never again.
Yes turns it into a trigger you can see and remove like any other.
"""
import hashlib
import json
import os
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta

import config

FILE = "patterns_seen.json"
CORE = None
MIN_DAYS = 4
LOOKBACK = 21
SKIP = re.compile(r"^(yes|no|yeah|nope|ok|okay|thanks?|thank you|stop|never mind|what|huh|hello|hi|hey)\b", re.I)


def _seen():
    try:
        return json.loads((config.JARVIS_DIR / FILE).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mark(key, how):
    s = _seen()
    s[key] = {"how": how, "at": datetime.now().isoformat(timespec="minutes")}
    (config.JARVIS_DIR / FILE).write_text(json.dumps(s, indent=1), encoding="utf-8")


def _norm(text):
    t = re.sub(r"\b(jarvis|please|can you|could you|hey|okay|ok|um|uh|for me|real quick)\b", " ", (text or "").lower())
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return " ".join(t.split())


def _asks(core):
    h = getattr(core, "history", None)
    if h is None:
        return []
    since = time.time() - LOOKBACK * 86400
    try:
        rows = h.db.execute("SELECT ts, who, text FROM messages WHERE ts >= ? ORDER BY ts", (since,)).fetchall()
    except Exception:
        return []
    return [(ts, _norm(tx)) for ts, who, tx in rows if who.lower() in ("you", "user") and len(tx.split()) >= 2
            and not SKIP.match(tx.strip()) and not tx.startswith("[")]


def time_habits(asks):
    """Same request, around the same time of day, on MIN_DAYS+ different days."""
    by = defaultdict(list)
    for ts, t in asks:
        if t:
            by[t].append(datetime.fromtimestamp(ts))
    out = []
    for t, when in by.items():
        days = {}
        for w in when:
            days.setdefault(w.date(), w)                      # first time that day
        if len(days) < MIN_DAYS:
            continue
        mins = sorted(w.hour * 60 + w.minute for w in days.values())
        med = mins[len(mins) // 2]
        close = [m for m in mins if abs(m - med) <= 45]
        if len(close) < MIN_DAYS:
            continue
        wk = [d.weekday() for d in days]
        weekdays = sum(1 for x in wk if x < 5) >= len(wk) - 1 and len(set(wk)) >= 3
        at = f"{(med // 15 * 15) // 60:02d}:{(med // 15 * 15) % 60:02d}"
        out.append({"kind": "time", "do": t, "at": at, "days": "weekdays" if weekdays else "daily", "n": len(close)})
    return sorted(out, key=lambda x: -x["n"])


def app_habits(core, asks):
    """Within 10 minutes of opening an app, the same request, on MIN_DAYS+ different days."""
    act = getattr(core, "activity", None)
    if act is None:
        return []
    end = datetime.now()
    try:
        ss = act.sessions(end - timedelta(days=LOOKBACK), end)
    except Exception:
        return []
    starts = defaultdict(list)                                # app -> first start each day
    seen_day = set()
    for s in ss:
        if s.get("idle"):
            continue
        d = datetime.fromtimestamp(s["s"]).date()
        if (s["app"], d) not in seen_day:
            seen_day.add((s["app"], d))
            starts[s["app"]].append(s["s"])
    out = []
    for app, ts_list in starts.items():
        if len(ts_list) < MIN_DAYS or app.lower() in ("explorer", "jarvis", "chrome", "msedge", "firefox", "windowsterminal"):
            continue
        count = defaultdict(set)
        for t0 in ts_list:
            for ts, t in asks:
                if t0 <= ts <= t0 + 600 and t:
                    count[t].add(datetime.fromtimestamp(t0).date())
        for t, days in count.items():
            if len(days) >= MIN_DAYS:
                out.append({"kind": "app", "do": t, "name": app, "n": len(days)})
    return sorted(out, key=lambda x: -x["n"])


def _key(h):
    raw = f"{h['kind']}|{h['do']}|{h.get('at', '')}|{h.get('name', '')}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def _already_automated(h):
    import triggers
    for r in triggers.load():
        if _norm(r["do"]) == h["do"]:
            return True
    return False


def find(core):
    asks = _asks(core)
    seen = _seen()
    for h in time_habits(asks) + app_habits(core, asks):
        if _key(h) not in seen and not _already_automated(h):
            return h
    return None


def offer(core, h):
    if h["kind"] == "time":
        when = "every weekday" if h["days"] == "weekdays" else "every day"
        line = (f"I've noticed you ask me \"{h['do']}\" around {h['at']} most days. Want me to just do it {when} at "
                f"{h['at']}?")
        setup = f"triggers add when=time at={h['at']} days={h['days']} do=\"{h['do']}\""
    else:
        line = (f"Every time you open {h['name']} you end up asking me \"{h['do']}\". Want me to do that "
                f"automatically when it opens?")
        setup = f"triggers add when=app name=\"{h['name']}\" do=\"{h['do']}\""
    b = core.brain
    if b is not None and isinstance(getattr(b, "history", None), list) and (not b.history or b.history[-1]["role"] == "assistant"):
        b.history.append({"role": "user", "content": f"[You noticed a habit and are offering to automate it: {setup}. "
                                                      f"If they say yes, set it up with exactly that, then confirm in one "
                                                      f"line. If no, say fine and don't bring it up again.]"})
        b.history.append({"role": "assistant", "content": [{"type": "text", "text": line}]})
    _mark(_key(h), "offered")
    core.events.put(("moment", {"line": line, "cards": [{"title": "A habit I noticed", "text": h["do"]}], "engage": 25}))
    print(f"[patterns] offered: {h}")


def tool(action="suggest"):
    """suggest: look now (ignores the once-a-day limit); list: what he's noticed so far; reset: forget the 'no's."""
    a = (action or "suggest").lower()
    if a == "reset":
        (config.JARVIS_DIR / FILE).unlink(missing_ok=True)
        return "Forgot which habits I'd already asked about."
    if CORE is None:
        return "Not available."
    if a == "list":
        asks = _asks(CORE)
        hs = time_habits(asks) + app_habits(CORE, asks)
        if not hs:
            return "No habits stand out yet (each needs at least 4 days of history)."
        return "Habits I've noticed: " + "; ".join(
            (f"\"{h['do']}\" around {h['at']} ({h['n']} days)" if h["kind"] == "time" else f"\"{h['do']}\" after opening {h['name']} ({h['n']} days)")
            for h in hs[:8])
    h = find(CORE)
    if not h:
        return "Nothing new worth automating yet."
    offer(CORE, h)
    return "Offered it (they'll hear it)."


def _loop():
    time.sleep(600)
    while True:
        try:
            core = CORE
            if core is not None and os.environ.get("JARVIS_SUGGEST", "true").lower() != "false":
                day = datetime.now().strftime("%Y-%m-%d")
                last = core._state_flag("pattern_day")
                if last != day and 10 <= datetime.now().hour < 22:
                    import moments
                    if not moments._busy_or_away(core, (10, 900)):
                        core._state_flag("pattern_day", day)
                        h = find(core)
                        if h:
                            offer(core, h)
        except Exception as e:
            print(f"[patterns] {e}")
        time.sleep(1800)


def start(core):
    global CORE
    CORE = core
    threading.Thread(target=_loop, daemon=True, name="habits").start()
