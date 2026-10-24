"""
Apple Music. "Play Blinding Lights on Apple Music", "put on the album After Hours on Apple Music".

Apple has no way for other programs to press play on a specific song on Windows (that needs Apple's paid
developer program and their own web player), so he does the next best thing:
  1. finds the exact song, album or artist with Apple's free public catalog search (no account needed),
  2. opens it straight on that page, in the Apple Music app (if it's installed and accepts links) or on the
     website (music.apple.com). You press play.
Pause, next, previous and volume work through the normal media keys, and "what's playing?" reads what
Windows' media controls report.
"""
import locale
import re
import urllib.parse

import config

SEARCH = "https://itunes.apple.com/search"
WEB = "https://music.apple.com"


def storefront():
    """Two-letter country for the catalog (songs differ a bit by country)."""
    c = (config.COUNTRY or "").strip().lower()
    if re.fullmatch(r"[a-z]{2}", c):
        return c
    try:
        loc = locale.getlocale()[0] or ""
    except Exception:
        loc = ""
    m = re.search(r"[_-]([A-Za-z]{2})\b", loc)
    return m.group(1).lower() if m else "us"


def _kind(query, kind):
    q = (query or "").strip()
    k = (kind or "auto").lower()
    if k == "auto":
        low = q.lower()
        if low.startswith(("the album ", "album ")) or low.endswith(" album"):
            k, q = "album", re.sub(r"^(the )?album |\s+album$", "", q, flags=re.I)
        elif low.startswith(("songs by ", "music by ", "the artist ")):
            k, q = "artist", re.sub(r"^(songs by |music by |the artist )", "", q, flags=re.I)
        elif "playlist" in low:
            k = "playlist"
        else:
            k = "song"
    return k, q.strip()


def find(query, kind="auto"):
    """Returns (item, None) or (None, reason). item: {kind, name, artist, url}."""
    import requests
    k, q = _kind(query, kind)
    if not q:
        return None, "What should I look for?"
    if k == "playlist":                                   # the public search doesn't cover playlists
        return {"kind": "search", "name": q, "artist": "", "url": f"{WEB}/{storefront()}/search?term={urllib.parse.quote(q)}"}, None
    entity = {"song": "song", "album": "album", "artist": "musicArtist"}[k]
    try:
        r = requests.get(SEARCH, params={"term": q, "entity": entity, "limit": 5, "country": storefront()}, timeout=10)
        results = r.json().get("results", []) if r.ok else []
    except Exception as e:
        return None, f"Apple's catalog didn't answer ({type(e).__name__})."
    if not results:
        return None, f"Couldn't find {q} on Apple Music."
    x = results[0]
    if k == "song":
        return {"kind": "song", "name": x.get("trackName", q), "artist": x.get("artistName", ""), "url": x.get("trackViewUrl")}, None
    if k == "album":
        return {"kind": "album", "name": x.get("collectionName", q), "artist": x.get("artistName", ""), "url": x.get("collectionViewUrl")}, None
    return {"kind": "artist", "name": x.get("artistName", q), "artist": "", "url": x.get("artistLinkUrl")}, None


def app_installed():
    import tools
    try:
        return bool(tools._best_match("apple music", tools._start_apps().keys()))
    except Exception:
        return False


def _app_takes_links():
    """Does something on this PC handle music:// links (the Apple Music app does when it registers them)?"""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "music") as k:
            winreg.QueryValueEx(k, "URL Protocol")
        return True
    except Exception:
        return False


def _desc(item):
    if item["kind"] == "search":
        return f"Apple Music results for {item['name']}"
    return f"{item['name']}" + (f" by {item['artist']}" if item.get("artist") else "")


def play(query, kind="auto", where="auto"):
    """The tool's main action: find it, open it where the user wants. Returns a sentence for Claude."""
    import tools
    w = (where or "auto").lower()
    if w == "auto":
        pref = (config.APPLE_MUSIC_DEFAULT or "auto").lower()
        w = pref if pref in ("web", "app") else ("app" if app_installed() else "web")
    item, err = find(query, kind)
    if err:
        return err
    url = (item["url"] or "").replace("&uo=4", "").replace("?uo=4", "")
    if w == "app":
        if not app_installed():
            return "The Apple Music app isn't installed (it's free in the Microsoft Store). Say 'on the web' to use the website."
        if _app_takes_links() and url:
            tools.open_url("music://" + url.split("://", 1)[-1], front=True)
            return f"Opened {_desc(item)} in the Apple Music app; the user presses play. Don't retry or switch services."
        tools.open_app("apple music", front=True)
        return (f"Opened the Apple Music app, but it doesn't accept links on this PC, so it can't jump to {_desc(item)}: "
                "tell the user to search for it there, or offer the website.")
    tools.open_url(url, front=True)
    return f"Opened {_desc(item)} on music.apple.com; the user presses play (signed in to Apple Music). Don't retry or switch services."


def now_playing():
    import netflix
    for s in netflix.media_sessions():
        if "applemusic" in s["app"].lower().replace(" ", "") or "itunes" in s["app"].lower():
            if not s["title"]:
                return "Apple Music is open, but it isn't saying what's on."
            return ("Playing: " if s["playing"] else "Paused on: ") + s["title"] + (f" by {s['artist']}" if s["artist"] else "") + "."
    return "Apple Music isn't playing anything I can see."
