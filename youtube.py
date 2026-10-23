"""
YouTube: find the actual video and start it playing, instead of opening a search page.

"Jarvis, play the Dune Part Two trailer", "play lofi hip hop on YouTube",
"find me videos about sourdough" ... "play the second one", "play it fullscreen".

How it finds the video (no Google account or API key needed):
  1. Reads YouTube's own search results and takes the top real video, skipping ads,
     Shorts, channels, playlists and (unless you asked for one) live streams.
  2. If YouTube changes that page and step 1 stops working, it falls back to yt-dlp,
     a widely used open-source tool that's updated whenever YouTube changes things.
Then it opens youtube.com/watch?v=... in your default browser, which starts playing.
Nothing is downloaded; it's exactly what happens when you click the video yourself.
"""
import json
import re
import threading
import time

SEARCH = "https://www.youtube.com/results"
WATCH = "https://www.youtube.com/watch?v="
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/130.0.0.0 Safari/537.36",
           "Accept-Language": "en-US,en;q=0.9"}
COOKIES = {"CONSENT": "YES+1", "SOCS": "CAI"}          # skips the cookie-consent page some regions get
_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_URL_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})")
_DATA = re.compile(r"(?:var\s+ytInitialData|window\[\"ytInitialData\"\])\s*=\s*")
_LAST = []                                            # last search, for "play the second one"
NOW = {}                                              # what was started last (title, channel, id)
_LOCK = threading.Lock()
ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "last": -1, "top": 1}


class YouTubeError(Exception):
    pass


# ------------------------------------------------------------------ reading YouTube's search page
def _text(x):
    if not isinstance(x, dict):
        return ""
    if "simpleText" in x:
        return x["simpleText"]
    return "".join(r.get("text", "") for r in x.get("runs", []))


def _video(vr):
    badges = json.dumps(vr.get("badges", [])) + json.dumps(vr.get("thumbnailOverlays", []))
    length = _text(vr.get("lengthText"))
    return {"id": vr["videoId"], "title": _text(vr.get("title")).strip(),
            "channel": _text(vr.get("ownerText") or vr.get("longBylineText")).strip(),
            "length": length, "views": _text(vr.get("shortViewCountText") or vr.get("viewCountText")),
            "live": ("LIVE" in badges and not length) or (not length and "watching" in _text(vr.get("viewCountText")))}


def parse_results(html, limit=10):
    """Videos from a YouTube search page, in page order. Pure function (tested without network)."""
    m = _DATA.search(html or "")
    if not m:
        return []
    try:
        data, _ = json.JSONDecoder().raw_decode(html, m.end())
    except ValueError:
        return []
    out, stack = [], [data]
    while stack and len(out) < limit:
        n = stack.pop()
        if isinstance(n, dict):
            vr = n.get("videoRenderer")
            if isinstance(vr, dict) and _ID.match(str(vr.get("videoId", ""))):
                out.append(_video(vr))
                continue
            stack.extend(reversed(list(n.values())))     # reversed + pop = document order
        elif isinstance(n, list):
            stack.extend(reversed(n))
    return out


def _scrape(query, limit):
    import requests
    r = requests.get(SEARCH, params={"search_query": query, "hl": "en"}, headers=HEADERS, cookies=COOKIES,
                     timeout=(3, 6))
    r.raise_for_status()
    return parse_results(r.text, limit)


def _ytdlp(query, limit):
    try:
        import yt_dlp
    except ImportError:
        return []
    class _Quiet:                                      # errors come back to us; don't spray them in the console
        def debug(self, msg): pass
        def info(self, msg): pass
        def warning(self, msg): pass
        def error(self, msg): pass
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "extract_flat": True, "noplaylist": True,
            "logger": _Quiet()}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(f"ytsearch{limit}:{query}", download=False) or {}
    out = []
    for e in info.get("entries") or []:
        vid = e.get("id") or ""
        if not _ID.match(vid):
            continue
        d = e.get("duration")
        length = f"{int(d) // 3600}:{int(d) % 3600 // 60:02d}:{int(d) % 60:02d}" if d and d >= 3600 else (
            f"{int(d) // 60}:{int(d) % 60:02d}" if d else "")
        out.append({"id": vid, "title": e.get("title") or "", "channel": e.get("channel") or e.get("uploader") or "",
                    "length": length, "views": "", "live": e.get("live_status") == "is_live"})
    return out


def search(query, limit=6):
    query = (query or "").strip()
    if not query:
        raise YouTubeError("Search for what?")
    errors = []
    for fn in (_scrape, _ytdlp):
        try:
            res = fn(query, limit)
            if res:
                return res
        except Exception as e:                       # network trouble or a page change: try the next way
            errors.append(f"{fn.__name__}: {type(e).__name__}")
    raise YouTubeError("Couldn't get results from YouTube" + (f" ({'; '.join(errors)})" if errors else "") + ".")


# ------------------------------------------------------------------ playing
def _pick(results, query):
    wants_live = bool(re.search(r"\blive ?stream\b|\blive now\b|\b24/7\b", query or "", re.I))
    for v in results:
        if v["live"] == wants_live:
            return v
    return results[0]


def _fullscreen_when_loaded(title, timeout=12):
    """Press F once the video's page is in front (never types into anything else)."""
    import tools
    end = time.time() + timeout
    words = [w for w in re.findall(r"\w+", title.lower()) if len(w) > 3][:3]
    while time.time() < end:
        time.sleep(0.5)
        try:
            t = (tools._wtitle(tools._fg()) or "").lower()
        except Exception:
            return
        if "youtube" in t and (not words or any(w in t for w in words)):
            time.sleep(1.2)                          # let the player take focus
            try:
                if "youtube" in (tools._wtitle(tools._fg()) or "").lower():
                    import pyautogui
                    pyautogui.press("f")
            except Exception:
                pass
            return


def _describe(v):
    bits = [v["title"]]
    if v["channel"]:
        bits.append(f"by {v['channel']}")
    if v["length"]:
        bits.append(f"({v['length']})")
    elif v["live"]:
        bits.append("(live)")
    return " ".join(bits)


def play(query=None, index=None, video=None, fullscreen=False, front=None):
    import tools
    v = None
    if video:
        m = _URL_ID.search(video) or (re.match(r"^([A-Za-z0-9_-]{11})$", video.strip()))
        if m:
            v = {"id": m.group(1), "title": "", "channel": "", "length": "", "views": "", "live": False}
    if v is None and index is not None:
        with _LOCK:
            last = list(_LAST)
        if not last:
            return "There's no earlier YouTube search to pick from. Search first, or say what to play."
        try:
            i = int(index)
        except (TypeError, ValueError):
            i = ORDINALS.get(str(index).lower(), 1)
        if i == -1:
            i = len(last)
        if not 1 <= i <= len(last):
            return f"There were only {len(last)} results."
        v = last[i - 1]
    if v is None:
        try:
            results = search(query, 6)
        except YouTubeError as e:
            return f"{e} Tell the user YouTube didn't answer; don't open anything else."
        with _LOCK:
            _LAST[:] = results
        v = _pick(results, query)
    if front is None:
        front = not tools.fullscreen_app()           # in a game: let it play behind, don't yank you out
    tools.open_url(WATCH + v["id"], front=bool(front))
    NOW.clear()
    NOW.update(v)
    if fullscreen and front and tools.IS_WINDOWS and v["title"]:
        threading.Thread(target=_fullscreen_when_loaded, args=(v["title"],), daemon=True).start()
    where = "" if front else " It's playing in the background so your game stays in front."
    return (f"Playing {_describe(v)} on YouTube [youtu.be/{v['id']}].{where}" if v["title"]
            else f"Playing that video on YouTube [youtu.be/{v['id']}].{where}")


def short_title(title, words=8):
    """'Dune: Part Two | Official Trailer 3 (HD)' -> 'Dune: Part Two', for saying out loud."""
    t = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", title or "")
    t = re.split(r"\s+[|•]\s+", t)[0].strip(" -")
    w = t.split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def control(action, query=None, index=None, video=None, fullscreen=False):
    """The tool."""
    a = (action or "play").lower()
    if a == "search":
        try:
            results = search(query, 6)
        except YouTubeError as e:
            return str(e)
        with _LOCK:
            _LAST[:] = results
        lines = [f"{i}. {_describe(v)}{', ' + v['views'] if v['views'] else ''}" for i, v in enumerate(results, 1)]
        return "Top YouTube results (say which to play; the user can say 'the second one'):\n" + "\n".join(lines)
    if a == "play":
        return play(query=query, index=index, video=video, fullscreen=bool(fullscreen))
    return "Unknown YouTube action. Use play or search (pause/next work with media_control)."
