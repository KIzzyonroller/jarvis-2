"""
Games, part two:

  * Post-match stats. For Steam games that publish stats (Dead by Daylight, CS2, and many more), he takes a snapshot
    of your Steam stats when the game opens and again when it closes (or when you ask "how did that go?"), and tells
    you what changed: escapes, generators, kills, wins... Needs your Steam key and ID (Settings > Connected apps)
    and Steam's "Game details" set to public.
    Valorant isn't on Steam: with a free HenrikDev key (api.henrikdev.xyz) and your Riot ID he reads your last match
    (agent, map, K/D/A, win or loss).
  * "Clip that": presses your recorder's save-replay shortcut (NVIDIA Instant Replay: Alt+F10, or Xbox Game Bar:
    Win+Alt+G), then checks a new video actually appeared. Only the overlay's own shortcut, nothing else in the game.
  * Sales radar: once a week, Steam games on sale that are like the ones you actually play (by their Steam tags),
    leaving out games you own.
  * Monthly report: on the 1st (or "how was my gaming month?"), hours per game, sessions, longest session, the wins
    and losses you told him about, and the change from the month before.
"""
import calendar
import json
import os
import threading
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import config

CORE = None
SNAP = {}                 # appid -> {"t", "stats": {name: value}}
STATE_FILE = "games_extra.json"


def _st():
    try:
        return json.loads((config.JARVIS_DIR / STATE_FILE).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_st(s):
    (config.JARVIS_DIR / STATE_FILE).write_text(json.dumps(s, indent=1), encoding="utf-8")


# ================================================================== Steam stats before / after
def _stats(appid):
    import steam
    if not steam.ready():
        raise RuntimeError("needs your Steam key and ID (Settings > Connected apps)")
    r = steam._get(f"{steam.API}/ISteamUserStats/GetUserStatsForGame/v2/",
                   {"key": config.STEAM_API_KEY, "steamid": steam.steamid(), "appid": appid})
    stats = (r.get("playerstats") or {}).get("stats") or []
    return {s["name"]: s.get("value", 0) for s in stats}


def _names(appid):
    """Steam's human names for stat keys ('DBD_Escape' -> 'Escapes'), cached."""
    st = _st()
    cache = st.setdefault("statnames", {})
    if str(appid) in cache:
        return cache[str(appid)]
    import steam
    try:
        r = steam._get(f"{steam.API}/ISteamUserStats/GetSchemaForGame/v2/", {"key": config.STEAM_API_KEY, "appid": appid})
        names = {s["name"]: s.get("displayName") or s["name"] for s in
                 (((r.get("game") or {}).get("availableGameStats") or {}).get("stats") or [])}
    except Exception:
        names = {}
    cache[str(appid)] = names
    _save_st(st)
    return names


def snapshot(game):
    import steam
    try:
        app = steam.appid_for(game)
        if not app:
            return
        SNAP[app] = {"t": time.time(), "game": game, "stats": _stats(app)}
        print(f"[stats] snapshot of {game}: {len(SNAP[app]['stats'])} stats")
    except Exception as e:
        print(f"[stats] {game}: {e}")


def _pretty(key, names):
    n = names.get(key) or key
    for pre in ("DBD_", "STAT_", "stat_", "total_", "TOTAL_"):
        if n.startswith(pre):
            n = n[len(pre):]
    return n.replace("_", " ").strip()


def diff(game):
    """What changed since the snapshot: [(name, +n)] biggest first, or raises with a plain reason."""
    import steam
    app = steam.appid_for(game)
    if not app:
        raise RuntimeError(f"{game} isn't a Steam game I can find")
    before = SNAP.get(app)
    if not before:
        raise RuntimeError("I didn't get a snapshot when it started (Steam key missing, or the game started before I did)")
    now = _stats(app)
    names = _names(app)
    ch = [(_pretty(k, names), v - before["stats"].get(k, 0)) for k, v in now.items()
          if isinstance(v, (int, float)) and v != before["stats"].get(k, 0)]
    ch = [(n, d) for n, d in ch if d and "time" not in n.lower() and "seconds" not in n.lower()]
    return sorted(ch, key=lambda x: -abs(x[1]))[:10]


def session_report(game, spoken=True):
    try:
        ch = diff(game)
    except Exception as e:
        return f"No post-match stats for {game}: {e}."
    if not ch:
        return (f"Steam hasn't recorded any new stats for {game} since you started (some games only update after "
                f"the match, or don't publish stats).")
    try:
        import pulls
        pulls.pull("briefing", {"game": f"{game}: this session", "friends": [],
                                "queue": [f"{n}: {'+' if d > 0 else ''}{d:g}" for n, d in ch]}, id="poststats",
                   title="Post-match", ttl=240, auto=False)
    except Exception:
        pass
    return f"{game} this session: " + ", ".join(f"{n} {'+' if d > 0 else ''}{d:g}" for n, d in ch[:6]) + "."


# ================================================================== Valorant (HenrikDev)
def valorant_last():
    key = os.environ.get("JARVIS_HENRIK_KEY", "").strip()
    rid = os.environ.get("JARVIS_RIOT_ID", "").strip()
    region = os.environ.get("JARVIS_RIOT_REGION", "na").strip().lower() or "na"
    if not key or "#" not in rid:
        return ("Valorant stats need a free HenrikDev API key (api.henrikdev.xyz, sign in with Discord) and your Riot ID "
                "like Name#TAG, in Settings > Games and alerts.")
    name, tag = rid.split("#", 1)
    import requests
    import urllib.parse as up
    url = f"https://api.henrikdev.xyz/valorant/v3/matches/{region}/{up.quote(name)}/{up.quote(tag)}"
    r = requests.get(url, params={"size": 1}, headers={"Authorization": key}, timeout=12)
    if r.status_code == 401 or r.status_code == 403:
        return "HenrikDev turned the key down; check it in Settings."
    if r.status_code == 404:
        return f"HenrikDev doesn't know {rid} in region {region.upper()}."
    r.raise_for_status()
    data = (r.json().get("data") or [])
    if not data:
        return "No recent Valorant matches found."
    m = data[0]
    meta = m.get("metadata") or {}
    me = None
    for p in ((m.get("players") or {}).get("all_players") or []):
        if p.get("name", "").lower() == name.lower() and p.get("tag", "").lower() == tag.lower():
            me = p
            break
    if not me:
        return "Found the match but not you in it (Riot ID changed?)."
    st = me.get("stats") or {}
    team = (me.get("team") or "").lower()
    teams = m.get("teams") or {}
    won = (teams.get(team) or {}).get("has_won")
    rounds = (teams.get(team) or {}).get("rounds_won"), (teams.get(team) or {}).get("rounds_lost")
    k, d, a = st.get("kills", 0), st.get("deaths", 0), st.get("assists", 0)
    line = (f"Last Valorant match: {'won' if won else 'lost' if won is False else 'played'} on {meta.get('map', '?')}"
            + (f" {rounds[0]}-{rounds[1]}" if None not in rounds else "") +
            f" as {me.get('character', '?')}, {k}/{d}/{a}" + (f", {st.get('headshots', 0)} headshots" if st.get("headshots") else "") + ".")
    try:
        import gamemode
        if won is not None and gamemode.WATCH:
            gamemode.WATCH.result("win" if won else "loss")
    except Exception:
        pass
    return line


# ================================================================== clip that
def _newest_video(since):
    roots = [config.HOME / "Videos", config.HOME / "Videos" / "Captures", config.HOME / "Videos" / "NVIDIA"]
    extra = os.environ.get("JARVIS_CLIP_FOLDER", "")
    if extra:
        roots.insert(0, Path(extra))
    best = None
    for r in roots:
        if not r.exists():
            continue
        for p in r.rglob("*.mp4"):
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            if m >= since and (best is None or m > best[0]):
                best = (m, p)
    return best[1] if best else None


def _recorder():
    import psutil
    names = {(p.info.get("name") or "").lower() for p in psutil.process_iter(["name"])}
    if any("nvidia overlay" in n or n == "nvcontainer.exe" for n in names) or "nvidia share.exe" in names:
        return "nvidia"
    if "gamebar.exe" in names or "gamebarftserver.exe" in names:
        return "gamebar"
    return "gamebar"                 # Game Bar ships with Windows; its shortcut works even when it isn't running yet


def clip():
    """Save the last moments with the recorder's own shortcut, then check a file appeared."""
    import pyautogui
    import tools
    rec = os.environ.get("JARVIS_CLIP_WITH", "auto").lower()
    rec = _recorder() if rec == "auto" else rec
    keys = {"nvidia": ("alt", "f10"), "gamebar": ("win", "alt", "g")}.get(rec, ("alt", "f10"))
    custom = os.environ.get("JARVIS_CLIP_KEY", "").strip()
    if custom:
        keys = tuple(k.strip().lower() for k in custom.split("+"))
    t0 = time.time() - 2
    try:
        pyautogui.hotkey(*keys, interval=0.03)
    finally:
        for k in keys:
            try:
                pyautogui.keyUp(k)
            except Exception:
                pass
        tools.release_modifiers()          # never leave Alt or Win held (see 1.0.35)
    for _ in range(20):
        time.sleep(1)
        p = _newest_video(t0)
        if p:
            return True, f"Clipped. Saved as {p.name}."
    who = "NVIDIA Instant Replay" if rec == "nvidia" else "Xbox Game Bar"
    return False, (f"I pressed {'+'.join(k.title() for k in keys)} for {who}, but no new video showed up in Videos. "
                   f"Is {'Instant Replay switched on in the NVIDIA overlay (Alt+Z)' if rec == 'nvidia' else 'background recording on in Game Bar settings'}?")


# ================================================================== sales radar
def _tags(appid):
    import steam
    st = _st()
    cache = st.setdefault("tags", {})
    if str(appid) in cache:
        return cache[str(appid)]
    try:
        d = steam._get("https://steamspy.com/api.php", {"request": "appdetails", "appid": appid}, timeout=15)
        tags = d.get("tags") or {}
        top = [t for t, _ in sorted(tags.items(), key=lambda x: -x[1])[:10]] if isinstance(tags, dict) else []
    except Exception:
        top = []
    cache[str(appid)] = top
    _save_st(st)
    return top


def radar(limit=6):
    """[{name, pct, price, why}] on sale now and like what you play. Raises with a plain reason."""
    import steam
    games = steam.owned()
    owned_ids = {g["appid"] for g in games}
    top = sorted(games, key=lambda g: -(g.get("playtime_2weeks", 0) * 5 + g.get("playtime_forever", 0)))[:6]
    taste = Counter()
    for g in top:
        for i, t in enumerate(_tags(g["appid"])):
            taste[t] += 10 - i
        time.sleep(0.3)
    if not taste:
        raise RuntimeError("couldn't read the tags of your most-played games")
    cc = (config.COUNTRY or "US").upper()
    fc = steam._get(f"{steam.STORE.replace('/api', '')}/api/featuredcategories", {"cc": cc, "l": "english"})
    items = (fc.get("specials") or {}).get("items") or []
    for k in ("top_sellers", "new_releases"):
        items += [i for i in (fc.get(k) or {}).get("items") or [] if i.get("discounted")]
    seen, out = set(), []
    for it in items:
        aid = it.get("id")
        if not aid or aid in seen or aid in owned_ids or not it.get("discount_percent"):
            continue
        seen.add(aid)
        tags = _tags(aid)
        score = sum(taste.get(t, 0) for t in tags)
        common = [t for t in tags if t in taste][:3]
        if score and common:
            out.append({"name": it.get("name"), "pct": it["discount_percent"],
                        "price": f"{it.get('final_price', 0) / 100:.2f} {it.get('currency', '')}".strip(),
                        "why": ", ".join(common), "score": score, "appid": aid})
        time.sleep(0.2)
    return sorted(out, key=lambda x: -x["score"])[:limit]


def radar_text(show=True):
    try:
        deals = radar()
    except Exception as e:
        return f"Couldn't check sales: {e}."
    if not deals:
        return "Nothing on sale right now that's really your kind of game."
    if show:
        try:
            import pulls
            pulls.pull("briefing", {"game": "On sale, your kind of game", "friends": [],
                                    "queue": [f"-{d['pct']}% {d['name']} ({d['price']}): {d['why']}" for d in deals]},
                       id="radar", title="Sales radar", ttl=300, auto=False)
        except Exception:
            pass
    return "On sale and like what you play: " + "; ".join(f"{d['name']} {d['pct']}% off ({d['price']}), {d['why']}" for d in deals) + "."


# ================================================================== monthly report
def month_report(year=None, month=None, show=True):
    import gamemode
    today = date.today()
    if not year:
        first = today.replace(day=1)
        prev = first - timedelta(days=1)
        year, month = (today.year, today.month) if today.day > 3 else (prev.year, prev.month)
    rows = gamemode._read_play()

    def stats(y, m):
        a = datetime(y, m, 1).timestamp()
        b = datetime(y + (m == 12), m % 12 + 1, 1).timestamp()
        mins, sessions, longest, w, l = defaultdict(float), Counter(), (0, ""), 0, 0
        days = Counter()
        for r in rows:
            if not a <= r["t"] < b:
                continue
            if "minutes" in r:
                mins[r["game"]] += r["minutes"]
                sessions[r["game"]] += 1
                days[datetime.fromtimestamp(r.get("start", r["t"])).strftime("%A")] += r["minutes"]
                if r["minutes"] > longest[0]:
                    longest = (r["minutes"], r["game"])
            elif r.get("result") == "win":
                w += 1
            elif r.get("result") == "loss":
                l += 1
        return mins, sessions, longest, w, l, days
    mins, sessions, longest, w, l, days = stats(year, month)
    py, pm = (year - 1, 12) if month == 1 else (year, month - 1)
    pmins = stats(py, pm)[0]
    total, ptotal = sum(mins.values()), sum(pmins.values())
    label = f"{calendar.month_name[month]} {year}"
    if not total:
        return f"No games logged in {label}."
    top = sorted(mins.items(), key=lambda x: -x[1])
    change = ((total - ptotal) / ptotal * 100) if ptotal else None
    lines = [f"{label}: {total / 60:.1f} hours of games"
             + (f" ({'+' if change >= 0 else ''}{change:.0f}% vs {calendar.month_name[pm]})" if change is not None else "") + "."]
    lines.append("Most played: " + ", ".join(f"{g} {m / 60:.1f}h ({sessions[g]} sessions)" for g, m in top[:5]) + ".")
    if longest[0]:
        lines.append(f"Longest sitting: {longest[0] / 60:.1f} hours of {longest[1]}.")
    if days:
        lines.append(f"Busiest day of the week: {days.most_common(1)[0][0]}.")
    if w or l:
        lines.append(f"Results you told me: {w} wins, {l} losses.")
    if show:
        try:
            import pulls
            pulls.pull("briefing", {"game": f"Gaming, {label}", "friends": [],
                                    "queue": [f"{g}: {m / 60:.1f}h" for g, m in top[:6]] +
                                             ([f"Total {total / 60:.1f}h" + (f" ({'+' if change >= 0 else ''}{change:.0f}%)" if change is not None else "")])},
                       id="month", title="Monthly report", ttl=300, auto=False)
        except Exception:
            pass
    return " ".join(lines)


# ================================================================== background: radar weekly, report on the 1st
def _loop():
    time.sleep(900)
    while True:
        try:
            core = CORE
            now = datetime.now()
            import moments
            if core is not None and 12 <= now.hour < 21 and not moments._busy_or_away(core, (5, 900)):
                st = _st()
                wk = now.strftime("%G-W%V")
                if os.environ.get("JARVIS_SALES_RADAR", "true").lower() != "false" and st.get("radar_week") != wk \
                        and now.weekday() in (3, 4, 5):
                    import steam
                    if steam.ready():
                        st["radar_week"] = wk
                        _save_st(st)
                        deals = radar(4)
                        if deals:
                            d = deals[0]
                            core.events.put(("moment", {"line": f"Sales radar: {d['name']} is {d['pct']}% off, and it's "
                                                                f"your kind of game ({d['why']}). "
                                                                + (f"Plus {len(deals) - 1} more like it." if len(deals) > 1 else ""),
                                                        "cards": []}))
                            radar_text(show=True)
                mk = now.strftime("%Y-%m")
                if now.day <= 3 and st.get("report_month") != mk and os.environ.get("JARVIS_MONTH_REPORT", "true").lower() != "false":
                    st["report_month"] = mk
                    _save_st(st)
                    prev = now.replace(day=1) - timedelta(days=1)
                    text = month_report(prev.year, prev.month, show=True)
                    if not text.startswith("No games"):
                        core.events.put(("moment", {"line": "Your gaming month is in. " + text.split(". ")[0] + ". The rest is on your desktop.",
                                                    "cards": []}))
        except Exception as e:
            print(f"[games] {e}")
        time.sleep(1800)


def start(core):
    global CORE
    CORE = core
    threading.Thread(target=_loop, daemon=True, name="games-extra").start()


def tool(action="session", game=None):
    a = (action or "session").lower()
    if a == "clip":
        return clip()[1]
    if a == "valorant":
        try:
            return valorant_last()
        except Exception as e:
            return f"Couldn't reach HenrikDev: {e}"
    if a == "radar":
        return radar_text()
    if a == "month":
        return month_report()
    import gamemode
    g = game or (gamemode.playing() if gamemode.WATCH else None) or (getattr(gamemode.WATCH, "last_session", None) or {}).get("name")
    if not g:
        return "Which game?"
    if "valorant" in g.lower():
        try:
            return valorant_last()
        except Exception as e:
            return f"Couldn't reach HenrikDev: {e}"
    return session_report(g)
