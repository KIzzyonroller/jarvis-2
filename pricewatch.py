"""
Price watcher: "tell me when that GPU drops under $400", "watch Elden Ring on Steam for a sale",
"let me know if Bitcoin goes over 120k".

What it can watch:
  * a product page, by its link: he reads the price the store publishes for search engines (the schema.org
    "offers" data most stores include: Best Buy, Newegg, Walmart, B&H, most Shopify shops...). Amazon usually
    blocks this; he tells you when a page won't give him a price instead of guessing.
  * a Steam game: Steam's own price, in your country's currency.
  * a stock or crypto: through the stocks module.

Checked every 6 hours (stocks and crypto every 15 minutes). When the price crosses your line he tells you once,
puts it on your desktop, and stops watching it (say "keep watching" to re-arm).
"""
import json
import re
import threading
import time
import urllib.request
import uuid
from datetime import datetime

import config

FILE = "price_watch.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36")
_lock = threading.Lock()
CORE = None


def _load():
    try:
        return json.loads((config.JARVIS_DIR / FILE).read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items):
    p = config.JARVIS_DIR / FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ reading prices
def _num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def page_price(url):
    """(price, currency, title) from a product page's structured data, or raises with a plain reason."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read(3_000_000).decode("utf-8", "replace")
    title = (re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I) or [None, ""])[1].strip()[:120]
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for node in _walk(data):
            offers = node.get("offers") if isinstance(node, dict) else None
            if not offers:
                continue
            for off in offers if isinstance(offers, list) else [offers]:
                if not isinstance(off, dict):
                    continue
                p = _num(off.get("price") or off.get("lowPrice"))
                if p:
                    return p, off.get("priceCurrency") or "", node.get("name") or title
    m = re.search(r'(?:itemprop|property)=["\'](?:price|product:price:amount|og:price:amount)["\'][^>]*content=["\']([\d.,]+)', html, re.I) \
        or re.search(r'content=["\']([\d.,]+)["\'][^>]*(?:itemprop|property)=["\'](?:price|product:price:amount)', html, re.I)
    if m:
        return _num(m.group(1)), "", title
    if "captcha" in html.lower() or "robot" in html.lower()[:20000]:
        raise ValueError("the store blocked me (a robot check)")
    raise ValueError("that page doesn't publish its price in a way I can read")


def _walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def steam_price(name):
    import steam
    app = steam.appid_for(name)
    if not app:
        raise ValueError(f"couldn't find {name} on Steam")
    cc = (getattr(config, "COUNTRY", "") or "us").lower()
    url = f"https://store.steampowered.com/api/appdetails?appids={app}&cc={cc}&filters=price_overview,basic"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=12) as r:
        d = json.loads(r.read().decode())[str(app)]["data"]
    po = d.get("price_overview")
    if not po:
        raise ValueError(f"{d.get('name', name)} has no price on Steam (free, or not sold here)")
    return po["final"] / 100, po.get("currency", ""), d.get("name", name), po.get("discount_percent", 0)


def market_price(symbol):
    import stocks
    try:
        sym = stocks.resolve(symbol)[0] or symbol         # "bitcoin" -> BTC-USD, "nvidia" -> NVDA
    except Exception:
        sym = symbol
    q = stocks.quote(sym)
    if not q or not q.get("price"):
        raise ValueError(f"no price for {symbol}")
    return float(q["price"]), q.get("currency", "USD"), q.get("name") or symbol


def check_one(w):
    kind = w["kind"]
    if kind == "url":
        p, cur, title = page_price(w["target"])
        return p, cur, title, None
    if kind == "steam":
        p, cur, title, disc = steam_price(w["target"])
        return p, cur, title, disc
    p, cur, title = market_price(w["target"])
    return p, cur, title, None


# ------------------------------------------------------------------ watching
def add(kind, target, below=None, above=None, label=None):
    kind = (kind or "").lower()
    if kind not in ("url", "steam", "stock", "crypto"):
        return "Watch a product link (url), a Steam game (steam), or a stock / crypto symbol (stock)."
    if below is None and above is None and kind != "steam":
        return "Watch for what: a price it drops below, or one it goes above?"
    w = {"id": uuid.uuid4().hex[:5], "kind": "stock" if kind == "crypto" else kind, "target": str(target).strip(),
         "below": _num(below), "above": _num(above), "label": label or "", "made": datetime.now().isoformat(timespec="minutes"),
         "on": True, "history": []}
    try:
        p, cur, title, disc = check_one(w)
    except Exception as e:
        return f"Couldn't read a price there: {e}. Try another store's link."
    w["label"] = w["label"] or (title or w["target"])[:80]
    w["currency"] = cur
    w["history"].append([int(time.time()), p])
    with _lock:
        items = _load()
        items.append(w)
        _save(items)
    goal = (f"below {w['below']:g}" if w["below"] is not None else "") + (" or " if w["below"] is not None and w["above"] is not None else "") + \
           (f"above {w['above']:g}" if w["above"] is not None else "") or "a sale"
    return (f"Watching {w['label']}: {p:,.2f} {cur} right now. I'll tell you when it's {goal}." +
            (f" It's already {disc}% off." if disc else ""))


def _hit(w, p, disc):
    if w["kind"] == "steam" and w["below"] is None and w["above"] is None:
        return bool(disc)
    return (w["below"] is not None and p <= w["below"]) or (w["above"] is not None and p >= w["above"])


def check_all(force=False):
    said = []
    with _lock:
        items = _load()
    now = time.time()
    for w in items:
        if not w.get("on", True):
            continue
        every = 900 if w["kind"] == "stock" else 6 * 3600
        if not force and now - w.get("checked", 0) < every:
            continue
        w["checked"] = now
        try:
            p, cur, title, disc = check_one(w)
            w["error"] = ""
        except Exception as e:
            w["error"] = str(e)[:140]
            continue
        w["history"] = (w.get("history", []) + [[int(now), p]])[-60:]
        if _hit(w, p, disc):
            w["on"] = False
            said.append((w, p, cur, disc))
    with _lock:
        cur_items = {x["id"]: x for x in _load()}
        for w in items:
            if w["id"] in cur_items:
                cur_items[w["id"]].update({k: w[k] for k in ("checked", "history", "on", "error") if k in w})
        _save(list(cur_items.values()))
    for w, p, cur, disc in said:
        _announce(w, p, cur, disc)
    return said


def _announce(w, p, cur, disc):
    first = w["history"][0][1] if w.get("history") else p
    line = (f"Price alert: {w['label']} is {p:,.2f} {cur} now" + (f", {disc}% off" if disc else "") +
            (f", down from {first:,.2f}" if first and p < first else "") + ".")
    print(f"[prices] {line}")
    core = CORE
    if core is None:
        return
    try:
        import pulls
        pulls.pull("price", {"label": w["label"], "price": p, "cur": cur, "goal": w.get("below") or w.get("above"),
                             "history": w.get("history", [])[-30:], "link": w["target"] if w["kind"] == "url" else ""},
                   id=f"price-{w['id']}", title="Price alert", ttl=600, auto=False)
    except Exception as e:
        print(f"[prices] panel: {e}")
    core.events.put(("moment", {"line": line + " I've stopped watching it; say keep watching if you want more.", "cards": []}))


def listing():
    items = _load()
    if not items:
        return "Not watching any prices."
    out = []
    for w in items:
        last = w["history"][-1][1] if w.get("history") else None
        goal = f"< {w['below']:g}" if w.get("below") is not None else f"> {w['above']:g}" if w.get("above") is not None else "any sale"
        out.append(f"[{w['id']}] {w['label']}: {last:,.2f} {w.get('currency', '')} (want {goal})" if last is not None
                   else f"[{w['id']}] {w['label']} (want {goal})")
        if not w.get("on", True):
            out[-1] += " (alerted, paused)"
        if w.get("error"):
            out[-1] += f" (last check failed: {w['error']})"
    return "Price watches: " + "; ".join(out)


def remove(what):
    with _lock:
        items = _load()
        keep = [w for w in items if w["id"] != what and (not what or what.lower() not in w["label"].lower())]
        _save(keep)
    return f"Stopped {len(items) - len(keep)} watch{'es' if len(items) - len(keep) != 1 else ''}." if len(keep) < len(items) else "No watch like that."


def rearm(what):
    with _lock:
        items = _load()
        n = 0
        for w in items:
            if w["id"] == what or (what and what.lower() in w["label"].lower()):
                w["on"] = True
                n += 1
        _save(items)
    return f"Watching again ({n})." if n else "No watch like that."


def tool(action="list", kind=None, target=None, below=None, above=None, label=None, id=None):
    a = (action or "list").lower()
    if a == "add":
        return add(kind, target, below, above, label)
    if a == "remove":
        return remove(id or label or target or "")
    if a == "rearm":
        return rearm(id or label or target or "")
    if a == "check":
        said = check_all(force=True)
        return (listing() + (f" {len(said)} alert(s) just went off." if said else ""))
    return listing()


def _loop():
    time.sleep(120)
    while True:
        try:
            if _load():
                check_all()
        except Exception as e:
            print(f"[prices] {e}")
        time.sleep(300)


def start(core):
    global CORE
    CORE = core
    threading.Thread(target=_loop, daemon=True, name="price-watch").start()
