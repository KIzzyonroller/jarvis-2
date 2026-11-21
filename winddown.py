"""
Wind-down: a slow landing before bed instead of a sudden "goodnight".

Set a bedtime (Settings > Conversation > Check-ins, or "my bedtime is 11:30"). Thirty minutes before it:
  * one quiet line: how long until bed, the first thing tomorrow, the morning weather
  * whisper mode on (quiet and short) until morning
  * lights slowly dim and warm over the half hour (if you have smart lights)
At bedtime, if you're still on the PC, one gentle nudge offering goodnight (which can sleep or lock the PC).
Never mid-game or mid-call: he waits for a gap, and gives up for the night if there isn't one.
"Start winding down" does it now; "skip wind-down tonight" cancels tonight's.
"""
import os
import threading
import time
from datetime import datetime, timedelta

import config

CORE = None
STATE = {"night": None, "stage": 0, "skip": None}
LEAD_MIN = 30


def bedtime():
    v = (os.environ.get("JARVIS_BEDTIME", "off") or "off").strip().lower()
    if v in ("off", "", "none"):
        return None
    try:
        h, m = (v.split(":") + ["0"])[:2]
        return int(h), int(m)
    except ValueError:
        return None


def _night_key(now):
    """Bedtimes after midnight belong to the evening before."""
    return (now - timedelta(hours=12)).strftime("%Y-%m-%d")


def _bed_dt(now, hm):
    bed = now.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
    if hm[0] < 12 and now.hour >= 12:
        bed += timedelta(days=1)                 # 00:30 bedtime seen from the evening
    elif hm[0] >= 12 and now.hour < 12:
        bed -= timedelta(days=1)                 # the 23:00 bedtime seen from just after midnight
    return bed


def _tomorrow_line(core):
    out = []
    try:
        import moments
        items = moments.tomorrow_items(core)
        if items:
            out.append(f"first thing tomorrow is {items[0]['text']} at {items[0]['time']}")
        w = moments.tomorrow_weather(core)
        if w:
            out.append(f"it'll be {w['label'].lower()}, high of {w['high']}{w['unit'][-1]}" + (", with rain" if w["rain"] >= 50 else ""))
    except Exception:
        pass
    return "; ".join(out)


def _dim_lights(minutes=LEAD_MIN):
    """Bring the lights down to warm and low in steps over the half hour."""
    try:
        import smarthome
        av = smarthome.available()
        if not (av.get("hue") or av.get("ha")):
            return
    except Exception:
        return
    steps = [(70, "warm white"), (55, "warm white"), (40, "orange"), (28, "orange"), (18, "orange")]
    for i, (bri, color) in enumerate(steps):
        if STATE["skip"] == STATE["night"] or STATE["stage"] >= 3:
            return
        try:
            smarthome.control("brightness", "all", value=bri)
            if i in (0, 2):
                smarthome.control("color", "all", color=color)
        except Exception as e:
            print(f"[wind-down] lights: {e}")
            return
        time.sleep(minutes * 60 / len(steps))


def begin(core, manual=False):
    """The half-hour-before moment (or 'start winding down' by voice)."""
    hm = bedtime()
    now = datetime.now()
    STATE["night"] = _night_key(now)
    STATE["stage"] = 1
    mins = int((_bed_dt(now, hm) - now).total_seconds() // 60) if hm else None
    try:
        import quiet
        quiet.set_manual("on")                   # quiet and short until morning (quiet.py lets go at its "to" hour)
    except Exception:
        pass
    tomorrow = _tomorrow_line(core)
    lead = (f"About {mins} minutes to bed." if mins and mins > 2 else "Time to start winding down.")
    line = lead + (f" Tomorrow: {tomorrow}." if tomorrow else "") + " I'll keep it quiet from here."
    threading.Thread(target=_dim_lights, daemon=True, name="wind-down-lights").start()
    return line


def tool(action="start", time_=None):
    a = (action or "start").lower()
    if a == "set":
        v = (time_ or "").strip().lower()
        import triggers
        hm = triggers._hhmm(v) if v not in ("off", "none") else "off"
        if not hm:
            return "What time? Like 23:30 or 11:30pm."
        if CORE is not None:
            CORE.set_widgets({"JARVIS_BEDTIME": hm})
        return "Wind-down off." if hm == "off" else f"Bedtime set to {hm}. I'll start winding things down half an hour before."
    if a == "skip":
        STATE["skip"] = _night_key(datetime.now())
        try:
            import quiet
            quiet.set_manual(None)
        except Exception:
            pass
        return "Okay, no wind-down tonight."
    if a == "status":
        hm = bedtime()
        return f"Bedtime is {hm[0]:02d}:{hm[1]:02d}." if hm else "No bedtime set."
    if CORE is None:
        return "Not available."
    return begin(CORE, manual=True)


def _loop():
    time.sleep(60)
    while True:
        time.sleep(30)
        try:
            core = CORE
            hm = bedtime()
            if core is None or not hm:
                continue
            now = datetime.now()
            night = _night_key(now)
            if STATE["night"] != night:
                STATE.update(night=night, stage=0)
            if STATE["skip"] == night:
                continue
            bed = _bed_dt(now, hm)
            to_bed = (bed - now).total_seconds() / 60
            import moments
            if STATE["stage"] == 0 and 0 < to_bed <= LEAD_MIN:
                if moments._busy_or_away(core, (0, 1800)):
                    if to_bed < 10:
                        STATE["stage"] = 1               # never found a gap: skip the half-hour part tonight
                    continue
                core.events.put(("moment", {"line": begin(core), "cards": []}))
            elif STATE["stage"] in (0, 1) and -45 <= to_bed <= 0:
                if moments._busy_or_away(core, (0, 600)):
                    if to_bed < -40:
                        STATE["stage"] = 3
                    continue
                STATE["stage"] = 3
                core.events.put(("moment", {"line": "It's bedtime. Want me to say goodnight and put the PC to sleep?",
                                            "cards": [], "engage": 25}))
        except Exception as e:
            print(f"[wind-down] {e}")


def start(core):
    global CORE
    CORE = core
    threading.Thread(target=_loop, daemon=True, name="wind-down").start()
