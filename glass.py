"""
Glass mode: Jarvis puts things on glass cards floating over your webcam, and you handle them with your hands.

  "Open glass mode."                      a window opens with your camera behind glass
  "Show me the top 5 budget mics."        five cards fly in from his ring at the top
  "Put my calendar for this week up."     one card, centre stage
  "What's on the glass?" / "Clear it."

Your hands (the camera finds them; nothing to wear):
  * Pinch (thumb and index together) on a card and move: drag it. Let go mid-swing to throw it.
  * Quick pinch: bring a card centre stage, or send it back.
  * Pinch one card with both hands and pull apart / push together: bigger / smaller. Twist to tilt it.
  * Throw a card off the screen: gone.
  * Make a fist over a card and hold it: crumple it.
  * Sweep an open hand fast across the screen: clear everything.
No camera, or it's off? The mouse does the same: drag, throw, click, scroll to resize.

How it stays private and safe:
  * The page is served only to this PC (127.0.0.1) with a secret key that changes every time Jarvis starts.
  * The camera picture never leaves your PC: hand tracking runs inside the page (Google's MediaPipe, loaded
    once from a public CDN). Nothing about your hands or camera goes to Jarvis or Claude, only which cards are
    up, which ones you closed and which one you're holding.
  * Cards are text and pictures only. Pictures come from web links, his own screenshots, or image files in
    folders he's allowed to read (never password stores or keys).
"""
import hmac
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from collections import OrderedDict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import config

KEEP = {"state", "persona", "caption", "duo", "voice", "turn_start", "turn_end", "telemetry", "confirm", "confirm_done", "discord", "react"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
MAX_CARDS = 12
MAX_TEXT = 4000
MAX_ITEMS = 12
MAX_IMAGE = 25 * 2**20


def _clean(s, n):
    s = str(s or "").replace("\r", "")
    return s[:n]


class GlassHub:
    def __init__(self, core=None, log=print, port=None, ui_dir=None):
        self.core = core
        self.log = log
        self.port = port or config.GLASS_PORT
        self.ui = Path(ui_dir or (config.RES_DIR / "ui"))
        self.token = secrets.token_urlsafe(18)
        self.lock = threading.RLock()
        self.cv = threading.Condition(self.lock)
        self.cards = OrderedDict()        # id -> card (what's on the glass; the page owns where they are)
        self.images = {}                  # image id -> file path (only files he chose to show)
        self.events = deque(maxlen=600)
        self.seq = 0
        self.next_id = 1
        self.snap = {}                    # last state/persona, for a page that just opened
        self.board = {"cards": [], "at": 0}
        self.last_seen = 0.0
        self.srv = None
        self._voice_t = 0.0
        self.trash = deque(maxlen=8)      # cards you threw away or crumpled, newest last (both palms up brings one back)
        self.files = {}                   # file id -> 3D model path
        self._live = None
        self._restore_saved()

    # ------------------------------------------------------------------ lifecycle
    @property
    def running(self):
        return self.srv is not None

    def url(self):
        return f"http://127.0.0.1:{self.port}/glass?t={self.token}"

    def connected(self, within=8.0):
        return time.time() - self.last_seen < within

    def start(self):
        if self.srv:
            return None
        hub = self
        handler = _make_handler(hub)
        last = None
        for port in [self.port] + [self.port + i for i in range(1, 6)]:
            try:
                srv = _Server(("127.0.0.1", port), handler)
                self.port, self.srv = port, srv
                break
            except OSError as e:
                last = e
        if not self.srv:
            return f"Glass mode couldn't start: ports {self.port} to {self.port + 5} are busy ({last})."
        threading.Thread(target=self.srv.serve_forever, daemon=True, name="glass").start()
        self.log(f"[glass] ready at http://127.0.0.1:{self.port}/glass")
        return None

    def stop(self):
        if self.srv:
            try:
                self.srv.shutdown()
                self.srv.server_close()
            except Exception:
                pass
            self.srv = None

    # ------------------------------------------------------------------ events for the page
    def _push(self, ev):
        with self.cv:
            self.seq += 1
            self.events.append((self.seq, ev))
            self.cv.notify_all()

    def feed(self, ev):
        """Everything the app shows passes through here; the page only wants how he's doing."""
        if self.srv is None:
            return
        t = ev.get("type")
        if t not in KEEP:
            return
        if t == "voice":                                 # his loudness, ~20 a second: 15 is plenty
            now = time.time()
            if now - self._voice_t < 1 / 15:
                return
            self._voice_t = now
        if t in ("state", "persona", "duo"):
            self.snap[t] = ev
        if t == "telemetry":
            if not any(c["kind"] == "stats" for c in self.cards.values()):
                return
            return self._push({k: ev.get(k) for k in ("type", "cpu", "ram", "ram_used", "ram_total", "disk", "down_kbps", "up_kbps")})
        if t == "confirm":                               # her yes/no question, as a card you can pinch
            card, _ = self.put_kind("approval", ev.get("title") or "Approve?", {}, stage=True,
                                    data={"cid": ev.get("id"), "detail": str(ev.get("detail") or "")[:400]})
            return
        if t == "confirm_done":
            for k in [k for k, c in self.cards.items() if c["kind"] == "approval"]:
                self.remove(k)
            return
        if t == "discord":                               # into the feed card, if one is up
            feed = next((c for c in self.cards.values() if c["kind"] == "feed"), None)
            if feed is not None:
                item = {"who": str(ev.get("from") or ev.get("who") or "Discord")[:40], "channel": str(ev.get("channel") or "")[:40],
                        "text": str(ev.get("text") or ev.get("content") or "")[:300], "at": time.time() * 1000}
                feed["data"].setdefault("items", []).insert(0, item)
                del feed["data"]["items"][12:]
                self._push({"type": "update", "id": feed["id"], "data": feed["data"]})
            return
        self._push({k: v for k, v in ev.items() if k in ("type", "state", "key", "name", "text", "v", "on", "who")})

    def events_since(self, since, wait=20.0):
        end = time.time() + wait
        with self.cv:
            while self.seq <= since and time.time() < end:
                self.cv.wait(timeout=max(0.1, end - time.time()))
            return [e for (n, e) in self.events if n > since], self.seq

    def sync(self):
        with self.lock:
            return {"type": "sync", "cards": list(self.cards.values()), "snap": list(self.snap.values()), "seq": self.seq}

    # ------------------------------------------------------------------ what the tool calls
    def _image(self, image):
        """A picture for a card: a web link, 'screenshot', or an image file he's allowed to read."""
        img = str(image or "").strip()
        if not img:
            return None, None
        if re.match(r"(?i)^https?://\S+$", img):
            return img, None
        import tools
        if img.lower() in ("screenshot", "screen", "my screen"):
            if not tools.IS_WINDOWS:
                return None, "Screenshots only work on Windows."
            out = tools.screenshot()
            m = re.search(r"saved to (.+?)\.?$", out)
            if not m:
                return None, out
            p = Path(m.group(1))
        else:
            p = tools._resolve(img, config.HOME)
        if p.suffix.lower() not in IMAGE_EXT:
            return None, "Only pictures (png, jpg, gif, webp, bmp) can go on the glass."
        if not tools._readable(p):
            return None, "That picture is somewhere I'm not allowed to look."
        if not p.is_file():
            return None, f"There's no picture at {p}."
        if p.stat().st_size > MAX_IMAGE:
            return None, "That picture is too big for the glass (over 25 MB)."
        return self.register(p), None

    def register(self, p):
        """A link the page can load this file from (pictures and 3D models he chose to show; nothing else)."""
        iid = secrets.token_urlsafe(8)
        with self.lock:
            if Path(p).suffix.lower() in IMAGE_EXT:
                self.images[iid] = Path(p)
                return f"/img/{iid}?t={self.token}"
            self.files[iid] = Path(p)
            return f"/file/{iid}?t={self.token}"

    def put(self, title="", body="", items=None, image=None, stage=True):
        title = _clean(title, 120).strip()
        body = _clean(body, MAX_TEXT).strip()
        if isinstance(items, str):
            items = [x.strip(" -•\t") for x in items.split("\n") if x.strip()]
        items = [_clean(x, 300).strip() for x in (items or []) if str(x).strip()][:MAX_ITEMS]
        url, err = self._image(image)
        if err:
            return None, err
        if not (title or body or items or url):
            return None, "Nothing to put on the glass: give it a title, text, a list or a picture."
        kind = "image" if url and not (body or items) else "list" if items and not body else "note"
        with self.lock:
            cid = self.next_id
            self.next_id += 1
            card = {"id": cid, "kind": kind, "title": title, "body": body, "items": items, "image": url,
                    "stage": bool(stage), "t": time.time()}
            if stage:
                for c in self.cards.values():
                    c["stage"] = False
            self.cards[cid] = card
            while len(self.cards) > MAX_CARDS:
                held = {c.get("id") for c in self.board.get("cards", []) if c.get("held")}
                old = next((k for k in self.cards if k not in held and k != cid), None)
                if old is None:
                    break
                self.cards.pop(old)
                self._push({"type": "remove", "id": old, "why": "full"})
        self._push({"type": "card", "card": card})
        return card, None

    def put_kind(self, kind, title="", args=None, stage=True, data=None):
        """A richer card (glass_kinds.py): timer, stats, weather, checklist, chart, map, 3D model..."""
        import glass_kinds
        args = dict(args or {})
        if data is None:
            try:
                data = glass_kinds.build(self, self.core, kind, dict(args, title=title))
            except ValueError as e:
                return None, str(e)
            except Exception as e:
                return None, f"Couldn't make that card ({type(e).__name__}: {e})."
        title = _clean(title, 120).strip()
        with self.lock:
            if kind == "sticky":                          # notes stay between sessions
                st = glass_kinds.load()
                st.setdefault("notes", []).append({"title": title, "text": data.get("text", "")})
                glass_kinds.save(st)
            cid = self.next_id
            self.next_id += 1
            card = {"id": cid, "kind": kind, "title": title, "body": "", "items": [], "image": None, "data": data,
                    "args": {k: v for k, v in args.items() if isinstance(v, (str, int, float, list)) and k != "data"},
                    "stage": bool(stage), "t": time.time()}
            if stage:
                for c in self.cards.values():
                    c["stage"] = False
            self.cards[cid] = card
        self._push({"type": "card", "card": card})
        self._ensure_live()
        return card, None

    def _restore_saved(self):
        """Sticky notes and pinned cards come back every time."""
        import glass_kinds
        st = glass_kinds.load()
        for n in st.get("notes", []):
            cid = self.next_id
            self.next_id += 1
            self.cards[cid] = {"id": cid, "kind": "sticky", "title": n.get("title", ""), "body": "", "items": [], "image": None,
                               "data": {"text": n.get("text", "")}, "args": {}, "stage": False, "t": time.time(), "saved": True}
        self._pins = st.get("pins", [])

    def restore_pins(self):
        """Pinned cards rebuilt (live ones get fresh data). Called when the page opens."""
        pins, self._pins = getattr(self, "_pins", []), []
        for p in pins:
            if p.get("kind") == "sticky":                   # sticky notes come back on their own already
                continue
            if p.get("kind") in (None, "note", "list"):
                self.put(p.get("title"), p.get("body"), p.get("items"), None, stage=False)
            else:
                self.put_kind(p["kind"], p.get("title", ""), p.get("args") or {}, stage=False)
            with self.lock:
                last = next(reversed(self.cards))
                self.cards[last]["pinned"] = True

    def pin(self, cid, on):
        import glass_kinds
        with self.lock:
            c = self.cards.get(cid)
            if not c:
                return False, "No such card."
            if c["kind"] in ("image", "photos", "model", "approval"):
                return False, "Pictures, photo stacks and 3D models can't be pinned (their files are only shared for this session)."
            c["pinned"] = bool(on)
            pins = [{"kind": None if x["kind"] in ("note", "list") else x["kind"], "title": x["title"], "body": x["body"],
                     "items": x["items"], "args": x.get("args", {})} for x in self.cards.values() if x.get("pinned")]
        st = glass_kinds.load()
        st["pins"] = pins
        glass_kinds.save(st)
        self._push({"type": "pinned", "id": cid, "on": bool(on)})
        return True, "Pinned: it'll be here next time." if on else "Unpinned."

    def update(self, ref, value=None, max_=None, items=None, text=None):
        """Change a card that's up: a progress bar's value, a checklist's items (ticks kept), a sticky's text."""
        import glass_kinds
        with self.lock:
            c = self._find(ref)
            if c is None:
                return False, "No card like that."
            d = c["data"]
            if c["kind"] == "progress":
                if value is not None:
                    d["value"] = float(value)
                if max_ is not None and float(max_) > 0:
                    d["max"] = float(max_)
            elif c["kind"] == "checklist" and items:
                done = {i["t"]: i["done"] for i in d.get("items", [])}
                d["items"] = [{"t": str(t)[:200], "done": bool(done.get(str(t)[:200]))} for t in items][:20]
                st = glass_kinds.load()
                st.setdefault("lists", {})[(c["title"] or "Checklist").lower()] = d["items"]
                glass_kinds.save(st)
            elif c["kind"] == "sticky" and text:
                d["text"] = str(text)[:600]
            else:
                return False, f"#{c['id']} is a {c['kind']} card: only progress bars, checklists and sticky notes change."
            cid = c["id"]
        self._push({"type": "update", "id": cid, "data": d})
        return True, f"Updated #{cid}."

    def _find(self, ref):
        """A card by id ('3', '#3') or by a bit of its title. Call with the lock held."""
        r = str(ref or "").strip().lower().lstrip("#")
        if r.isdigit():
            return self.cards.get(int(r))
        if not r:                                         # no id: the one up close, else the newest
            return next((c for c in self.cards.values() if c.get("stage")), None) or (next(reversed(self.cards.values())) if self.cards else None)
        return next((c for c in reversed(list(self.cards.values())) if r in (c["title"] or "").lower()), None)

    def restore(self, ref=None):
        """Bring back the last card you threw away."""
        with self.lock:
            if not self.trash:
                return False, "Nothing to bring back."
            card = self.trash.pop()
            cid = self.next_id
            self.next_id += 1
            card = dict(card, id=cid, stage=True, t=time.time())
            for c in self.cards.values():
                c["stage"] = False
            self.cards[cid] = card
        self._push({"type": "card", "card": card})
        return True, ""

    def _ensure_live(self):
        """While a stats or now-playing card is up: GPU numbers and the song, every couple of seconds."""
        if self._live and self._live.is_alive():
            return
        self._live = threading.Thread(target=self._live_loop, daemon=True, name="glass-live")
        self._live.start()

    def _live_loop(self):
        import glass_kinds
        last_np = None
        while self.srv is not None:
            kinds = {c["kind"] for c in list(self.cards.values())}
            if not kinds & {"stats", "nowplaying"}:
                return
            if "stats" in kinds and self.connected():
                g = glass_kinds.gpu()
                if g:
                    self._push(dict(g, type="gpu"))
            if "nowplaying" in kinds:
                np = glass_kinds.nowplaying(self.core)
                key = np and (np["title"], np["artist"], np["playing"])
                if key != last_np or (np and np.get("playing") and int(time.time()) % 10 == 0):
                    last_np = key
                    self._push({"type": "np", "data": np or {}})
            time.sleep(2)

    def remove(self, ref):
        ref = str(ref or "").strip().lower().lstrip("#")
        with self.lock:
            if ref in ("", "all", "everything"):
                gone = list(self.cards)
            elif ref.isdigit():
                gone = [int(ref)] if int(ref) in self.cards else []
            else:
                gone = [k for k, c in self.cards.items() if ref in c["title"].lower()]
            for k in gone:
                self.cards.pop(k, None)
        for k in gone:
            self._push({"type": "remove", "id": k, "why": "jarvis"})
        return gone

    def clear(self):
        with self.lock:
            n = len(self.cards)
            self.cards.clear()
            self.images.clear()
        self._push({"type": "clear"})
        return n

    def page_report(self, data):
        """The page says what's on the glass now (and what the user closed by hand)."""
        self.last_seen = time.time()
        closed = [int(x) for x in (data.get("closed") or []) if str(x).isdigit()]
        with self.lock:
            for k in closed:
                c = self.cards.pop(k, None)
                if c is not None and c["kind"] != "approval":
                    self.trash.append(c)
                    if c["kind"] == "sticky":          # thrown away: the note's done
                        import glass_kinds
                        st = glass_kinds.load()
                        st["notes"] = [n for n in st.get("notes", []) if n.get("text") != c["data"].get("text")]
                        glass_kinds.save(st)
            cards = []
            for c in (data.get("cards") or [])[:MAX_CARDS * 2]:
                try:
                    cid = int(c.get("id"))
                except (TypeError, ValueError):
                    continue
                if cid in self.cards:
                    cards.append({"id": cid, "held": bool(c.get("held")), "stage": bool(c.get("stage")),
                                  "big": bool(c.get("big"))})
                    self.cards[cid]["stage"] = bool(c.get("stage"))
            self.board = {"cards": cards, "at": time.time(), "hands": int(data.get("hands") or 0),
                          "mode": str(data.get("mode") or "")[:20], "pointing": data.get("pointing")}

    def board_text(self):
        with self.lock:
            if not self.cards:
                return "The glass is empty." + ("" if self.connected() else " (Glass mode isn't open.)")
            info = {c["id"]: c for c in self.board.get("cards", [])}
            lines = []
            for cid, c in self.cards.items():
                b = info.get(cid, {})
                tags = [t for t, on in (("centre stage", c.get("stage")), ("the user is holding it", b.get("held")),
                                        ("made bigger", b.get("big")), ("the user is pointing at it", self.board.get("pointing") == cid),
                                        ("pinned", c.get("pinned"))) if on]
                what = c["title"] or (c["items"][0] if c["items"] else c["body"][:60]) or (c.get("data") or {}).get("text", "")[:60] or "a picture"
                lines.append(f"#{cid} {c['kind']}: {what}" + (f" ({', '.join(tags)})" if tags else ""))
            head = "On the glass:" if self.connected() else "On the glass (the window isn't open right now):"
            return head + "\n" + "\n".join(lines)

    def bye(self):
        self._push({"type": "bye"})
        self._off_desktop()

    def game_card(self, name):
        """Game mode noticed a game: put its card (notes + quick timers) up, unless it's already there."""
        with self.lock:
            for c in self.cards.values():
                if c["kind"] == "game" and (c["data"] or {}).get("name", "").lower() == name.lower():
                    return c
        card, err = self.put_kind("game", name, {}, stage=False)
        return card

    def game_update(self, name, data):
        """Notes or timers changed: refresh any card for that game."""
        with self.lock:
            ids = [c["id"] for c in self.cards.values() if c["kind"] == "game" and (c["data"] or {}).get("name", "").lower() == name.lower()]
            for i in ids:
                self.cards[i]["data"] = data
        for i in ids:
            self._push({"type": "update", "id": i, "data": data})

    def game_timer(self, label):
        """Start one of the game card's quick timers by voice."""
        self._push({"type": "game_timer", "label": label})

    def calibrate(self):
        """Start 'line up my hand' (handy on the desktop, where there's no keyboard or mouse to start it)."""
        self._push({"type": "calibrate"})

    # ------------------------------------------------------------------ where it shows: its own window or the desktop
    def _desk(self):
        return getattr(self.core, "desk", None) if self.core is not None else None

    def _off_desktop(self):
        d = self._desk()
        if d is not None and getattr(d, "glass_url", None):
            try:
                d.glass(None)
            except Exception as e:
                self.log(f"[glass] desktop: {e}")

    def on_desktop(self):
        d = self._desk()
        return bool(d is not None and getattr(d, "glass_url", None))

    def open_window(self):
        """Open glass mode where Settings says. Returns 'desktop' if it went on the desktop, else True/False."""
        if config.GLASS_WHERE == "desktop":
            d = self._desk()
            try:
                if d is not None and d.glass(self.url() + "&desk"):
                    return "desktop"
            except Exception as e:
                self.log(f"[glass] couldn't put it on the desktop: {e}")
            self.log("[glass] the living desktop isn't running, so glass mode opens in its own window")
        return self._browser()

    def move(self, where):
        """Settings changed while it's open: move it across (the page that was open says goodbye)."""
        was_desk, live = self.on_desktop(), self.connected()
        if not live and not was_desk:
            return
        if (where == "desktop") == was_desk:
            return
        self._push({"type": "bye"})
        self._off_desktop()
        threading.Timer(0.8, self.open_window).start()

    def desk_fallback(self, why=""):
        """The desktop copy couldn't get the camera: use the normal window instead."""
        self.log(f"[glass] no camera on the desktop ({why or 'refused'}); opening its own window")
        self._off_desktop()
        return self._browser()

    def _browser(self):
        """An app-style window (no tabs or address bar) in Edge or Chrome; the default browser if neither."""
        url = self.url()
        if sys.platform == "win32":
            cands = [shutil.which("msedge"), shutil.which("chrome")]
            for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
                if base:
                    cands += [os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                              os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")]
            for exe in cands:
                if exe and os.path.isfile(exe):
                    try:
                        subprocess.Popen([exe, f"--app={url}", "--window-size=1440,860", "--new-window"],
                                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                        return True
                    except OSError:
                        continue
        import webbrowser
        return webbrowser.open(url)


def _make_handler(hub):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json", extra=None):
            data = body if isinstance(body, bytes) else (json.dumps(body) if ctype == "application/json" else body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype + ("; charset=utf-8" if ("text" in ctype or "json" in ctype) else ""))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", str(len(data)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _ok_host(self):
            # stops other websites from reaching it through a DNS trick: only these exact host names
            host = (self.headers.get("Host") or "").lower()
            return host in (f"127.0.0.1:{hub.port}", f"localhost:{hub.port}")

        def _authed(self, header_only=False):
            q = parse_qs(urlparse(self.path).query).get("t", [""])[0]
            tok = self.headers.get("X-Token") or ("" if header_only else q)
            return bool(tok) and hmac.compare_digest(tok.encode(), hub.token.encode())

        def do_GET(self):
            if self.client_address[0] not in ("127.0.0.1", "::1") or not self._ok_host():
                return self._send(403, {"error": "this PC only"})
            u = urlparse(self.path)
            path = u.path
            if path.startswith("/fonts/"):                # the app's own fonts (no key needed: just fonts)
                name = Path(path).name
                f = hub.ui / "fonts" / name
                if re.fullmatch(r"[\w.-]+\.woff2", name) and f.is_file():
                    return self._send(200, f.read_bytes(), "font/woff2", {"Cache-Control": "max-age=86400"})
                return self._send(404, {"error": "no"})
            if not self._authed():
                if path in ("/", "/glass"):
                    return self._send(403, "<!doctype html><meta charset=utf-8><title>Glass</title><body style='background:"
                                      "#02060b;color:#9fdcef;font:16px sans-serif;padding:40px'>This link is old. Ask "
                                      "Jarvis to open glass mode again.</body>", "text/html")
                return self._send(403, {"error": "key"})
            if path in ("/", "/glass"):
                f = hub.ui / "glass.html"
                return self._send(200, f.read_bytes(), "text/html",
                                  {"Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline' "
                                   "'unsafe-eval' 'wasm-unsafe-eval' blob: https://cdn.jsdelivr.net; connect-src 'self' https://cdn.jsdelivr.net "
                                   "https://storage.googleapis.com; img-src 'self' https: data: blob:; style-src 'self' "
                                   "'unsafe-inline'; font-src 'self'; media-src 'self' blob: mediastream:; worker-src 'self' blob: "
                                   "https://cdn.jsdelivr.net" +
                                   # on the desktop it lives inside her wallpaper page (a file:// page, which CSP can't
                                   # name). Still needs this run's secret key, so no website can frame it.
                                   ("" if "desk" in parse_qs(u.query, keep_blank_values=True) else "; frame-ancestors 'none'"),
                                   "Permissions-Policy": "camera=(self), microphone=()"})
            if path == "/events":
                try:
                    since = int(parse_qs(u.query).get("since", ["-1"])[0])
                except ValueError:
                    since = -1
                hub.last_seen = time.time()
                if since < 0:
                    if getattr(hub, "_pins", None):
                        hub.restore_pins()                 # pinned cards come back when the page opens
                    return self._send(200, {"events": [hub.sync()], "seq": hub.seq})
                evs, seq = hub.events_since(since, wait=15.0)
                hub.last_seen = time.time()
                return self._send(200, {"events": evs, "seq": seq})
            m = re.fullmatch(r"/file/([\w-]{6,20})", path)
            if m:
                p = hub.files.get(m.group(1))
                if not p or not p.is_file():
                    return self._send(404, {"error": "gone"})
                return self._send(200, p.read_bytes(), "model/gltf-binary" if p.suffix.lower() == ".glb" else "model/gltf+json")
            m = re.fullmatch(r"/img/([\w-]{6,20})", path)
            if m:
                p = hub.images.get(m.group(1))
                if not p or not p.is_file():
                    return self._send(404, {"error": "gone"})
                ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
                if not ctype.startswith("image/"):
                    return self._send(403, {"error": "not a picture"})
                return self._send(200, p.read_bytes(), ctype)
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            try:                                           # always read the body, so the connection stays in step
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n) if 0 < n <= 200_000 else b""
            except (ValueError, OSError):
                raw = b""
                n = -1
            if n > 200_000 or n < 0:
                self.close_connection = True
                return self._send(413, {"error": "too big"})
            if self.client_address[0] not in ("127.0.0.1", "::1") or not self._ok_host():
                return self._send(403, {"error": "this PC only"})
            if not self._authed(header_only=True):        # a custom header: other websites can't send one
                return self._send(403, {"error": "key"})
            try:
                data = json.loads(raw or b"{}")
            except ValueError:
                return self._send(400, {"error": "bad json"})
            if urlparse(self.path).path == "/board":
                hub.page_report(data if isinstance(data, dict) else {})
                return self._send(200, {"ok": True})
            if urlparse(self.path).path == "/action":       # you pinched a control on a card
                import glass_kinds
                try:
                    ok, msg = glass_kinds.act(hub, hub.core, data if isinstance(data, dict) else {})
                except Exception as e:
                    ok, msg = False, f"{type(e).__name__}: {e}"
                    print(f"[glass] action failed: {msg}")
                return self._send(200, {"ok": ok, "msg": msg})
            return self._send(404, {"error": "not found"})

        def do_OPTIONS(self):                              # no cross-site access, ever
            self.close_connection = True
            self._send(403, {"error": "no"})
    return H


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):     # a browser hanging up mid-request isn't news
        pass
