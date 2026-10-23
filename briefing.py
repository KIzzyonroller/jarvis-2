"""
Morning briefing: the facts are gathered locally and in parallel (each source has a short time limit,
so one slow site never holds the rest up), then the fast model turns them into a few spoken sentences
in his own voice. No web searches by Claude, so it's quick and cheap.

Sources (all free, no keys):
  * Weather: Open-Meteo (open-meteo.com). Location: JARVIS_CITY if set, otherwise your approximate
    location from your IP address (ipapi.co), remembered for a week.
  * Your reminders due today.
  * Discord messages since you were last at the PC (from Windows notifications, see notifications.py).
  * PC health, only if something's worth mentioning (low disk space, low battery).
  * Headlines: an RSS feed (default CBC top stories; JARVIS_NEWS_RSS to change, empty to turn off).
"""
import json
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import config

WMO = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "foggy with frost",
       51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
       61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
       71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains", 80: "rain showers", 81: "rain showers",
       82: "heavy rain showers", 85: "snow showers", 86: "heavy snow showers", 95: "thunderstorms",
       96: "thunderstorms with hail", 99: "thunderstorms with hail"}


WEATHER_DATA = {}
HEADLINES = []          # the last weather reading, as numbers (for the HUD's weather card)


def _get(url, params=None, timeout=4):
    import requests
    r = requests.get(url, params=params, timeout=(2, timeout), headers={"User-Agent": "Jarvis-assistant/1.0"})
    r.raise_for_status()
    return r


# ------------------------------------------------------------------ location + weather
def location(flags_get=None, flags_set=None):
    """(lat, lon, place, country_code) or None."""
    cached = flags_get("location") if flags_get else None
    if cached and time.time() - cached.get("t", 0) < 7 * 86400 and cached.get("city_setting") == config.CITY:
        return cached["lat"], cached["lon"], cached["place"], cached.get("cc", "")
    loc = None
    if config.CITY:
        q = ", ".join(x for x in (config.CITY,) if x)
        res = (_get("https://geocoding-api.open-meteo.com/v1/search", {"name": config.CITY, "count": 1}).json()
               .get("results") or [])
        if res:
            r = res[0]
            loc = (r["latitude"], r["longitude"], r.get("name") or q, r.get("country_code", ""))
    if loc is None:
        d = _get("https://ipapi.co/json/").json()
        if d.get("latitude") is not None:
            loc = (d["latitude"], d["longitude"], d.get("city") or "your area", d.get("country_code", ""))
    if loc and flags_set:
        flags_set("location", {"lat": loc[0], "lon": loc[1], "place": loc[2], "cc": loc[3], "t": time.time(),
                               "city_setting": config.CITY})
    return loc


def weather(loc):
    lat, lon, place, cc = loc
    fahrenheit = (config.COUNTRY or cc or "").upper() == "US"
    d = _get("https://api.open-meteo.com/v1/forecast", {
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 1,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
        "temperature_unit": "fahrenheit" if fahrenheit else "celsius",
        "wind_speed_unit": "mph" if fahrenheit else "kmh"}).json()
    unit = "°F" if fahrenheit else "°C"
    cur, day = d.get("current", {}), d.get("daily", {})
    first = lambda k: (day.get(k) or [None])[0]
    parts = [f"{place}: {WMO.get(cur.get('weather_code'), 'unknown')} and {round(cur.get('temperature_2m', 0))}{unit} now"]
    if cur.get("apparent_temperature") is not None and abs(cur["apparent_temperature"] - cur.get("temperature_2m", 0)) >= 3:
        parts.append(f"feels like {round(cur['apparent_temperature'])}{unit}")
    if first("temperature_2m_max") is not None:
        parts.append(f"high {round(first('temperature_2m_max'))}, low {round(first('temperature_2m_min'))}")
    if first("weather_code") is not None:
        parts.append(f"today mostly {WMO.get(first('weather_code'), 'mixed')}")
    if (first("precipitation_probability_max") or 0) >= 30:
        parts.append(f"{first('precipitation_probability_max')}% chance of precipitation")
    WEATHER_DATA.clear()
    WEATHER_DATA.update({"place": place, "unit": unit, "now": round(cur.get("temperature_2m", 0)),
                         "feels": round(cur.get("apparent_temperature", cur.get("temperature_2m", 0))),
                         "code": cur.get("weather_code"), "label": WMO.get(cur.get("weather_code"), ""),
                         "high": round(first("temperature_2m_max")) if first("temperature_2m_max") is not None else None,
                         "low": round(first("temperature_2m_min")) if first("temperature_2m_min") is not None else None,
                         "rain": first("precipitation_probability_max")})
    return ", ".join(parts)


# ------------------------------------------------------------------ the rest
def headlines(n=2):
    url = config.NEWS_RSS
    if not url:
        return None
    root = ET.fromstring(_get(url).content)
    titles = [(i.findtext("title") or "").strip() for i in root.iter("item")]
    titles = [t for t in titles if t][:n]
    HEADLINES[:] = titles
    return "; ".join(titles) or None


def reminders_today(items):
    today = datetime.now().date()
    out = []
    for r in items:
        try:
            due = datetime.fromisoformat(str(r["due"]))
        except (ValueError, KeyError):
            continue
        if due.date() == today and due >= datetime.now():          # still to come today
            out.append(f"{r['message']} at {due.strftime('%I:%M %p').lstrip('0')}")
    return "; ".join(out) or "nothing else due today"


def pc_health():
    try:
        import psutil
    except ImportError:
        return None
    notes = []
    try:
        import os
        disk = psutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\" if os.name == "nt" else "/")
        if disk.free < 15 * 2**30:
            notes.append(f"main drive only has {disk.free / 2**30:.0f} GB free")
    except Exception:
        pass
    try:
        b = psutil.sensors_battery()
        if b and not b.power_plugged and b.percent < 30:
            notes.append(f"battery at {round(b.percent)}%")
    except Exception:
        pass
    return "; ".join(notes) or None


def discord_since(watcher, since):
    if watcher is None or not watcher.ok:
        return None
    msgs = watcher.since(since)
    if not msgs:
        return "no new Discord messages"
    names = []
    for m in msgs:
        if m["sender"] not in names:
            names.append(m["sender"])
    last = msgs[-1]
    import notifications
    return (f"{len(msgs)} Discord message{'s' if len(msgs) != 1 else ''} from {', '.join(names[:4])}"
            f"{' and others' if len(names) > 4 else ''}; latest from {last['sender']}: \"{notifications.speakable(last['text'], 20)}\"")


def gather(reminder_items, watcher=None, discord_from=None, flags_get=None, flags_set=None, budget=5.0):
    """All the facts, gathered in parallel. Anything slower than `budget` seconds is left out."""
    facts = {}

    def run(key, fn, *a):
        try:
            v = fn(*a)
            if v:
                facts[key] = v
        except Exception as e:
            print(f"[briefing] {key}: {type(e).__name__}")

    def wx():
        loc = location(flags_get, flags_set)
        if loc:
            facts["weather"] = weather(loc)

    jobs = [threading.Thread(target=run, args=("weather", wx), daemon=True),
            threading.Thread(target=run, args=("headlines", headlines), daemon=True),
            threading.Thread(target=run, args=("pc", pc_health), daemon=True)]
    for j in jobs:
        j.start()
    run("reminders", reminders_today, reminder_items)
    if watcher is not None:
        run("discord", discord_since, watcher, discord_from or time.time() - 12 * 3600)
    end = time.time() + budget
    for j in jobs:
        j.join(max(0.0, end - time.time()))
    out = dict(facts)
    if "weather" in out and WEATHER_DATA:
        out["_weather"] = dict(WEATHER_DATA)
    if "headlines" in out:
        out["_headlines"] = list(HEADLINES)
    today = datetime.now().date()
    out["_reminders"] = []
    for r in reminder_items:
        try:
            due = datetime.fromisoformat(str(r["due"]))
        except (ValueError, KeyError):
            continue
        if due.date() == today and due >= datetime.now():
            out["_reminders"].append({"text": r["message"], "time": due.strftime("%I:%M %p").lstrip("0")})
    if watcher is not None and getattr(watcher, "ok", False):
        out["_discord"] = [{"from": m["sender"], "text": m["text"]} for m in watcher.since(discord_from or time.time() - 12 * 3600)][-6:]
    return out


def prompt(facts, morning=True):
    now = datetime.now()
    when = f"{now.strftime('%A, %B')} {now.day}, {now.strftime('%I:%M %p').lstrip('0')}"
    lines = [f"{k}: {v}" for k, v in (("Weather", facts.get("weather")), ("Reminders today", facts.get("reminders")),
                                      ("Discord", facts.get("discord")), ("PC", facts.get("pc")),
                                      ("Headlines", facts.get("headlines"))) if v]
    part = "morning" if 4 <= now.hour < 12 else "afternoon" if 12 <= now.hour < 18 else "evening"
    kind = (f"the user's {part} briefing (first time they're at the PC today)" if morning
            else "a quick catch-up briefing")
    return (f"[Give {kind}. It's {when}. Facts gathered just now:\n" + "\n".join(lines) +
            "\nSay it in your own voice: 4 to 6 short spoken sentences, most useful first (weather, then today's "
            "reminders, then Discord, then one headline). Natural speech, no lists, no markdown. Use only these "
            "facts; skip anything missing. Don't call any tools.]")


def fallback(facts):
    """If Claude can't be reached: a plain spoken version."""
    bits = []
    if facts.get("weather"):
        bits.append("Weather: " + facts["weather"] + ".")
    if facts.get("reminders"):
        bits.append("Today: " + facts["reminders"] + ".")
    if facts.get("discord"):
        bits.append(facts["discord"][0].upper() + facts["discord"][1:] + ".")
    if facts.get("headlines"):
        bits.append("In the news: " + facts["headlines"].split(";")[0] + ".")
    return " ".join(bits) or "Nothing to report."
