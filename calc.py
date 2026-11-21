"""
Quick maths and conversions, answered instantly on this PC (no AI call), with the working shown on your desktop.

  "what's 15% of 240"         "18 percent tip on 64.50"     "what's 1250 divided by 12"
  "convert 5 miles to km"     "350 fahrenheit in celsius"   "how many cups in a liter"
  "200 grams of flour in cups" (flour, sugar, butter, rice, water)
  "100 dollars in quetzales"  (live rates from the European Central Bank, cached for 6 hours)
"""
import ast
import json
import math
import operator
import re
import time
import urllib.request

# ------------------------------------------------------------------ safe arithmetic
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv, ast.USub: operator.neg,
        ast.UAdd: operator.pos}
_FUNCS = {"sqrt": math.sqrt, "sin": lambda x: math.sin(math.radians(x)), "cos": lambda x: math.cos(math.radians(x)),
          "tan": lambda x: math.tan(math.radians(x)), "log": math.log10, "ln": math.log, "abs": abs, "round": round,
          "pi": math.pi, "e": math.e}


def _ev(n):
    if isinstance(n, ast.Expression):
        return _ev(n.body)
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
        return n.value
    if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
        a, b = _ev(n.left), _ev(n.right)
        if isinstance(n.op, ast.Pow) and abs(b) > 100:
            raise ValueError("too big")
        return _OPS[type(n.op)](a, b)
    if isinstance(n, ast.UnaryOp) and type(n.op) in _OPS:
        return _OPS[type(n.op)](_ev(n.operand))
    if isinstance(n, ast.Name) and n.id in _FUNCS and not callable(_FUNCS[n.id]):
        return _FUNCS[n.id]
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and len(n.args) == 1:
        return _FUNCS[n.func.id](_ev(n.args[0]))
    raise ValueError("not plain maths")


WORDS = [(r"\bplus\b", "+"), (r"\bminus\b", "-"), (r"\b(times|multiplied by|x)\b", "*"), (r"\bdivided by\b|\bover\b", "/"),
         (r"\bto the power of\b|\bto the\b|\^", "**"), (r"\bsquared\b", "**2"), (r"\bcubed\b", "**3"),
         (r"\bsquare root of\b", "sqrt "), (r"(\d),(\d{3})", r"\1\2"), (r"[$€£]", "")]


def arithmetic(expr):
    e = expr.lower().strip().rstrip("?.")
    for rx, rep in WORDS:
        e = re.sub(rx, rep, e)
    e = re.sub(r"sqrt\s+([\d.]+)", r"sqrt(\1)", e)
    if not re.fullmatch(r"[\d\s+\-*/().%a-z]*", e) or not re.search(r"\d", e):
        return None
    try:
        v = _ev(ast.parse(e, mode="eval"))
    except Exception:
        return None
    return float(v)


def nice(v):
    if v is None:
        return "?"
    if abs(v) >= 1e15 or (v and abs(v) < 1e-6):
        return f"{v:.4g}"
    if float(v).is_integer():
        return f"{int(v):,}"
    return f"{v:,.4f}".rstrip("0").rstrip(".")


# ------------------------------------------------------------------ units
LEN = {"mm": .001, "millimeter": .001, "cm": .01, "centimeter": .01, "m": 1, "meter": 1, "metre": 1, "km": 1000,
       "kilometer": 1000, "kilometre": 1000, "in": .0254, "inch": .0254, "inches": .0254, "ft": .3048, "foot": .3048,
       "feet": .3048, "yd": .9144, "yard": .9144, "mi": 1609.344, "mile": 1609.344}
MASS = {"mg": .001, "g": 1, "gram": 1, "kg": 1000, "kilo": 1000, "kilogram": 1000, "oz": 28.3495, "ounce": 28.3495,
        "lb": 453.592, "lbs": 453.592, "pound": 453.592, "ton": 907184.74, "tonne": 1e6, "stone": 6350.29}
VOL = {"ml": 1, "milliliter": 1, "l": 1000, "liter": 1000, "litre": 1000, "tsp": 4.92892, "teaspoon": 4.92892,
       "tbsp": 14.7868, "tablespoon": 14.7868, "cup": 236.588, "floz": 29.5735, "fluid ounce": 29.5735, "pint": 473.176,
       "quart": 946.353, "gallon": 3785.41}
SPEED = {"kmh": 1, "km/h": 1, "kph": 1, "mph": 1.609344, "m/s": 3.6, "knot": 1.852}
DATA = {"b": 1, "byte": 1, "kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12, "kib": 1024, "mib": 1024 ** 2, "gib": 1024 ** 3}
TIME = {"second": 1, "sec": 1, "minute": 60, "min": 60, "hour": 3600, "hr": 3600, "day": 86400, "week": 604800,
        "year": 31557600}
TABLES = [LEN, MASS, VOL, SPEED, DATA, TIME]
DENSITY = {"water": 1.0, "milk": 1.03, "flour": .53, "sugar": .85, "brown sugar": .93, "butter": .96, "rice": .85,
           "oil": .92, "honey": 1.42, "salt": 1.2, "oats": .41}     # grams per millilitre, cooking averages
TEMP = {"c": "c", "celsius": "c", "centigrade": "c", "f": "f", "fahrenheit": "f", "k": "k", "kelvin": "k"}
CUR_NAMES = {"dollar": "USD", "dollars": "USD", "usd": "USD", "bucks": "USD", "euro": "EUR", "euros": "EUR", "eur": "EUR",
             "pound sterling": "GBP", "pounds sterling": "GBP", "gbp": "GBP", "quetzal": "GTQ", "quetzales": "GTQ",
             "quetzals": "GTQ", "gtq": "GTQ", "peso": "MXN", "pesos": "MXN", "mxn": "MXN", "yen": "JPY", "jpy": "JPY",
             "canadian dollar": "CAD", "canadian dollars": "CAD", "cad": "CAD", "yuan": "CNY", "cny": "CNY",
             "rupee": "INR", "rupees": "INR", "inr": "INR", "real": "BRL", "reais": "BRL", "brl": "BRL",
             "franc": "CHF", "francs": "CHF", "chf": "CHF", "won": "KRW", "krw": "KRW", "aud": "AUD",
             "australian dollar": "AUD", "australian dollars": "AUD"}
_RATES = {"t": 0, "rates": {}}


def _unit(u):
    u = u.lower().strip().rstrip(".")
    for cand in (u, u.rstrip("s"), u[:-2] if u.endswith("es") else u):
        for t in TABLES:
            if cand in t:
                return t, t[cand]
    return None, None


def _rates():
    if time.time() - _RATES["t"] < 6 * 3600 and _RATES["rates"]:
        return _RATES["rates"]
    try:
        with urllib.request.urlopen("https://open.er-api.com/v6/latest/USD", timeout=6) as r:
            d = json.loads(r.read().decode())
        if d.get("result") == "success":
            _RATES.update(t=time.time(), rates=d["rates"])
    except Exception as e:
        print(f"[calc] rates: {e}")
    return _RATES["rates"]


def _currency(word):
    w = word.lower().strip()
    if w in CUR_NAMES:
        return CUR_NAMES[w]
    if re.fullmatch(r"[a-z]{3}", w) and w.upper() in (_RATES["rates"] or {}):
        return w.upper()
    return None


def convert(text, offline=False):
    """'5 miles to km' -> (answer text, working) or None. offline: don't fetch exchange rates (just say if it's money)."""
    t = text.lower().strip().rstrip("?.")
    t = re.sub(r"^(convert|what is|what's|whats|how much is|how many)\s+", "", t)
    m = re.match(r"^([\d.,]+)\s*(?:degrees?\s*)?([a-z/ ]+?)\s+(?:to|in|into|as)\s+(?:degrees?\s*)?([a-z/ ]+)$", t)
    if not m:
        m2 = re.match(r"^([a-z ]+?)\s+in\s+(?:a|an|one)\s+([a-z ]+)$", t)        # "cups in a liter"
        if m2:
            return convert(f"1 {m2.group(2)} to {m2.group(1)}", offline)
        return None
    num = float(m.group(1).replace(",", ""))
    a, b = m.group(2).strip(), m.group(3).strip()
    # temperature
    if a in TEMP and b in TEMP:
        fa, fb = TEMP[a], TEMP[b]
        c = num if fa == "c" else (num - 32) * 5 / 9 if fa == "f" else num - 273.15
        out = c if fb == "c" else c * 9 / 5 + 32 if fb == "f" else c + 273.15
        return f"{nice(num)}°{fa.upper()} is {nice(round(out, 1))}°{fb.upper()}", f"{nice(num)} {fa.upper()} → {fb.upper()}"
    # money
    ca, cb = _currency(a), _currency(b)
    if (ca or cb) and not (ca and cb):
        for side in ("a", "b"):                          # "100 pounds in dollars": pounds sterling, not weight
            if (a if side == "a" else b) in ("pound", "pounds", "quid"):
                ca, cb = (ca or "GBP", cb) if side == "a" else (ca, cb or "GBP")
    if ca or cb:
        if offline:
            return ("(money)", "") if (ca and cb) else None
        rates = _rates()
        ca, cb = ca or _currency(a), cb or _currency(b)
        if not (ca and cb and rates.get(ca) and rates.get(cb)):
            return None
        out = num / rates[ca] * rates[cb]
        return (f"{nice(num)} {ca} is about {nice(round(out, 2))} {cb}",
                f"1 {ca} = {nice(round(rates[cb] / rates[ca], 4))} {cb} (today's rate)")
    # cooking: weight <-> volume of an ingredient ("200 grams of flour in cups")
    ing = None
    mi = re.match(r"^(.+?)\s+of\s+(.+)$", a)
    if mi and mi.group(2) in DENSITY:
        a, ing = mi.group(1), mi.group(2)
    ta, fa = _unit(a)
    tb, fb = _unit(b)
    if ta is None or tb is None:
        return None
    if ta is tb:
        out = num * fa / fb
        return f"{nice(num)} {a} is {nice(round(out, 3))} {b}", f"{nice(num)} × {nice(fa / fb)}"
    if {id(ta), id(tb)} == {id(MASS), id(VOL)}:
        dens = DENSITY.get(ing or "water")
        grams = num * fa if ta is MASS else num * fa * dens
        out = grams / fb if tb is MASS else grams / dens / fb
        return (f"{nice(num)} {a}{' of ' + ing if ing else ''} is about {nice(round(out, 2))} {b}",
                f"using {ing or 'water'} at {dens} g per ml")
    return None


def percent(text):
    t = text.lower().strip().rstrip("?.")
    m = re.search(r"([\d.]+)\s*(?:%|percent)\s*(?:tip\s+)?(?:of|on)\s*\$?([\d.,]+)", t)
    if m:
        p, base = float(m.group(1)), float(m.group(2).replace(",", ""))
        v = p / 100 * base
        if "tip" in t:
            art = "An" if re.match(r"(8|11|18|80|800)(\D|$)", nice(p)) else "A"
            return f"{art} {nice(p)}% tip on {nice(base)} is {nice(round(v, 2))}, so {nice(round(base + v, 2))} in total", f"{nice(base)} × {nice(p / 100)}"
        return f"{nice(p)}% of {nice(base)} is {nice(round(v, 4))}", f"{nice(base)} × {nice(p / 100)}"
    m = re.search(r"([\d.,]+)\s+is what (?:percent|%) of\s+([\d.,]+)", t)
    if m:
        a, b = float(m.group(1).replace(",", "")), float(m.group(2).replace(",", ""))
        return f"{nice(a)} is {nice(round(a / b * 100, 2))}% of {nice(b)}", f"{nice(a)} ÷ {nice(b)} × 100"
    return None


def answer(text, offline=False):
    """(spoken answer, working) for maths or a conversion, or None if it isn't one."""
    for fn in (percent, lambda t: convert(t, offline)):
        try:
            r = fn(text)
        except Exception:
            r = None
        if r:
            return r
    t = re.sub(r"^(what's|whats|what is|calculate|compute|how much is|work out)\s+", "", text.lower().strip())
    v = arithmetic(t)
    if v is not None and re.search(r"[\d)]\s*[-+*/%^x]|\bplus\b|\bminus\b|\btimes\b|divided|sqrt|squared|power|root", t):
        return f"{nice(v)}", f"{t.strip().rstrip('?')} = {nice(v)}"
    return None


def show(text, ans, working):
    try:
        import pulls
        pulls.pull("calc", {"q": text.strip().rstrip("?"), "a": ans, "work": working}, id="calc", title="Worked out", ttl=45, auto=False)
    except Exception as e:
        print(f"[calc] panel: {e}")


def tool(expression):
    r = answer(expression or "")
    if not r:
        return "That isn't something I can work out exactly here; do it yourself step by step."
    show(expression, *r)
    return f"{r[0]}. (Working: {r[1]})"
