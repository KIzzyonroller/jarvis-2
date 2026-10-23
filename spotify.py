"""
Real Spotify control through Spotify's official Web API.

"Play Blinding Lights", "play my gym playlist", "queue some Daft Punk",
"what's playing", "like this song", "shuffle on"...

One-time setup (5 minutes; since February 2026 the app owner needs Spotify Premium):
  1. developer.spotify.com/dashboard -> Create app. Any name. Redirect URI:
         http://127.0.0.1:8765/callback
     Tick "Web API". Save.
  2. Copy the Client ID into .env as SPOTIFY_CLIENT_ID=...
  3. First time you ask him to play something, your browser opens and asks
     you to allow it. After that it just works (it remembers the login).

Spotify only lets apps CONTROL playback on Premium accounts. Without the setup,
he opens a Spotify search in the app instead.
No password is ever seen by Jarvis: you log in on Spotify's own page.
"""
import base64
import hashlib
import json
import os
import re
import secrets
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import config

API = "https://api.spotify.com/v1"
AUTH = "https://accounts.spotify.com/authorize"
TOKEN = "https://accounts.spotify.com/api/token"
REDIRECT = "http://127.0.0.1:8765/callback"
SCOPES = ("user-read-playback-state user-modify-playback-state user-read-currently-playing "
          "user-library-read user-library-modify playlist-read-private playlist-read-collaborative")


class SpotifyError(Exception):
    pass


class Spotify:
    def __init__(self):
        self.last_item = None
        self.client_id = config.SPOTIFY_CLIENT_ID
        self.path = config.JARVIS_DIR / "spotify_token.json"
        self.tok = None
        self.lock = threading.Lock()
        try:
            self.tok = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self.tok = None

    @property
    def configured(self):
        return bool(self.client_id)

    # ------------------------------------------------------------------ auth (PKCE: no client secret needed)
    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.tok), encoding="utf-8")

    def _token_request(self, data):
        import requests
        r = requests.post(TOKEN, data={**data, "client_id": self.client_id}, timeout=15)
        if r.status_code != 200:
            raise SpotifyError(f"Spotify login failed ({r.status_code}): {r.text[:200]}")
        t = r.json()
        t["expires_at"] = time.time() + int(t.get("expires_in", 3600)) - 60
        if "refresh_token" not in t and self.tok:
            t["refresh_token"] = self.tok.get("refresh_token")
        self.tok = t
        self._save()

    def login(self, timeout=180):
        """Opens Spotify's login page in the browser and waits for the redirect."""
        verifier = base64.urlsafe_b64encode(os.urandom(48)).rstrip(b"=").decode()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        state = secrets.token_urlsafe(16)
        box = {}

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                if q.get("state", [None])[0] == state:
                    box["code"] = q.get("code", [None])[0]
                    box["error"] = q.get("error", [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                msg = "Spotify connected. You can close this tab." if box.get("code") else "Spotify login didn't work."
                self.wfile.write(f"<html><body style='font:20px sans-serif;background:#03070c;color:#62d6ff;"
                                 f"padding:40px'>{msg}</body></html>".encode())

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 8765), H)
        srv.timeout = 1
        url = AUTH + "?" + urllib.parse.urlencode({
            "client_id": self.client_id, "response_type": "code", "redirect_uri": REDIRECT, "scope": SCOPES,
            "state": state, "code_challenge_method": "S256", "code_challenge": challenge})
        import webbrowser
        webbrowser.open(url)
        end = time.time() + timeout
        try:
            while time.time() < end and "code" not in box and "error" not in box:
                srv.handle_request()
        finally:
            srv.server_close()
        if not box.get("code"):
            raise SpotifyError("Spotify login was cancelled or timed out.")
        self._token_request({"grant_type": "authorization_code", "code": box["code"], "redirect_uri": REDIRECT,
                             "code_verifier": verifier})

    def _access(self):
        with self.lock:
            if not self.tok:
                self.login()
            elif time.time() > self.tok.get("expires_at", 0):
                self._token_request({"grant_type": "refresh_token", "refresh_token": self.tok["refresh_token"]})
            return self.tok["access_token"]

    def call(self, method, path, params=None, body=None, retry=True):
        import requests
        r = requests.request(method, API + path, params=params, json=body, timeout=15,
                             headers={"Authorization": f"Bearer {self._access()}"})
        if r.status_code == 401 and retry:
            self.tok["expires_at"] = 0
            return self.call(method, path, params, body, retry=False)
        if r.status_code == 204 or not r.content:
            return {}
        try:
            data = r.json()
        except ValueError:
            data = {}
        if r.status_code >= 400:
            reason = (data.get("error") or {}).get("reason") or (data.get("error") or {}).get("message") or r.text[:120]
            raise SpotifyError(f"{r.status_code}:{reason}")
        return data

    # ------------------------------------------------------------------ helpers
    def devices(self):
        return self.call("GET", "/me/player/devices").get("devices", [])

    @staticmethod
    def _this_pc(devs):
        """Spotify on THIS computer (Spotify names it after the PC), else any computer that can be controlled."""
        import socket
        me = socket.gethostname().lower()
        ok = [d for d in devs if not d.get("is_restricted")]
        return ([d for d in ok if (d.get("name") or "").lower() == me]
                or [d for d in ok if d.get("type") == "Computer"])

    def _device(self, wake):
        """Where to play. This PC first: a phone or speaker that's merely "active" in the background used to win,
        so songs went there and nothing played here."""
        devs = self.devices()
        mine = self._this_pc(devs)
        if mine:
            return mine[0]["id"]
        active = [d for d in devs if d.get("is_active") and not d.get("is_restricted")]
        if not wake:
            return (active or devs or [{}])[0].get("id")
        # Spotify isn't open on this PC: start it and wait for it to show up
        import tools
        tools.open_thing("spotify", kind="app")
        for _ in range(20):
            time.sleep(0.75)
            mine = self._this_pc(self.devices())
            if mine:
                time.sleep(1.0)                     # it registers a moment before it can actually play
                return mine[0]["id"]
        return active[0]["id"] if active else None

    def start(self, dev, item):
        """Play item on dev and CHECK that it's really playing. Spotify often says OK (204) to a device that
        just opened or isn't the active one, and then plays nothing. Returns True once it's playing."""
        body = {"uris": [item["uri"]]} if item.get("type") == "track" else {"context_uri": item["uri"]}
        state = self.call("GET", "/me/player") or {}
        if (state.get("device") or {}).get("id") != dev:
            self.call("PUT", "/me/player", None, {"device_ids": [dev], "play": False})     # make this PC the player
            time.sleep(0.8)
        for attempt in range(2):
            self.call("PUT", "/me/player/play", {"device_id": dev}, body)
            for _ in range(8):
                time.sleep(0.4)
                if self._playing(item):
                    return True
            time.sleep(0.8)                         # didn't take: once more (common right after Spotify opens)
        return False

    def _playing(self, item):
        s = self.call("GET", "/me/player") or {}
        if not s.get("is_playing"):
            return False
        cur = s.get("item") or {}
        ctx = (s.get("context") or {}).get("uri")
        if item.get("type") == "track":
            return cur.get("uri") == item["uri"] or cur.get("name", "").lower() == item.get("name", "").lower()
        return ctx == item["uri"] or bool(cur)

    def search(self, query, kind="track", limit=5):
        res = self.call("GET", "/search", {"q": query, "type": kind, "limit": limit})
        return (res.get(kind + "s") or {}).get("items", [])


def _save_to_library(sp, item):
    """Like a song. Spotify replaced PUT /me/tracks with PUT /me/library (uris) in February 2026, for new apps
    first; older apps still have the old one for now. Try the new one, then the old."""
    uri = item.get("uri") or f"spotify:track:{item['id']}"
    tries = [("/me/library", None, {"uris": [uri]}), ("/me/library", {"uris": uri}, None),
             ("/me/tracks", {"ids": item["id"]}, None)]
    err = None
    for path, params, body in tries:
        try:
            sp.call("PUT", path, params, body)
            return
        except SpotifyError as e:
            err = e
            if not re.match(r"(400|404|405|410)", str(e)):
                raise
    raise err


def _desc(item):
    if not item:
        return ""
    t = item.get("type")
    if t == "track":
        return f"{item['name']} by {', '.join(a['name'] for a in item.get('artists', []))}"
    if t == "playlist":
        return f"the playlist {item['name']}"
    if t == "album":
        return f"the album {item['name']} by {', '.join(a['name'] for a in item.get('artists', []))}"
    return item.get("name", "")


_SP = None


def client():
    global _SP
    if _SP is None:
        _SP = Spotify()
    return _SP


def search_uri(query):
    """spotify:search: link with the query encoded. Spotify registers its link handler on Windows as
    Spotify.exe --protocol-uri=%1 WITHOUT quotes, so a raw space cuts the link short and Spotify only
    searched the first word ("never gonna give you up" -> "never")."""
    q = _clean_query(query)
    return "spotify:search:" + urllib.parse.quote(q, safe="")


LIKED_RE = re.compile(r"^(?:my |all my )?(?:liked|saved|favou?rite) (?:songs|tracks|music)$|^my likes$", re.I)


def _clean_query(query):
    """Undo URL-style encoding Claude sometimes adds itself ("liked+songs", "liked%20songs"). A '+' only
    counts as a space when there are no real spaces, so a song like "1+1" with other words keeps it."""
    q = str(query or "").strip()
    if "+" in q and " " not in q:
        q = q.replace("+", " ")
    return urllib.parse.unquote(q).strip()


def app_link(query):
    """The spotify: link for a request: Liked Songs opens your Liked Songs page, anything else a search."""
    if LIKED_RE.match(_clean_query(query)):
        return "spotify:collection:tracks"
    return search_uri(query)


def _what(query):
    return "your Liked Songs" if app_link(query) == "spotify:collection:tracks" else f"a search for '{_clean_query(query)}'"


def _open_in_app(uri_or_search, what, why):
    """Spotify can't press play for us: open exactly that thing in the Spotify app instead. Never switches
    to another service: if you asked for Spotify, you get Spotify."""
    import tools
    front = not tools.fullscreen_app()
    tools.open_url(uri_or_search, front=front)
    return f"{why}, so I opened {what} in the Spotify app; the user just has to press play. Don't retry or try other services."


def status():
    """'Jarvis, Spotify status': what's set up, and what Spotify can see, in one sentence or two."""
    sp = client()
    if not sp.configured:
        return ("Spotify control isn't set up, so I can only open songs in the app for you to press play. "
                "It needs Premium and a Client ID in the dot env file; the readme has the steps.")
    try:
        me = sp.call("GET", "/me") or {}
        devs = sp.devices()
    except SpotifyError as e:
        return f"Spotify is set up, but it refused me: {e}."
    except Exception as e:
        return f"Spotify is set up, but I couldn't reach it: {type(e).__name__}."
    plan = me.get("product")
    line = f"Logged in as {me.get('display_name') or 'you'}" + (f", on {plan}" if plan else "") + ". "
    if plan and plan != "premium":
        line += "Spotify only lets apps press play on Premium, so I'll open songs for you instead. "
    here = Spotify._this_pc(devs)
    if here:
        line += f"Spotify on this PC is ready ({here[0].get('name')})."
    elif devs:
        line += "Spotify isn't open on this PC; I can see " + ", ".join(d.get("name", "?") for d in devs[:4]) + "."
    else:
        line += "Spotify isn't open anywhere right now; I'll open it when you ask for a song."
    return line


def control(action, query=None, kind="auto", value=None):
    """The Jarvis tool. Returns a short plain-English result."""
    sp = client()
    if not sp.configured:
        if (action or "").lower() in ("play", "queue") and query:
            return _open_in_app(app_link(query), _what(query),
                                "Spotify control isn't set up yet (5-minute setup in the README)")
        return ("Spotify control isn't set up (no SPOTIFY_CLIENT_ID in .env; the README explains the 5-minute setup). "
                "Use media_control for play/pause/next.")
    a = (action or "").lower()
    sp.last_item = None
    try:
        if a == "now_playing":
            cur = sp.call("GET", "/me/player/currently-playing")
            item = cur.get("item")
            if not item:
                return "Nothing's playing on Spotify."
            return ("Playing: " if cur.get("is_playing") else "Paused on: ") + _desc(item) + "."
        if a in ("play", "queue"):
            if not query:
                if a == "play":
                    sp.call("PUT", "/me/player/play", {"device_id": sp._device(True)})
                    return "Resumed."
                return "Queue what?"
            k = (kind or "auto").lower()
            q = query
            if k == "auto":
                low = query.lower()
                if re.search(r"\b(liked|saved) songs\b|\bmy likes\b", low):
                    k = "liked"
                elif "playlist" in low:
                    k, q = "playlist", low.replace("my ", "").replace("playlist", "").strip() or query
                elif low.startswith("the album ") or " album" in low:
                    k, q = "album", low.replace("the album", "").replace("album", "").strip()
                else:
                    k = "track"
            if k == "liked":
                dev = sp._device(True)
                if dev and sp.start(dev, {"type": "playlist", "uri": "spotify:collection:tracks"}):
                    return "Playing your Liked Songs."
                return _open_in_app("spotify:collection:tracks", "your Liked Songs", "Spotify didn't start playing")
            if k == "playlist":
                mine = sp.call("GET", "/me/playlists", {"limit": 50}).get("items", [])
                pick = next((p for p in mine if p and q.lower() in p["name"].lower()), None)
                items = [pick] if pick else sp.search(q, "playlist", 5)
            else:
                items = sp.search(q, "artist" if k == "artist" else k, 5)
            items = [i for i in items if i]
            if not items:
                return f"Couldn't find '{query}' on Spotify."
            item = items[0]
            sp.last_item = item
            if a == "queue":
                if item.get("type") != "track":
                    return "Only songs can be queued."
                sp.call("POST", "/me/player/queue", {"uri": item["uri"], "device_id": sp._device(True)})
                return f"Queued {_desc(item)}."
            if sp.tok and sp.tok.get("premium") is False:          # already know this account can't be controlled
                return _open_in_app(item["uri"], _desc(item), "Spotify only lets apps press play on Premium accounts")
            dev = sp._device(True)
            if not dev:
                return _open_in_app(item["uri"], _desc(item), "Spotify wasn't running and didn't start in time")
            if sp.start(dev, item):
                return f"Playing {_desc(item)}."
            print(f"[spotify] play accepted but nothing started on {dev}; opening it in the app instead")
            return _open_in_app(item["uri"], _desc(item), "Spotify accepted the request but didn't start playing")
        if a in ("pause", "resume", "next", "previous"):
            dev = sp._device(a == "resume")
            path = {"pause": ("PUT", "/me/player/pause"), "resume": ("PUT", "/me/player/play"),
                    "next": ("POST", "/me/player/next"), "previous": ("POST", "/me/player/previous")}[a]
            sp.call(path[0], path[1], {"device_id": dev} if dev else None)
            return {"pause": "Paused.", "resume": "Resumed.", "next": "Skipped.", "previous": "Back one."}[a]
        if a == "like":
            cur = sp.call("GET", "/me/player/currently-playing").get("item")
            if not cur:
                return "Nothing's playing."
            _save_to_library(sp, cur)
            return f"Liked {_desc(cur)}."
        if a == "shuffle":
            on = str(value).lower() not in ("false", "off", "0", "no")
            sp.call("PUT", "/me/player/shuffle", {"state": "true" if on else "false"})
            return "Shuffle on." if on else "Shuffle off."
        if a == "repeat":
            mode = (value or "context").lower()
            mode = {"on": "context", "song": "track", "one": "track", "off": "off"}.get(mode, mode)
            sp.call("PUT", "/me/player/repeat", {"state": mode})
            return f"Repeat {mode}."
        if a == "volume":
            v = max(0, min(100, int(float(value))))
            sp.call("PUT", "/me/player/volume", {"volume_percent": v})
            return f"Spotify volume {v}."
        return "Unknown Spotify action."
    except SpotifyError as e:
        msg = str(e)
        if msg.startswith("403") and re.search(r"regist|allowlist|not.*(added|allowed)", msg, re.I):
            return ("Spotify refused: this Spotify account isn't on the app's user list. In developer.spotify.com, "
                    "open the app > User Management and add the account's name and email (up to 5 people).")
        if msg.startswith("403") and re.search(r"owner|developer", msg, re.I):
            return ("Spotify refused: since February 2026 Spotify's developer apps only work if the account that "
                    "made the app has Premium. Without it, leave SPOTIFY_CLIENT_ID empty and I'll open songs in the app.")
        if "PREMIUM_REQUIRED" in msg or msg.startswith("403"):
            if a in ("play", "queue") and query:
                try:
                    sp.tok["premium"] = False                     # don't ask Spotify again next time
                    sp._save()
                except Exception:
                    pass
                item = sp.last_item
                if item:
                    return _open_in_app(item["uri"], _desc(item), "Spotify only lets apps press play on Premium accounts")
                return _open_in_app(app_link(query), _what(query),
                                    "Spotify only lets apps press play on Premium accounts")
            return "That needs Spotify Premium. Use media_control instead."
        if "NO_ACTIVE_DEVICE" in msg or msg.startswith("404"):
            return "Spotify isn't running anywhere. Open it first (or say play something and I'll start it)."
        return f"Spotify error: {msg}"
    except Exception as e:
        return f"Spotify failed: {type(e).__name__}: {e}"
