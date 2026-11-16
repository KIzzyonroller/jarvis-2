"""
Stocks: prices, why something moved, earnings dates, comparisons, a market rundown, your watchlist, and big-move
heads-ups. Jarvis gives his read on them (the bull case, the bear case, what he'd watch), never "buy this", and he
never trades: there's nothing here that can place an order.

Data: Yahoo Finance's public chart, search and quote-summary endpoints. Free, no key, no account. Unofficial, so it
can break or be slow; when it does, he says so and can search the web instead. Prices can be delayed (usually up to
15 minutes for US exchanges).

Settings > Stocks: your watchlist (JUNO_STOCKS), big-move alerts (JUNO_STOCK_ALERTS) and how big (JUNO_STOCK_ALERT_PCT),
and whether the morning briefing includes the market (JUNO_STOCKS_BRIEFING).
"""
import json
import re
import threading
import time
from datetime import datetime, timezone

import config

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0 Safari/537.36", "Accept": "application/json"}
Q1 = "https://query1.finance.yahoo.com"
Q2 = "https://query2.finance.yahoo.com"
STATE = "stocks.json"
INDEXES = [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"), ("^DJI", "Dow"), ("^VIX", "VIX"), ("BTC-USD", "Bitcoin")]
RANGES = {"1d": ("1d", "5m"), "5d": ("5d", "30m"), "1mo": ("1mo", "1d"), "3mo": ("3mo", "1d"), "6mo": ("6mo", "1d"),
          "ytd": ("ytd", "1d"), "1y": ("1y", "1d"), "5y": ("5y", "1wk"), "max": ("max", "1mo")}
NOT_ADVICE = "(Jarvis isn't a financial advisor: this is information and his read, not a recommendation.)"

_cache, _lock = {}, threading.Lock()
_session = None


# ------------------------------------------------------------------ plumbing
def _http():
    global _session
    if _session is None:
        import requests
        _session = requests.Session()
        _session.headers.update(UA)
    return _session


def _get(url, params=None, ttl=60, timeout=10):
    """JSON from Yahoo, cached for ttl seconds (prices barely change in a minute, and it keeps us polite)."""
    key = url + "?" + json.dumps(params or {}, sort_keys=True)
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    last = None
    for base in (url, url.replace(Q1, Q2)) if url.startswith(Q1) else (url,):
        try:
            r = _http().get(base, params=params, timeout=timeout)
            if r.status_code == 429:
                last = RuntimeError("Yahoo is rate-limiting us; try again in a minute")
                continue
            r.raise_for_status()
            data = r.json()
            with _lock:
                _cache[key] = (time.time(), data)
                if len(_cache) > 400:
                    for k in sorted(_cache, key=lambda k: _cache[k][0])[:100]:
                        _cache.pop(k, None)
            return data
        except Exception as e:
            last = e
    raise last or RuntimeError("no answer")


_crumb = {"v": None, "at": 0}


def _with_crumb(url, params):
    """Quote-summary needs a cookie and a 'crumb' token, which Yahoo hands out to anyone who asks."""
    if not _crumb["v"] or time.time() - _crumb["at"] > 3600:
        s = _http()
        try:
            s.get("https://fc.yahoo.com", timeout=8, allow_redirects=True)
        except Exception:
            pass
        r = s.get(Q1 + "/v1/test/getcrumb", timeout=8)
        if r.status_code != 200 or not r.text or "<" in r.text:
            raise RuntimeError("Yahoo wouldn't give out a token")
        _crumb.update(v=r.text.strip(), at=time.time())
    return _get(url, dict(params, crumb=_crumb["v"]), ttl=1800)


def _load():
    try:
        return json.loads((config.JARVIS_DIR / STATE).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(st):
    try:
        (config.JARVIS_DIR / STATE).write_text(json.dumps(st), encoding="utf-8")
    except Exception as e:
        print(f"[stocks] couldn't save: {e}")


def _money(v, cur="USD"):
    if v is None:
        return "?"
    sym = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CAD": "C$", "AUD": "A$"}.get(cur or "USD", "")
    if abs(v) >= 1e12:
        return f"{sym}{v / 1e12:.2f} trillion"
    if abs(v) >= 1e9:
        return f"{sym}{v / 1e9:.1f} billion"
    if abs(v) >= 1e6:
        return f"{sym}{v / 1e6:.1f} million"
    return f"{sym}{v:,.2f}" + ("" if sym else f" {cur}")


def _pct(v):
    if v is None:
        return "?"
    v = 0.0 if abs(v) < 0.005 else v
    return f"{'+' if v >= 0 else ''}{v:.2f}%"


# ------------------------------------------------------------------ symbols
COMMON = {"google": "GOOGL", "alphabet": "GOOGL", "facebook": "META", "meta": "META", "apple": "AAPL", "microsoft": "MSFT",
          "amazon": "AMZN", "nvidia": "NVDA", "tesla": "TSLA", "netflix": "NFLX", "amd": "AMD", "intel": "INTC",
          "s&p": "^GSPC", "s&p 500": "^GSPC", "sp500": "^GSPC", "nasdaq": "^IXIC", "dow": "^DJI", "dow jones": "^DJI",
          "bitcoin": "BTC-USD", "btc": "BTC-USD", "ethereum": "ETH-USD", "eth": "ETH-USD", "gold": "GC=F", "oil": "CL=F",
          "spy": "SPY", "qqq": "QQQ", "vix": "^VIX", "gamestop": "GME", "nintendo": "NTDOY", "sony": "SONY",
          "ea": "EA", "electronic arts": "EA", "take two": "TTWO", "take-two": "TTWO", "roblox": "RBLX", "unity": "U",
          "valve": None, "steam": None, "epic": None, "epic games": None, "spotify": "SPOT", "discord": None}


def resolve(name):
    """'apple' / 'AAPL' / 'nvidia corp' -> (symbol, display name) or (None, why)."""
    q = (name or "").strip()
    if not q:
        return None, "no name"
    low = q.lower().strip(" .$")
    if low in COMMON:
        sym = COMMON[low]
        return (sym, q) if sym else (None, f"{q} isn't publicly traded")
    if re.fullmatch(r"\^?[A-Za-z]{1,5}([.-][A-Za-z]{1,3})?|[A-Za-z]{2,5}-USD|[A-Z]{1,3}=F", q.strip("$")) and (q.isupper() or q.startswith("$")):
        return q.strip("$").upper(), q.strip("$").upper()
    try:
        d = _get(Q1 + "/v1/finance/search", {"q": q, "quotesCount": 6, "newsCount": 0, "listsCount": 0}, ttl=86400)
        for it in d.get("quotes") or []:
            if it.get("quoteType") in ("EQUITY", "ETF", "INDEX", "CRYPTOCURRENCY", "MUTUALFUND", "FUTURE") and it.get("symbol"):
                return it["symbol"], it.get("shortname") or it.get("longname") or it["symbol"]
    except Exception as e:
        print(f"[stocks] search {q}: {e}")
    if re.fullmatch(r"[A-Za-z]{1,5}", q):
        return q.upper(), q.upper()
    return None, f"couldn't find a ticker for {q}"


# ------------------------------------------------------------------ data
def chart(sym, rng="5d"):
    r, iv = RANGES.get(rng, RANGES["5d"])
    d = _get(f"{Q1}/v8/finance/chart/{sym}", {"range": r, "interval": iv, "includePrePost": "false"},
             ttl=60 if rng in ("1d", "5d") else 900)
    res = ((d or {}).get("chart") or {}).get("result") or []
    if not res:
        err = ((d or {}).get("chart") or {}).get("error") or {}
        raise RuntimeError(err.get("description") or f"no data for {sym}")
    return res[0]


def quote(sym):
    """The essentials for one symbol, as a dict."""
    c = chart(sym, "5d")
    m = c.get("meta") or {}
    closes = [x for x in (((c.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []) if x is not None]
    price = m.get("regularMarketPrice") or (closes[-1] if closes else None)
    # daily closes, the last one being today's (or the last session's): the one before it is "yesterday"
    prev = closes[-2] if len(closes) >= 2 else (m.get("previousClose") or m.get("chartPreviousClose"))
    chg = (price - prev) if (price is not None and prev) else None
    return {
        "symbol": m.get("symbol") or sym, "name": m.get("longName") or m.get("shortName") or sym,
        "price": price, "prev": prev, "change": chg, "pct": (chg / prev * 100) if (chg is not None and prev) else None,
        "currency": m.get("currency") or "USD", "exchange": m.get("fullExchangeName") or m.get("exchangeName") or "",
        "day_high": m.get("regularMarketDayHigh"), "day_low": m.get("regularMarketDayLow"),
        "high52": m.get("fiftyTwoWeekHigh"), "low52": m.get("fiftyTwoWeekLow"), "volume": m.get("regularMarketVolume"),
        "state": _market_state(m), "time": m.get("regularMarketTime"),
    }


def _market_state(m):
    tp = (m.get("currentTradingPeriod") or {}).get("regular") or {}
    now = time.time()
    if tp.get("start") and tp.get("end"):
        if tp["start"] <= now <= tp["end"]:
            return "open"
        return "closed"
    return ""


def performance(sym, rng):
    c = chart(sym, rng)
    closes = [x for x in (((c.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []) if x is not None]
    if len(closes) < 2:
        return None, closes
    return (closes[-1] - closes[0]) / closes[0] * 100, closes


def news(sym, n=5):
    d = _get(Q1 + "/v1/finance/search", {"q": sym, "quotesCount": 0, "newsCount": n, "listsCount": 0}, ttl=600)
    out = []
    for it in (d.get("news") or [])[:n]:
        t = it.get("providerPublishTime")
        ago = ""
        if t:
            h = (time.time() - t) / 3600
            ago = f"{int(h * 60)}m ago" if h < 1 else f"{int(h)}h ago" if h < 48 else f"{int(h / 24)}d ago"
        out.append({"title": it.get("title", ""), "source": it.get("publisher", ""), "ago": ago, "link": it.get("link", "")})
    return out


def summary(sym):
    """Valuation, earnings date, analyst targets: best effort (needs the crumb, so it fails more often)."""
    d = _with_crumb(f"{Q2}/v10/finance/quoteSummary/{sym}",
                    {"modules": "price,summaryDetail,defaultKeyStatistics,financialData,calendarEvents,assetProfile"})
    r = ((d.get("quoteSummary") or {}).get("result") or [{}])[0]

    def raw(mod, k):
        v = (r.get(mod) or {}).get(k)
        return v.get("raw") if isinstance(v, dict) else v
    earn = ((r.get("calendarEvents") or {}).get("earnings") or {}).get("earningsDate") or []
    when, ts = None, None
    if earn:
        ts = earn[0].get("raw") if isinstance(earn[0], dict) else None
        if ts:
            when = datetime.fromtimestamp(ts, timezone.utc).astimezone().strftime("%a %b %d")
    prof = r.get("assetProfile") or {}
    return {
        "market_cap": raw("price", "marketCap") or raw("summaryDetail", "marketCap"),
        "pe": raw("summaryDetail", "trailingPE"), "fwd_pe": raw("summaryDetail", "forwardPE"),
        "ps": raw("summaryDetail", "priceToSalesTrailing12Months"), "div_yield": raw("summaryDetail", "dividendYield"),
        "beta": raw("summaryDetail", "beta"), "rev_growth": raw("financialData", "revenueGrowth"),
        "margin": raw("financialData", "profitMargins"), "debt_eq": raw("financialData", "debtToEquity"),
        "fcf": raw("financialData", "freeCashflow"), "target": raw("financialData", "targetMeanPrice"),
        "rating": (r.get("financialData") or {}).get("recommendationKey"),
        "analysts": raw("financialData", "numberOfAnalystOpinions"), "earnings": when, "earnings_ts": ts,
        "sector": prof.get("sector"), "industry": prof.get("industry"),
        "about": (prof.get("longBusinessSummary") or "")[:400],
    }


# ------------------------------------------------------------------ watchlist (Settings > Stocks)
def watchlist():
    import os
    raw = os.environ.get("JUNO_STOCKS", "")
    return [s.strip().upper() for s in re.split(r"[,\s]+", raw) if s.strip()][:20]


def _set_watchlist(syms):
    import settings
    import os
    val = ", ".join(dict.fromkeys(s.upper() for s in syms))
    settings.save({"JUNO_STOCKS": val})
    os.environ["JUNO_STOCKS"] = val
    if WATCH is not None:
        WATCH.feed(force=True)


# ------------------------------------------------------------------ what he says
def _line(q):
    cur = q["currency"]
    bits = [f"{q['name']} ({q['symbol']}) {_money(q['price'], cur)}, {_pct(q['pct'])} today"]
    if q.get("state") == "closed":
        bits.append("market closed, last price")
    return ", ".join(bits)


def market():
    out = []
    for sym, name in INDEXES:
        try:
            q = quote(sym)
            out.append(f"{name} {_pct(q['pct'])}" + (f" at {q['price']:,.0f}" if sym != "^VIX" else f" ({q['price']:.1f})"))
        except Exception:
            pass
    return out


def briefing_line():
    """For the morning briefing: the market in one line plus any big movers on the watchlist. '' if nothing."""
    try:
        idx = market()[:3]
        movers = []
        for s in watchlist()[:12]:
            try:
                q = quote(s)
                if q["pct"] is not None and abs(q["pct"]) >= 2:
                    movers.append(f"{q['symbol']} {_pct(q['pct'])}")
            except Exception:
                pass
        if not idx and not movers:
            return ""
        return "; ".join(filter(None, [", ".join(idx), ("watchlist movers: " + ", ".join(movers)) if movers else ""]))
    except Exception as e:
        print(f"[stocks] briefing: {e}")
        return ""


# ------------------------------------------------------------------ paper portfolio: his takes, kept score on
# Pretend positions only, no money anywhere. Every time he (or you) calls one, it's written down with the price and the
# reason, so later you can see whether his opinions actually held up.
def paper_open(sym, side="long", take=""):
    q = quote(sym)
    st = _load()
    book = st.setdefault("paper", [])
    book.append({"sym": q["symbol"], "side": "short" if str(side).lower().startswith(("short", "bear", "down")) else "long",
                 "entry": q["price"], "at": time.time(), "take": (take or "")[:200], "open": True})
    _save(st)
    return q


def paper_close(sym):
    st = _load()
    for p in reversed(st.get("paper", [])):
        if p["sym"] == sym.upper() and p.get("open"):
            q = quote(p["sym"])
            p.update(open=False, exit=q["price"], closed=time.time())
            _save(st)
            return p, _ret(p, q["price"])
    return None, None


def _ret(p, price):
    if not p.get("entry") or price is None:
        return None
    r = (price - p["entry"]) / p["entry"] * 100
    return -r if p["side"] == "short" else r


def paper_report(include_closed=True):
    book = _load().get("paper", [])
    if not book:
        return "No paper calls yet. Say \"paper trade NVDA long because...\" (pretend positions, no money) to start keeping score.", []
    lines, rows, wins, n = [], [], 0, 0
    for p in book:
        price = p.get("exit") if not p.get("open") else None
        if p.get("open"):
            try:
                price = quote(p["sym"])["price"]
            except Exception:
                price = None
        r = _ret(p, price)
        days = int((time.time() - p["at"]) / 86400)
        if r is not None:
            n += 1
            wins += r > 0
        if p.get("open") or include_closed:
            lines.append(f"{p['sym']} {p['side']} from {p['entry']:,.2f} ({days}d{'' if p.get('open') else ', closed'}): "
                         f"{_pct(r)}" + (f". Reason: {p['take']}" if p.get("take") else ""))
            rows.append({"time": _pct(r), "text": f"{p['sym']} {p['side']}" + ("" if p.get("open") else " (closed)")})
    head = f"Paper record: {wins} of {n} calls are right so far." if n else "Paper record:"
    return head + "\n" + "\n".join(lines) + "\n(Pretend positions: no money involved.)", rows


def tool(action="quote", symbols=None, range=None, symbol=None, add=None, remove=None, side=None, take=None):
    """The stocks tool. Returns plain text for Jarvis to turn into speech."""
    a = (action or "quote").lower()
    syms = [s for s in (symbols or []) if s] or ([symbol] if symbol else [])
    try:
        if a == "paper":
            return paper_report()[0]
        if a in ("paper_open", "paper_close"):
            if not syms:
                return "Which stock?"
            out = []
            for s in syms[:4]:
                sym, nm = resolve(s)
                if not sym:
                    out.append(nm)
                    continue
                if a == "paper_open":
                    q = paper_open(sym, side or "long", take or "")
                    out.append(f"Noted on paper: {q['symbol']} {side or 'long'} at {_money(q['price'], q['currency'])}. "
                               "Pretend position, no money; I'll keep score.")
                else:
                    pos, r = paper_close(sym)
                    out.append(f"Closed paper {sym}: {_pct(r)}." if pos else f"No open paper call on {sym}.")
            return " ".join(out)
        if a == "market":
            m = market()
            wl = []
            for s in watchlist()[:10]:
                try:
                    wl.append(_line(quote(s)))
                except Exception:
                    pass
            return ("Markets: " + ("; ".join(m) if m else "couldn't reach the data right now") +
                    (".\nWatchlist: " + "; ".join(wl) if wl else ".\n(Watchlist is empty: they can add tickers.)"))
        if a == "watchlist":
            cur = watchlist()
            if add or remove:
                adds = [resolve(x)[0] for x in (add if isinstance(add, list) else [add]) if x]
                rems = {x.upper() for x in (remove if isinstance(remove, list) else [remove]) if x}
                rems |= {resolve(x)[0] for x in rems if resolve(x)[0]}
                new = [s for s in cur if s not in rems] + [s for s in adds if s and s not in cur]
                _set_watchlist(new)
                return "Watchlist now: " + (", ".join(new) or "empty") + "."
            if not cur:
                return "The watchlist is empty. Add tickers by name or symbol."
            lines = []
            for s in cur:
                try:
                    lines.append(_line(quote(s)))
                except Exception as e:
                    lines.append(f"{s}: no data ({e})")
            return "Watchlist:\n" + "\n".join(lines)
        if not syms:
            return "Which stock? Give a company name or ticker."
        found = []
        for s in syms[:6]:
            sym, nm = resolve(s)
            if not sym:
                found.append((None, nm))
            else:
                found.append((sym, nm))
        bad = [nm for sym, nm in found if not sym]
        good = [sym for sym, _ in found if sym]
        if not good:
            return "; ".join(bad) + "."
        note = (" (" + "; ".join(bad) + ")") if bad else ""
        if a == "quote":
            out = []
            for s in good:
                q = quote(s)
                ln = _line(q)
                if q.get("day_low") and q.get("day_high"):
                    ln += f"; day range {q['day_low']:,.2f} to {q['day_high']:,.2f}"
                if q.get("low52") and q.get("high52"):
                    ln += f"; 52-week {q['low52']:,.2f} to {q['high52']:,.2f}"
                out.append(ln)
            return "\n".join(out) + note + "\n(Prices can be delayed up to 15 minutes.)"
        if a in ("history", "performance"):
            rng = (range or "1mo").lower().replace(" ", "")
            rng = {"week": "5d", "1w": "5d", "month": "1mo", "1m": "1mo", "year": "1y", "6m": "6mo", "3m": "3mo"}.get(rng, rng)
            out = []
            for s in good:
                p, closes = performance(s, rng)
                if p is None:
                    out.append(f"{s}: not enough data for {rng}")
                    continue
                hi, lo = max(closes), min(closes)
                out.append(f"{s} over {rng}: {_pct(p)} (from {closes[0]:,.2f} to {closes[-1]:,.2f}; high {hi:,.2f}, low {lo:,.2f})")
            return "\n".join(out) + note
        if a == "compare":
            rng = (range or "1y").lower()
            out = []
            for s in good:
                q = quote(s)
                p, _ = performance(s, rng)
                ln = f"{q['symbol']} {_money(q['price'], q['currency'])}, today {_pct(q['pct'])}, {rng} {_pct(p)}"
                try:
                    sm = summary(s)
                    ln += (f", market cap {_money(sm['market_cap'], q['currency'])}" if sm.get("market_cap") else "") + \
                          (f", P/E {sm['pe']:.1f}" if sm.get("pe") else "") + \
                          (f", revenue growth {sm['rev_growth'] * 100:.0f}%" if sm.get("rev_growth") is not None else "") + \
                          (f", margin {sm['margin'] * 100:.0f}%" if sm.get("margin") is not None else "")
                except Exception:
                    pass
                out.append(ln)
            return "\n".join(out) + note
        if a == "news":
            out = []
            for s in good[:3]:
                items = news(s, 5)
                q = quote(s)
                out.append(f"{_line(q)}. Recent headlines:" if items else f"{_line(q)}. No recent headlines found.")
                out += [f"- {i['title']} ({i['source']}, {i['ago']})" for i in items]
            return "\n".join(out) + note + ("\nIf the headlines don't explain the move, search the web for why it moved today.")
        if a in ("earnings", "analysis", "fundamentals", "opinion"):
            out = []
            for s in good[:3]:
                q = quote(s)
                ln = [_line(q)]
                try:
                    sm = summary(s)
                except Exception as e:
                    sm = {}
                    ln.append(f"(fundamentals unavailable right now: {e}; web search can fill in)")
                if a == "earnings":
                    ln.append(f"next earnings: {sm.get('earnings') or 'unknown (search the web)'}")
                else:
                    p1, _ = performance(s, "1y")
                    pick = [("sector", sm.get("sector")), ("industry", sm.get("industry")),
                            ("market cap", _money(sm["market_cap"], q["currency"]) if sm.get("market_cap") else None),
                            ("P/E", f"{sm['pe']:.1f}" if sm.get("pe") else None),
                            ("forward P/E", f"{sm['fwd_pe']:.1f}" if sm.get("fwd_pe") else None),
                            ("price/sales", f"{sm['ps']:.1f}" if sm.get("ps") else None),
                            ("revenue growth", f"{sm['rev_growth'] * 100:.0f}%" if sm.get("rev_growth") is not None else None),
                            ("profit margin", f"{sm['margin'] * 100:.0f}%" if sm.get("margin") is not None else None),
                            ("debt/equity", f"{sm['debt_eq']:.0f}" if sm.get("debt_eq") is not None else None),
                            ("free cash flow", _money(sm["fcf"], q["currency"]) if sm.get("fcf") else None),
                            ("dividend yield", f"{sm['div_yield'] * 100:.2f}%" if sm.get("div_yield") else None),
                            ("beta", f"{sm['beta']:.2f}" if sm.get("beta") else None),
                            ("1-year", _pct(p1) if p1 is not None else None),
                            ("52-week range", f"{q['low52']:,.2f} to {q['high52']:,.2f}" if q.get("low52") else None),
                            ("analyst mean target", f"{sm['target']:,.2f}" if sm.get("target") else None),
                            ("analyst consensus", f"{sm['rating']} ({sm.get('analysts')} analysts)" if sm.get("rating") else None),
                            ("next earnings", sm.get("earnings"))]
                    ln.append("; ".join(f"{k} {v}" for k, v in pick if v))
                    if sm.get("about"):
                        ln.append("business: " + sm["about"])
                    try:
                        hd = news(s, 3)
                        if hd:
                            ln.append("headlines: " + " | ".join(i["title"] for i in hd))
                    except Exception:
                        pass
                out.append("\n".join(ln))
            tail = ""
            if a != "earnings":
                tail = ("\n[Give your own read in your voice: the bull case, the bear case, and what you'd watch (earnings, "
                        "margins, valuation vs growth). An opinion is fine ('richly priced', 'I like the balance sheet'); "
                        "telling them to buy, sell or how much is not. Mention once, briefly, that you're not a financial "
                        "advisor. Search the web for anything recent the numbers don't explain.] ")
            return "\n\n".join(out) + note + tail
        return "Unknown stocks action."
    except Exception as e:
        return f"Couldn't get stock data right now ({type(e).__name__}: {e}). Web search can answer instead."


# ------------------------------------------------------------------ background: the widget, and big-move heads-ups
class StockWatch:
    def __init__(self, core):
        self.core = core
        self._stop = threading.Event()
        self._kick = threading.Event()

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="stock-watch").start()
        return self

    def stop(self):
        self._stop.set()
        self._kick.set()

    def feed(self, force=False):
        self._kick.set()

    def _loop(self):
        self._stop.wait(60)
        while not self._stop.is_set():
            wl = watchlist()
            try:
                import livefeed
                import deskwidgets
                if wl and "stocks" in deskwidgets.enabled():
                    livefeed.watch(wl[:8], secs=420)           # the widget ticks live too
            except Exception as e:
                print(f"[stocks] live: {e}")
            rows = []
            for s in wl[:8]:
                try:
                    q = quote(s)
                    rows.append({"sym": q["symbol"], "price": q["price"], "pct": q["pct"], "cur": q["currency"]})
                except Exception:
                    pass
            try:
                self.core.emit({"type": "w_stocks", "rows": rows})
            except Exception:
                pass
            if getattr(config, "STOCK_ALERTS", False):
                self._alerts(rows)
            for job in (self._earnings_eve, self._weekly):
                try:
                    job()
                except Exception as e:
                    print(f"[stocks] {job.__name__}: {e}")
            self._kick.clear()
            self._kick.wait(5 * 60)

    def _say(self, title, line, items):
        self.core.emit({"type": "cards", "cards": [{"title": title, "list": items}]})
        if getattr(self.core, "history", None) is not None:
            self.core.history.add("Stocks", line)
        import gamemode
        import moments
        if not gamemode.playing() and not moments._busy_or_away(self.core, (2, 900)):
            self.core.events.put(("moment", {"line": line, "cards": []}))
            return True
        return False

    def _earnings_eve(self):
        """The evening before a watchlist (or paper) company reports: a heads-up and the offer of what to watch."""
        if not getattr(config, "STOCK_EARNINGS", True) or datetime.now().hour < 17:
            return
        st = _load()
        today = datetime.now().strftime("%Y-%m-%d")
        if st.get("eve_day") == today:
            return
        syms = list(dict.fromkeys(watchlist() + [p["sym"] for p in st.get("paper", []) if p.get("open")]))[:15]
        if not syms:
            return
        tomorrow = (datetime.now().date().toordinal() + 1)
        due = []
        for s in syms:
            try:
                ts = summary(s).get("earnings_ts")
            except Exception:
                continue
            if ts and datetime.fromtimestamp(ts).date().toordinal() == tomorrow:
                due.append(s)
        st = _load()
        st["eve_day"] = today
        _save(st)
        if due:
            line = (f"{' and '.join(due[:3])} {'reports' if len(due) == 1 else 'report'} earnings tomorrow. "
                    "Want the rundown on what I'd watch?")
            self._say("Earnings tomorrow", line, [{"time": "tmrw", "text": s} for s in due[:6]])

    def _weekly(self):
        """Sunday evening: how the week went for the market, the watchlist and his paper calls."""
        now = datetime.now()
        if not getattr(config, "STOCKS_WEEKLY", True) or now.weekday() != 6 or not (17 <= now.hour < 22):
            return
        st = _load()
        wk = now.strftime("%G-%V")
        if st.get("weekly") == wk:
            return
        wl = watchlist()
        if not wl and not st.get("paper"):
            return
        moves = []
        for s in wl[:12]:
            try:
                p, _ = performance(s, "5d")
                if p is not None:
                    moves.append((s, p))
            except Exception:
                pass
        try:
            spx, _ = performance("^GSPC", "5d")
        except Exception:
            spx = None
        st = _load()
        st["weekly"] = wk
        _save(st)
        moves.sort(key=lambda m: -m[1])
        bits = []
        if spx is not None:
            bits.append(f"The S&P finished the week {_pct(spx).replace('+', 'up ').replace('-', 'down ')}")
        if moves:
            best, worst = moves[0], moves[-1]
            bits.append(f"best on your watchlist was {best[0]} at {_pct(best[1])}" +
                        (f", worst {worst[0]} at {_pct(worst[1])}" if worst is not best else ""))
        rec, _rows = paper_report(include_closed=False)
        if st.get("paper"):
            bits.append(rec.split("\n")[0].replace("Paper record: ", "on paper, ").rstrip("."))
        if not bits:
            return
        line = "Weekly market recap: " + "; ".join(bits) + "."
        self._say("Your week in markets", line, [{"time": _pct(p), "text": s} for s, p in moves[:6]])

    def _alerts(self, rows):
        st = _load()
        today = datetime.now().strftime("%Y-%m-%d")
        seen = st.get("alerted", {}) if st.get("day") == today else {}
        limit = float(getattr(config, "STOCK_ALERT_PCT", 4))
        big = [r for r in rows if r.get("pct") is not None and abs(r["pct"]) >= limit
               and abs(r["pct"]) >= abs(seen.get(r["sym"], 0)) + limit / 2]
        if not big:
            return
        for r in big:
            seen[r["sym"]] = r["pct"]
        st.update(day=today, alerted=seen)
        _save(st)
        r = max(big, key=lambda r: abs(r["pct"]))
        line = (f"Heads up: {r['sym']} is {'up' if r['pct'] > 0 else 'down'} {abs(r['pct']):.1f} percent today" +
                (f", and {len(big) - 1} more on your watchlist moved big" if len(big) > 1 else "") + ". Want to know why?")
        self._say("Big moves", line, [{"time": _pct(x["pct"]), "text": f"{x['sym']} {_money(x['price'], x.get('cur'))}"}
                                      for x in big[:5]])


WATCH = None


def start(core):
    global WATCH
    if WATCH is None:
        WATCH = StockWatch(core).start()
    return WATCH
