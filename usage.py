"""
What he's costing you, and a daily spending limit.

Every Claude request reports how many tokens it used; this turns that into dollars with the price
table below, adds Groq speech and web searches, and keeps daily totals in Documents\\Jarvis\\usage.json.
The System panel shows today's and this month's spend. At 80% of the daily limit he gives you a heads-up;
at 100% he stops calling Claude until midnight (instant commands like "pause" or "volume 30" keep
working) unless you say "raise my budget to 10 dollars".

These are ESTIMATES. The prices were taken from published rate cards in October 2026 and can change;
Anthropic's console (console.anthropic.com, Usage) is the real bill. To correct a price, put a
prices.json in Documents\\Jarvis, e.g. {"claude-sonnet-5-5": {"in": 2, "out": 10, "cache_write": 2.5, "cache_read": 0.2}}
(dollars per million tokens).
"""
import json
import threading
import time
from datetime import datetime

import config

# dollars per million tokens: input, output, cache write (5-minute), cache read
PRICES = {
    "claude-sonnet-5-5": {"in": 2.0, "out": 10.0, "cache_write": 2.5, "cache_read": 0.20},
    "claude-opus-5-5": {"in": 4.0, "out": 20.0, "cache_write": 5.0, "cache_read": 0.40},
    "claude-haiku-5-5": {"in": 0.10, "out": 0.50, "cache_write": 0.125, "cache_read": 0.01},    # prompts under 100k tokens
}
HAIKU_LONG = 5.0               # Haiku 5.5 charges 5x for prompts over 100k tokens
WEB_SEARCH = 0.01              # per search
GROQ_PER_HOUR = 0.04           # Groq whisper-large-v3-turbo, each request billed as at least 10 seconds

_LOCK = threading.Lock()
_DATA = None


def _path():
    return config.JARVIS_DIR / "usage.json"


def _load():
    global _DATA
    if _DATA is None:
        try:
            _DATA = json.loads(_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _DATA = {}
        _DATA.setdefault("days", {})
    return _DATA


def _save():
    try:
        _path().parent.mkdir(parents=True, exist_ok=True)
        tmp = _path().with_suffix(".tmp")
        tmp.write_text(json.dumps(_DATA, indent=1), encoding="utf-8")
        tmp.replace(_path())
    except OSError:
        pass


def _prices(model):
    table = dict(PRICES)
    try:
        table.update(json.loads((config.JARVIS_DIR / "prices.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    if model in table:
        return table[model], True
    for name, p in table.items():                         # e.g. a dated model id: match its family
        if name in str(model) or str(model).startswith(name):
            return p, True
    return table["claude-sonnet-5-5"], False


def _day():
    return datetime.now().strftime("%Y-%m-%d")


def _add(usd, kind, **counts):
    with _LOCK:
        d = _load()["days"].setdefault(_day(), {"usd": 0.0, "claude": 0, "searches": 0, "speech_secs": 0.0})
        d["usd"] = round(d["usd"] + usd, 6)
        for k, v in counts.items():
            d[k] = d.get(k, 0) + v
        _save()
    return usd


def cost_of(model, u):
    """Dollars for one response's usage object (or dict)."""
    g = (lambda k: (u.get(k) if isinstance(u, dict) else getattr(u, k, None)) or 0)
    p, _ = _prices(model)
    inp, out, cw, cr = g("input_tokens"), g("output_tokens"), g("cache_creation_input_tokens"), g("cache_read_input_tokens")
    mult = HAIKU_LONG if "haiku" in str(model) and inp + cw + cr > 100_000 else 1.0
    usd = (inp * p["in"] + out * p["out"] + cw * p["cache_write"] + cr * p["cache_read"]) / 1e6 * mult
    stu = u.get("server_tool_use") if isinstance(u, dict) else getattr(u, "server_tool_use", None)
    searches = (stu.get("web_search_requests") if isinstance(stu, dict) else getattr(stu, "web_search_requests", 0)) or 0
    return usd + searches * WEB_SEARCH, searches


def record_claude(model, u):
    usd, searches = cost_of(model, u)
    return _add(usd, "claude", claude=1, searches=searches)


def record_groq(seconds):
    return _add(max(10.0, seconds) / 3600 * GROQ_PER_HOUR, "groq", speech_secs=round(seconds, 1))


def today():
    with _LOCK:
        return _load()["days"].get(_day(), {}).get("usd", 0.0)


def month():
    m = datetime.now().strftime("%Y-%m")
    with _LOCK:
        return sum(v.get("usd", 0.0) for k, v in _load()["days"].items() if k.startswith(m))


def budget():
    """Today's limit in dollars (0 = no limit)."""
    with _LOCK:
        d = _load()
        if d.get("budget_day") == _day() and d.get("budget_today") is not None:
            return float(d["budget_today"])
        if d.get("budget") is not None:
            return float(d["budget"])
    return float(config.DAILY_BUDGET)


def set_budget(dollars, today_only=False):
    with _LOCK:
        d = _load()
        if today_only:
            d["budget_today"], d["budget_day"] = float(dollars), _day()
        else:
            d["budget"] = float(dollars)
            d.pop("budget_today", None)
        _save()


def over_budget():
    b = budget()
    return b > 0 and today() >= b


def warn_due():
    """True once a day when spend passes 80% of the limit."""
    b = budget()
    if b <= 0 or today() < 0.8 * b:
        return False
    with _LOCK:
        d = _load()
        if d.get("warned") == _day():
            return False
        d["warned"] = _day()
        _save()
    return True


def snapshot():
    return {"today": round(today(), 4), "month": round(month(), 2), "budget": budget()}


def spoken():
    t, m, b = today(), month(), budget()
    lim = f" of your {b:.2f} dollar daily limit" if b > 0 else ""
    return f"About {t:.2f} dollars today{lim}, and {m:.2f} this month. That's an estimate; Anthropic's console has the exact bill."
