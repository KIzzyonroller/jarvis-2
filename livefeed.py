"""
Real-time prices for the desktop: every trade-driven price change, as it happens, for whatever is on screen (a stock
panel he pulled up, your watchlist widget). Green when it ticks up, red when it ticks down.

Source: Yahoo Finance's streaming feed (the one its own website uses for live quotes). Free and keyless, unofficial,
so it can change without notice. What it carries is what Yahoo is allowed to show for free: US stocks in real time
during market hours (Nasdaq-listed and most NYSE names via Cboe), crypto around the clock, some indexes and other
exchanges delayed. Outside market hours US stocks simply don't tick. If the stream can't connect, prices fall back to
asking every 15 seconds.

Uses aiohttp (already installed with the Discord bot) in its own thread; nothing here blocks the rest of him.
"""
import asyncio
import base64
import json
import struct
import threading
import time

URL = "wss://streamer.finance.yahoo.com/?version=2"
ORIGIN = "https://finance.yahoo.com"


# ------------------------------------------------------------------ the feed's messages (protobuf, decoded by hand)
FIELDS = {1: "id", 2: "price", 3: "time", 4: "currency", 5: "exchange", 8: "pct", 9: "volume", 10: "high",
          11: "low", 12: "change", 13: "short_name", 15: "prev"}
FLOATS = {2, 8, 10, 11, 12, 15, 16, 17, 18, 19, 20, 21}
ZIGZAG = {3, 9}


def _varint(b, i):
    out = shift = 0
    while True:
        c = b[i]
        i += 1
        out |= (c & 0x7F) << shift
        if not c & 0x80:
            return out, i
        shift += 7


def decode(raw):
    """One PricingData message -> {"id", "price", "pct", "change", "time" (ms), ...}."""
    b, i, out = raw, 0, {}
    while i < len(b):
        key, i = _varint(b, i)
        f, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _varint(b, i)
            if f in ZIGZAG:
                v = (v >> 1) ^ -(v & 1)
        elif wt == 5:
            v = struct.unpack("<f", b[i:i + 4])[0]
            i += 4
        elif wt == 1:
            v = struct.unpack("<d", b[i:i + 8])[0]
            i += 8
        elif wt == 2:
            n, i = _varint(b, i)
            v = b[i:i + n]
            i += n
            try:
                v = v.decode("utf-8")
            except UnicodeDecodeError:
                v = None
        else:
            break
        if f in FIELDS and v is not None:
            out[FIELDS[f]] = v
    return out


def parse(msg):
    """A frame from the socket: plain base64, or {"type": "pricing", "message": base64} (newer)."""
    data = msg
    if isinstance(msg, str) and msg.lstrip().startswith("{"):
        try:
            j = json.loads(msg)
        except ValueError:
            return None
        data = j.get("message") if j.get("type") in (None, "pricing") else None
        if not data:
            return None
    try:
        return decode(base64.b64decode(data))
    except Exception:
        return None


# ------------------------------------------------------------------ the stream
class Stream:
    """Holds the symbols anyone wants (with an expiry each), keeps one socket open while there are any."""

    def __init__(self, emit):
        self.emit = emit
        self.want = {}                  # SYMBOL -> expiry time (0 = until released)
        self.last = {}                  # SYMBOL -> last price sent
        self.sent_at = {}
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.ok = False                 # the socket is up and talking
        self.loop_thread = threading.Thread(target=self._run, daemon=True, name="live-prices")
        self.loop_thread.start()
        threading.Thread(target=self._fallback, daemon=True, name="live-prices-poll").start()

    def watch(self, syms, secs=0):
        until = time.time() + secs if secs else 0
        with self.lock:
            for s in syms:
                s = s.upper()
                cur = self.want.get(s)
                if cur == 0:
                    continue
                self.want[s] = 0 if until == 0 else max(cur or 0, until)
        self.wake.set()

    def release(self, syms):
        with self.lock:
            for s in syms:
                self.want.pop(s.upper(), None)
        self.wake.set()

    def _symbols(self):
        now = time.time()
        with self.lock:
            for s, t in list(self.want.items()):
                if t and t < now:
                    self.want.pop(s)
            return sorted(self.want)

    def _tick(self, d):
        sym = (d.get("id") or "").upper()
        price = d.get("price")
        if not sym or price is None:
            return
        now = time.time()
        prev = self.last.get(sym)
        if prev is not None and abs(price - prev) < 1e-9 and now - self.sent_at.get(sym, 0) < 5:
            return                                  # same price, nothing to show yet
        if now - self.sent_at.get(sym, 0) < 0.3:   # at most ~3 a second per symbol
            return
        self.last[sym], self.sent_at[sym] = price, now
        ev = {"type": "tick", "sym": sym, "price": round(price, 6), "dir": 0 if prev is None else (1 if price > prev else -1 if price < prev else 0),
              "t": d.get("time") or int(now * 1000)}
        for k in ("pct", "change", "high", "low", "volume"):
            if d.get(k) is not None:
                ev[k] = round(d[k], 6) if isinstance(d[k], float) else d[k]
        try:
            self.emit(ev)
        except Exception as e:
            print(f"[live] {e}")

    # -------------------------------------------------- socket (asyncio, in its own thread)
    def _run(self):
        asyncio.run(self._main())

    async def _main(self):
        backoff = 2
        while True:
            syms = self._symbols()
            if not syms:
                self.ok = False
                await asyncio.get_running_loop().run_in_executor(None, self.wake.wait, 30)
                self.wake.clear()
                continue
            try:
                await self._session()
                backoff = 2
            except Exception as e:
                self.ok = False
                print(f"[live] stream dropped ({type(e).__name__}: {e}); retrying in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(60, backoff * 2)

    async def _session(self):
        import aiohttp
        async with aiohttp.ClientSession() as http:
            async with http.ws_connect(URL, headers={"Origin": ORIGIN, "User-Agent": "Mozilla/5.0"}, heartbeat=25) as ws:
                subbed = set()
                print("[live] stream connected")
                while True:
                    want = set(self._symbols())
                    if not want:
                        if subbed:
                            await ws.send_str(json.dumps({"unsubscribe": sorted(subbed)}))
                        return
                    if want != subbed:
                        if subbed - want:
                            await ws.send_str(json.dumps({"unsubscribe": sorted(subbed - want)}))
                        if want - subbed:
                            await ws.send_str(json.dumps({"subscribe": sorted(want - subbed)}))
                        subbed = want
                    try:
                        msg = await ws.receive(timeout=2)
                    except asyncio.TimeoutError:
                        continue
                    if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                        raise ConnectionError("closed")
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        d = parse(msg.data)
                        if d:
                            self.ok = True
                            self._tick(d)

    # -------------------------------------------------- when the socket can't connect: ask every 15 seconds
    def _fallback(self):
        while True:
            time.sleep(15)
            if self.ok:
                continue
            syms = self._symbols()
            if not syms:
                continue
            import stocks
            for s in syms[:10]:
                try:
                    q = stocks.quote(s)
                    self._tick({"id": q["symbol"], "price": q["price"], "pct": q["pct"], "change": q["change"],
                                "high": q["day_high"], "low": q["day_low"]})
                except Exception:
                    pass


STREAM = None


def start(emit):
    global STREAM
    if STREAM is None:
        STREAM = Stream(emit)
    return STREAM


def watch(syms, secs=0):
    if STREAM is not None and syms:
        STREAM.watch(syms, secs)


def release(syms):
    if STREAM is not None:
        STREAM.release(syms)
