"""
Steam: friends online and what they're playing, "what should I play?", wishlist sales, and patch notes for the
games you actually play.

Setup (Settings > Connected apps > Steam):
  * a Steam Web API key: https://steamcommunity.com/dev/apikey (any domain name works, e.g. localhost). Free.
  * your Steam profile: the link to it, your custom URL name, or your 17-digit Steam ID.
  * Your profile's "Game details" must be Public for your library and playtime (Steam > Profile > Edit Profile >
    Privacy Settings). Friends need "Friends list" visible to you.

Without a key, she still knows what's installed on this PC (from Steam's own files) and can read patch notes.
Background checks are slow on purpose (sales twice a day, patch notes every few hours) so Steam never rate-limits you.
Read-only: she never buys, sends messages or changes anything on your account.
"""
import json
import re
import threading
import time
from pathlib import Path

import config

API = "https://api.steampowered.com"
STORE = "https://store.steampowered.com/api"
STATE = "steam.json"
PERSONA = {0: "offline", 1: "online", 2: "busy", 3: "away", 4: "snoozing", 5: "looking to trade", 6: "looking to play"}


def _get(url, params=None, timeout=12):
    import requests
    r = requests.get(url, params=params or {}, timeout=timeout, headers={"User-Agent": "Juno-desktop-assistant"})
    r.raise_for_status()
    return r.json()


def _load():
    try:
        return json.loads((config.JARVIS_DIR / STATE).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(st):
    try:
        (config.JARVIS_DIR / STATE).write_text(json.dumps(st), encoding="utf-8")
    except OSError:
        pass


def ready():
    return bool(config.STEAM_API_KEY and config.STEAM_ID)


def steamid():
    """Your 64-bit Steam ID from whatever was put in Settings (cached)."""
    raw = (config.STEAM_ID or "").strip().rstrip("/")
    if not raw:
        raise RuntimeError("Steam isn't set up: add your Steam profile in Settings > Connected apps > Steam")
    m = re.search(r"(7656\d{13})", raw)
    if m:
        return m.group(1)
    vanity = raw.split("/id/")[-1] if "/id/" in raw else raw
    st = _load()
    if st.get("vanity") == vanity and st.get("sid"):
        return st["sid"]
    if not config.STEAM_API_KEY:
        raise RuntimeError("needs a Steam Web API key to look up a custom profile name")
    r = _get(f"{API}/ISteamUser/ResolveVanityURL/v1/", {"key": config.STEAM_API_KEY, "vanityurl": vanity})["response"]
    if r.get("success") != 1:
        raise RuntimeError(f"Steam doesn't know the profile '{vanity}'")
    st.update(vanity=vanity, sid=r["steamid"])
    _save(st)
    return r["steamid"]


# ------------------------------------------------------------------ friends
def friends():
    sid = steamid()
    fl = _get(f"{API}/ISteamUser/GetFriendList/v1/", {"key": config.STEAM_API_KEY, "steamid": sid, "relationship": "friend"})
    ids = [f["steamid"] for f in fl.get("friendslist", {}).get("friends", [])]
    if not ids:
        return "No friends visible (the friends list may be private)."
    people = []
    for i in range(0, len(ids), 100):
        r = _get(f"{API}/ISteamUser/GetPlayerSummaries/v2/", {"key": config.STEAM_API_KEY, "steamids": ",".join(ids[i:i + 100])})
        people += r.get("response", {}).get("players", [])
    playing = [p for p in people if p.get("gameextrainfo")]
    online = [p for p in people if p.get("personastate", 0) > 0 and not p.get("gameextrainfo")]
    out = []
    if playing:
        out.append("Playing: " + "; ".join(f"{p['personaname']} ({p['gameextrainfo']})" for p in playing))
    if online:
        out.append("Online: " + ", ".join(f"{p['personaname']}" + (f" ({PERSONA.get(p['personastate'])})" if p['personastate'] > 1 else "")
                                          for p in online[:20]))
    return "\n".join(out) or f"All {len(people)} friends are offline."


# ------------------------------------------------------------------ library and "what should I play"
def owned():
    r = _get(f"{API}/IPlayerService/GetOwnedGames/v1/", {"key": config.STEAM_API_KEY, "steamid": steamid(),
                                                         "include_appinfo": 1, "include_played_free_games": 1})
    games = r.get("response", {}).get("games", [])
    if not games:
        raise RuntimeError("your library is hidden: set Game details to Public in Steam's privacy settings")
    return games


def suggest(hours=None):
    """Candidates by kind, for her to pick from with the user's mood in mind."""
    games = owned()
    now = time.time()
    recent = sorted([g for g in games if g.get("playtime_2weeks")], key=lambda g: -g["playtime_2weeks"])[:6]
    forgotten = sorted([g for g in games if g.get("playtime_forever", 0) > 600 and now - g.get("rtime_last_played", 0) > 90 * 86400],
                       key=lambda g: -g["playtime_forever"])[:8]
    backlog = [g for g in games if g.get("playtime_forever", 0) < 60]
    import random
    random.shuffle(backlog)
    installed = {g["appid"] for g in installed_games()}
    tag = lambda g: g["name"] + (" (installed)" if g["appid"] in installed else "")
    out = [f"Library: {len(games)} games, {len(backlog)} barely played."]
    if recent:
        out.append("Lately: " + "; ".join(f"{tag(g)} {g['playtime_2weeks'] / 60:.0f}h in 2 weeks" for g in recent))
    if forgotten:
        out.append("Old favourites not touched in 3+ months: " + "; ".join(f"{tag(g)} ({g['playtime_forever'] / 60:.0f}h total)" for g in forgotten))
    if backlog:
        out.append("Never really played: " + "; ".join(tag(g) for g in backlog[:10]))
    return "\n".join(out) + "\nPick one or two and say why; prefer installed games for 'right now'."


# ------------------------------------------------------------------ what's installed (no key needed)
def _steam_path():
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        return Path(winreg.QueryValueEx(k, "SteamPath")[0])
    except Exception:
        p = Path(r"C:\Program Files (x86)\Steam")
        return p if p.exists() else None


def _vdf_values(text, key):
    return re.findall(r'"%s"\s+"([^"]*)"' % key, text, re.I)


def installed_games():
    """[{appid, name, size, last_played}] from Steam's library files on this PC."""
    root = _steam_path()
    if not root:
        return []
    libs = {root / "steamapps"}
    lf = root / "steamapps" / "libraryfolders.vdf"
    if lf.exists():
        for p in _vdf_values(lf.read_text(encoding="utf-8", errors="replace"), "path"):
            libs.add(Path(p.replace("\\\\", "\\")) / "steamapps")
    out = []
    for lib in libs:
        if not lib.is_dir():
            continue
        for m in lib.glob("appmanifest_*.acf"):
            try:
                t = m.read_text(encoding="utf-8", errors="replace")
                name = (_vdf_values(t, "name") or [m.stem])[0]
                if re.search(r"redistributable|steamworks common|proton|steam linux runtime", name, re.I):
                    continue
                out.append({"appid": int((_vdf_values(t, "appid") or [0])[0]), "name": name,
                            "size": int((_vdf_values(t, "SizeOnDisk") or [0])[0]),
                            "last_played": int((_vdf_values(t, "LastPlayed") or [0])[0])})
            except Exception:
                continue
    return out


def appid_for(name):
    """A game's Steam app id from its name: installed games first, then your library."""
    n = (name or "").lower().strip()
    if n.isdigit():
        return int(n)
    for g in installed_games():
        if n and (n in g["name"].lower() or g["name"].lower() in n):
            return g["appid"]
    if ready():
        for g in owned():
            if n and n in g["name"].lower():
                return g["appid"]
    known = {"dbd": 381210, "dead by daylight": 381210}
    return known.get(n)


# ------------------------------------------------------------------ patch notes
def news(appid, count=3):
    r = _get(f"{API}/ISteamNews/GetNewsForApp/v2/", {"appid": appid, "count": count, "maxlength": 0,
                                                     "feeds": "steam_community_announcements"})
    return r.get("appnews", {}).get("newsitems", [])


def _clean(bb):
    t = re.sub(r"\[/?(?:h\d|b|i|u|list|olist|\*|p|url[^\]]*|img[^\]]*|previewyoutube[^\]]*|table|tr|td|th|hr|strike|spoiler|quote[^\]]*|code)\]", " ", bb or "")
    t = re.sub(r"\{STEAM_CLAN_IMAGE\}\S*", "", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", t)).strip()


def patch_notes(game):
    aid = appid_for(game)
    if not aid:
        return f"I couldn't find '{game}' on Steam."
    items = news(aid, 5)
    upd = [i for i in items if re.search(r"patch|update|hotfix|fix|notes|ptb|chapter|season", i["title"], re.I)] or items
    if not upd:
        return "No recent announcements for that game."
    i = upd[0]
    when = time.strftime("%B %d", time.localtime(i["date"]))
    return (f"{i['title']} ({when}) - {i['url']}\nSummarize what matters to a player (nerfs, buffs, fixes, new stuff); "
            f"give real numbers only if they're in the text:\n" + _clean(i.get("contents"))[:7000])


# ------------------------------------------------------------------ wishlist sales
def wishlist_sales(min_discount=1):
    sid = steamid()
    r = _get(f"{API}/IWishlistService/GetWishlist/v1/", {"steamid": sid, "key": config.STEAM_API_KEY})
    ids = [i["appid"] for i in r.get("response", {}).get("items", [])]
    if not ids:
        return [], 0
    cc = (config.COUNTRY or "US").upper()
    st = _load()
    names = st.setdefault("names", {})
    sales = []
    for i in range(0, len(ids), 40):
        chunk = ids[i:i + 40]
        try:
            prices = _get(f"{STORE}/appdetails", {"appids": ",".join(map(str, chunk)), "cc": cc, "filters": "price_overview"})
        except Exception as e:
            print(f"[steam] prices: {e}")
            continue
        for aid in chunk:
            d = (prices.get(str(aid)) or {}).get("data") or {}
            po = d.get("price_overview") if isinstance(d, dict) else None
            if po and po.get("discount_percent", 0) >= min_discount:
                sales.append({"appid": aid, "pct": po["discount_percent"], "price": po.get("final_formatted"),
                              "was": po.get("initial_formatted")})
        time.sleep(1.5)
    for s in sales:                                      # names only for the ones on sale (one lookup each, cached)
        if str(s["appid"]) not in names:
            try:
                d = _get(f"{STORE}/appdetails", {"appids": s["appid"], "filters": "basic"})
                names[str(s["appid"])] = ((d.get(str(s["appid"])) or {}).get("data") or {}).get("name") or str(s["appid"])
                time.sleep(1)
            except Exception:
                names[str(s["appid"])] = str(s["appid"])
        s["name"] = names[str(s["appid"])]
    _save(st)
    return sorted(sales, key=lambda s: -s["pct"]), len(ids)


def sales_text():
    sales, n = wishlist_sales()
    if not n:
        return "Your wishlist is empty (or private)."
    if not sales:
        return f"Nothing on your wishlist ({n} games) is on sale right now."
    return f"{len(sales)} of {n} wishlist games on sale: " + "; ".join(f"{s['name']} -{s['pct']}% {s['price']} (was {s['was']})" for s in sales[:12])


# ------------------------------------------------------------------ background: sales and patch notes
class SteamWatch:
    def __init__(self, core):
        self.core = core
        self._stop = threading.Event()

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="steam-watch").start()
        return self

    def stop(self):
        self._stop.set()

    def _loop(self):
        self._stop.wait(180)
        while not self._stop.is_set():
            st = _load()
            now = time.time()
            try:
                if config.STEAM_SALE_ALERTS and ready() and now - st.get("sales_at", 0) > 12 * 3600:
                    self._sales()
                if config.PATCH_NOTES and now - st.get("news_at", 0) > 3 * 3600:
                    self._patches()
            except Exception as e:
                print(f"[steam] {e}")
            self._stop.wait(30 * 60)

    def _tell(self, title, line, items):
        self.core.emit({"type": "cards", "cards": [{"title": title, "list": items}]})
        if getattr(self.core, "history", None) is not None:
            self.core.history.add("Steam", line)
        import gamemode
        import moments
        if not gamemode.playing() and not moments._busy_or_away(self.core, (2, 900)):
            self.core.events.put(("moment", {"line": line, "cards": []}))

    def _sales(self):
        sales, _ = wishlist_sales(min_discount=config.STEAM_SALE_MIN)
        st = _load()
        seen = st.get("seen_sales", {})
        new = [s for s in sales if seen.get(str(s["appid"])) != s["pct"]]
        st["seen_sales"] = {str(s["appid"]): s["pct"] for s in sales}
        st["sales_at"] = time.time()
        _save(st)
        if new:
            top = new[:4]
            line = (f"{top[0]['name']} from your wishlist is {top[0]['pct']} percent off" +
                    (f", and {len(new) - 1} more" if len(new) > 1 else "") + ".")
            self._tell("Wishlist sales", line, [{"time": f"-{s['pct']}%", "text": f"{s['name']} {s['price']}"} for s in top])

    def _patches(self):
        st = _load()
        seen = st.setdefault("seen_news", {})
        week = time.time() - 14 * 86400
        games = [g for g in installed_games() if g["last_played"] > week]
        found = []
        for g in sorted(games, key=lambda g: -g["last_played"])[:8]:
            try:
                items = news(g["appid"], 3)
            except Exception:
                continue
            for i in items:
                if i["date"] < time.time() - 3 * 86400 or not re.search(r"patch|update|hotfix|notes|chapter", i["title"], re.I):
                    continue
                if seen.get(str(g["appid"])) == i["gid"]:
                    break
                seen[str(g["appid"])] = i["gid"]
                found.append((g["name"], i["title"]))
                break
            time.sleep(1)
        st["news_at"] = time.time()
        _save(st)
        if found:
            name, title = found[0]
            line = f"{name} just got an update: {title}. Want the patch notes summed up?"
            self._tell("Game updates", line, [{"time": n, "text": t} for n, t in found])


WATCH = None


def start(core):
    global WATCH
    if WATCH is None:
        WATCH = SteamWatch(core).start()
    return WATCH
