"""
Triggers: things he does by himself when something happens.

    "When I open Dead by Daylight, turn the lights red, open Discord and play my DBD playlist."
    "Every weekday at 8, tell me the market and the weather."
    "When I get back to my PC, tell me if I missed any Discord messages."
    "Every Sunday at 6pm, remind me to plan the week."

Kinds: app (a program or game starts), time (a time of day, on chosen days), back (you return after a break).
What to do is plain English, run exactly as if you'd said it, so anything he can do works (including your routines).
Stored in triggers.json. Settings > Conversation > Automation turns them all off.
"""
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime

import config

FILE = "triggers.json"
DAYS = {"daily": "0123456", "everyday": "0123456", "weekdays": "01234", "weekends": "56",
        "mon": "0", "tue": "1", "wed": "2", "thu": "3", "fri": "4", "sat": "5", "sun": "6"}
_lock = threading.Lock()
CORE = None


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower().replace(".exe", ""))


def load():
    try:
        return json.loads((config.JARVIS_DIR / FILE).read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(rules):
    (config.JARVIS_DIR / FILE).write_text(json.dumps(rules, indent=1), encoding="utf-8")


def _days(spec):
    spec = (spec or "daily").lower().replace(" ", "")
    if spec in DAYS:
        return DAYS[spec]
    out = ""
    for part in re.split(r"[,/&]|and", spec):
        out += DAYS.get(part[:3], "")
    return "".join(sorted(set(out))) or "0123456"


def _hhmm(at):
    m = re.match(r"^\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$", (at or "").lower())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if m.group(3) == "pm" and h < 12:
        h += 12
    if m.group(3) == "am" and h == 12:
        h = 0
    return f"{h:02d}:{mi:02d}" if 0 <= h < 24 and 0 <= mi < 60 else None


def describe(r):
    w = r["when"]
    if w["kind"] == "app":
        head = f"when {w['name']} opens"
    elif w["kind"] == "time":
        d = w.get("days", "0123456")
        dn = {"0123456": "every day", "01234": "weekdays", "56": "weekends"}.get(
            d, ", ".join("Mon Tue Wed Thu Fri Sat Sun".split()[int(i)] for i in d))
        head = f"{dn} at {w['at']}"
    else:
        head = "when you get back to the PC"
    return f"{head}: {r['do']}" + ("" if r.get("on", True) else " (paused)")


def add(kind, do, name=None, at=None, days=None):
    kind = (kind or "").lower()
    if not do or not str(do).strip():
        return "What should I do when it happens?"
    if kind == "app":
        if not name:
            return "Which app or game?"
        when = {"kind": "app", "name": name.strip()}
    elif kind == "time":
        hm = _hhmm(at)
        if not hm:
            return "What time? Like 8:00, 6pm or 21:30."
        when = {"kind": "time", "at": hm, "days": _days(days)}
    elif kind == "back":
        when = {"kind": "back"}
    else:
        return "When: an app or game opening (app), a time of day (time), or you getting back to the PC (back)."
    r = {"id": uuid.uuid4().hex[:6], "when": when, "do": str(do).strip()[:400], "on": True,
         "made": datetime.now().isoformat(timespec="minutes")}
    with _lock:
        rules = load()
        rules.append(r)
        _save(rules)
    return f"Trigger set ({r['id']}): {describe(r)}."


def remove(what):
    with _lock:
        rules = load()
        keep = [r for r in rules if r["id"] != what and (_norm(what) not in _norm(describe(r)) or not what)]
        if len(keep) == len(rules):
            return f"No trigger matching '{what}'."
        _save(keep)
    return f"Removed {len(rules) - len(keep)} trigger{'s' if len(rules) - len(keep) != 1 else ''}."


def pause(what, on):
    with _lock:
        rules = load()
        n = 0
        for r in rules:
            if what in ("all", "", None) or r["id"] == what or _norm(what) in _norm(describe(r)):
                r["on"] = on
                n += 1
        _save(rules)
    return f"{'Resumed' if on else 'Paused'} {n} trigger{'s' if n != 1 else ''}."


def listing():
    rules = load()
    if not rules:
        return "No triggers yet."
    return "Triggers: " + "; ".join(f"[{r['id']}] {describe(r)}" for r in rules)


# ------------------------------------------------------------------ firing
def _fire(r, why):
    core = CORE
    if core is None or os.environ.get("JARVIS_TRIGGERS", "true").lower() == "false" or not r.get("on", True):
        return
    print(f"[trigger] {why}: {r['do']}")
    with _lock:
        rules = load()
        for x in rules:
            if x["id"] == r["id"]:
                x["last"] = time.time()
        _save(rules)
    core.emit({"type": "toast", "text": f"Trigger: {r['do'][:80]}"})
    core.events.put(("text", ("watcher", f"(A trigger they set up is firing because {why}. Do this now, then at most "
                                         f"one short spoken line:) {r['do']}", time.time())))


def on_back(mins_away):
    for r in load():
        if r["when"]["kind"] == "back":
            _fire(r, f"they're back after {mins_away:.0f} minutes away")


def on_game(name):
    _app_started(name)


_GENERIC = {"", "app", "game", "launcher", "client", "music", "desktop", "the", "player", "browser", "studio", "beta", "ptb"}


def _rest_is_generic(rest):
    """'spotify' started and the trigger says 'Spotify music': the leftover word is generic, so it counts."""
    return rest in _GENERIC


def _app_started(name):
    n = _norm(name)
    if not n:
        return
    for r in load():
        w = r["when"]
        if w["kind"] != "app":
            continue
        want = _norm(w["name"])
        # "deadbydaylightwin64shipping" contains "deadbydaylight": yes. "steam" inside "steamvr": no (too short a part).
        if want and (want in n or (len(n) >= 5 and n in want and _rest_is_generic(want.replace(n, "", 1)))) \
                and time.time() - r.get("last", 0) > 120:
            _fire(r, f"{w['name']} just opened")


class Watch:
    def __init__(self):
        self.seen = None
        self.fired_today = set()

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="triggers").start()
        return self

    def _loop(self):
        import psutil
        time.sleep(30)
        while True:
            try:
                rules = load()
                if rules and os.environ.get("JARVIS_TRIGGERS", "true").lower() != "false":
                    self._apps(psutil, rules)
                    self._times(rules)
            except Exception as e:
                print(f"[trigger] {e}")
            time.sleep(4)

    def _apps(self, psutil, rules):
        if not any(r["when"]["kind"] == "app" for r in rules):
            return
        now = set()
        for p in psutil.process_iter(["name"]):
            nm = (p.info.get("name") or "").lower()
            if nm:
                now.add(nm)
        if self.seen is not None:
            for nm in now - self.seen:
                _app_started(nm)
        self.seen = now

    def _times(self, rules):
        now = datetime.now()
        day = now.strftime("%Y-%m-%d")
        for r in rules:
            w = r["when"]
            if w["kind"] != "time" or str(now.weekday()) not in w.get("days", "0123456"):
                continue
            h, m = map(int, w["at"].split(":"))
            due = now.replace(hour=h, minute=m, second=0, microsecond=0)
            key = f"{r['id']}:{day}"
            if key in self.fired_today:
                continue
            if 0 <= (now - due).total_seconds() <= 15 * 60:        # up to 15 minutes late (PC asleep, busy)
                self.fired_today.add(key)
                _fire(r, f"it's {w['at']}")


def start(core):
    global CORE
    CORE = core
    return Watch().start()
