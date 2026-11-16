"""
Things he keeps an eye on and keeps up on the desktop while they matter:

  score     a game's live score (ESPN's public scoreboards: NFL, NBA, MLB, NHL, college, MLS, Premier League,
            La Liga, Serie A, Bundesliga, Ligue 1, Champions League, Liga MX...). Ends at full time.
  download  a file that's still downloading (the newest .crdownload / .part / .tmp in Downloads, or a path you
            name). Ends when it stops growing for a minute or the partial file turns into the real one.
  flight    a flight in the air, by flight number (adsb.lol's free feed of what planes broadcast). Ends when it
            lands or disappears.

Packages aren't here: every carrier wants an account and a paid key for tracking, so he says so and offers to look
the tracking number up on the web instead.
"""
import os
import re
import time
from datetime import datetime
from pathlib import Path

import config

ESPN = "https://site.api.espn.com/apis/site/v2/sports/{}/scoreboard"
LEAGUES = {
    "nfl": "football/nfl", "college football": "football/college-football", "ncaaf": "football/college-football",
    "nba": "basketball/nba", "wnba": "basketball/wnba", "college basketball": "basketball/mens-college-basketball",
    "mlb": "baseball/mlb", "nhl": "hockey/nhl", "mls": "soccer/usa.1", "premier league": "soccer/eng.1", "epl": "soccer/eng.1",
    "la liga": "soccer/esp.1", "serie a": "soccer/ita.1", "bundesliga": "soccer/ger.1", "ligue 1": "soccer/fra.1",
    "champions league": "soccer/uefa.champions", "europa league": "soccer/uefa.europa", "liga mx": "soccer/mex.1",
    "fa cup": "soccer/eng.fa", "eredivisie": "soccer/ned.1", "primeira liga": "soccer/por.1",
}
GUESS_ORDER = ["nfl", "nba", "mlb", "nhl", "premier league", "la liga", "champions league", "serie a", "bundesliga",
               "ligue 1", "mls", "liga mx", "college football", "college basketball", "wnba"]
AIRLINES = {"UA": "UAL", "AA": "AAL", "DL": "DAL", "WN": "SWA", "B6": "JBU", "AS": "ASA", "NK": "NKS", "F9": "FFT",
            "AV": "AVA", "CM": "CMP", "AM": "AMX", "Y4": "VOI", "BA": "BAW", "LH": "DLH", "AF": "AFR", "KL": "KLM",
            "IB": "IBE", "AC": "ACA", "EK": "UAE", "QR": "QTR", "TK": "THY", "LA": "LAN", "VS": "VIR", "U2": "EZY",
            "FR": "RYR", "WS": "WJA", "HA": "HAL", "G4": "AAY", "SY": "SCX", "VB": "VIV", "AR": "ARG", "CX": "CPA",
            "SQ": "SIA", "QF": "QFA", "NH": "ANA", "JL": "JAL", "EY": "ETD", "TP": "TAP", "AZ": "ITY", "LX": "SWR"}
_ACTIVE = {}


def _get(url, params=None):
    import requests
    r = requests.get(url, params=params or {}, timeout=8, headers={"User-Agent": "Jarvis-desktop-assistant"})
    r.raise_for_status()
    return r.json()


# ------------------------------------------------------------------ scores
def _find_game(team, league=None):
    team_l = team.lower()
    order = [league.lower()] if league and league.lower() in LEAGUES else GUESS_ORDER
    for lg in order:
        try:
            j = _get(ESPN.format(LEAGUES[lg]))
        except Exception:
            continue
        for ev in j.get("events", []):
            comp = (ev.get("competitions") or [{}])[0]
            names = " ".join(f"{c['team'].get('displayName', '')} {c['team'].get('shortDisplayName', '')} "
                             f"{c['team'].get('abbreviation', '')}" for c in comp.get("competitors", []))
            if team_l in names.lower():
                return lg, ev["id"]
    return None, None


def _score(lg, eid):
    j = _get(ESPN.format(LEAGUES[lg]))
    ev = next((e for e in j.get("events", []) if e["id"] == eid), None)
    if not ev:
        return None
    comp = (ev.get("competitions") or [{}])[0]
    st = (ev.get("status") or {}).get("type") or {}
    teams = []
    for c in sorted(comp.get("competitors", []), key=lambda c: c.get("homeAway") != "home"):
        teams.append({"name": c["team"].get("shortDisplayName") or c["team"].get("displayName"), "score": c.get("score"),
                      "win": bool(c.get("winner"))})
    detail = st.get("shortDetail") or st.get("detail") or ""
    venue = ((comp.get("venue") or {}).get("fullName")) or ""
    last = ((comp.get("situation") or {}).get("lastPlay") or {}).get("text") or ""
    lines = [x for x in (last, ev.get("name"), venue) if x]
    return {"kind": "score", "teams": teams, "status": detail, "lines": lines[:3], "live": st.get("state") == "in",
            "source": "ESPN", "done": st.get("completed", False)}


# ------------------------------------------------------------------ downloads
def _downloads_dir():
    import tools
    return tools._known_folders()["downloads"]


def _partial(path=None):
    if path:
        import tools
        p = tools._resolve(path, tools.config.HOME)
        return p if p.exists() else None
    d = _downloads_dir()
    cands = [p for p in d.glob("*") if p.suffix.lower() in (".crdownload", ".part", ".partial", ".download", ".tmp", ".opdownload")]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None


def _download_state(st):
    p = st["path"]
    final = Path(re.sub(r"\.(crdownload|part|partial|download|opdownload)$", "", str(p), flags=re.I))
    if not p.exists() and final.exists():
        size = final.stat().st_size
        return {"main": "Done", "progress": 100, "status": "finished", "lines": [f"{final.name} · {size / 2**20:,.0f} MB"],
                "source": "Downloads folder", "done": True}
    if not p.exists():
        return {"main": "Gone", "status": "stopped", "lines": [f"{p.name} disappeared (cancelled?)"], "done": True}
    size = p.stat().st_size
    now = time.time()
    rate = max(0.0, (size - st["size"]) / max(.5, now - st["t"]))
    st.update(size=size, t=now, still=(st.get("still", 0) + 1) if rate <= 0 else 0)
    hist = st.setdefault("hist", [])
    hist.append(round(rate / 2**20, 2))
    del hist[:-90]
    lines = [f"{final.name} · {size / 2**20:,.0f} MB so far"]
    return {"main": f"{rate / 2**20:.1f} MB/s" if rate > 0 else f"{size / 2**20:,.0f} MB", "status": "downloading" if rate > 0 else "waiting",
            "lines": lines, "spark": list(hist), "source": "Downloads folder", "done": st["still"] >= 60}


# ------------------------------------------------------------------ flights
def _callsign(flight):
    f = re.sub(r"\s+", "", flight.upper())
    m = re.match(r"^([A-Z0-9]{2})(\d{1,4}[A-Z]?)$", f)
    if m and m.group(1) in AIRLINES:
        return AIRLINES[m.group(1)] + m.group(2)
    return f


def _flight(cs, trail=None):
    j = _get(f"https://api.adsb.lol/v2/callsign/{cs}")
    ac = (j.get("ac") or [None])[0]
    if not ac:
        return None
    if trail is not None and ac.get("lat") is not None:
        if not trail or (trail[-1][0], trail[-1][1]) != (ac["lat"], ac["lon"]):
            trail.append((round(ac["lat"], 4), round(ac["lon"], 4)))
            del trail[:-240]
    alt = ac.get("alt_baro")
    ground = alt == "ground" or (isinstance(alt, (int, float)) and alt < 100)
    lines = [f"{cs} · {ac.get('t') or ac.get('desc') or ''}".strip(" ·")]
    if ac.get("lat") is not None:
        lines.append(f"at {ac['lat']:.2f}, {ac['lon']:.2f}")
    main = "On the ground" if ground else f"{int(alt):,} ft" if isinstance(alt, (int, float)) else "In the air"
    if ac.get("gs") and not ground:
        lines.insert(1, f"{int(ac['gs'])} kt ground speed")
    out = {"main": main, "status": "landed" if ground else "airborne", "lines": lines, "source": "adsb.lol", "done": ground,
           "kind": "flight", "alt": alt if isinstance(alt, (int, float)) else 0, "gs": ac.get("gs"), "track": ac.get("track"),
           "lat": ac.get("lat"), "lon": ac.get("lon")}
    if trail is not None:
        out["trail"] = list(trail)
    return out


# ------------------------------------------------------------------ the tool
def track(kind, query=None, league=None, path=None, stop=False):
    import pulls
    kind = (kind or "").lower()
    if stop:
        pulls.stop_live(kind=f"track-{kind}" if kind else "track")
        pulls.clear("tracker") if not kind else None
        return "Stopped tracking."
    if kind == "package":
        return ("I can't track packages live: every carrier wants an account and a paid key for that. I can look the "
                "tracking number up on the web right now instead.")
    if kind == "score":
        if not query:
            return "Which team?"
        lg, eid = _find_game(query, league)
        if not eid:
            return f"I couldn't find a {query} game on today's scoreboards" + (f" for {league}" if league else "") + "."
        d = _score(lg, eid)
        pid = f"track-score-{eid}"
        pulls.pull("tracker", d, id=pid, title="Score", ttl=900, live=True, auto=False)
        if not d["done"]:
            pulls.keep_live(pid, lambda: _gate(_score(lg, eid)), every=10, for_secs=4 * 3600, ttl=900)
        t = d["teams"]
        return f"{t[0]['name']} {t[0]['score']}, {t[1]['name']} {t[1]['score']} ({d['status']}). It's live on the desktop."
    if kind == "download":
        p = _partial(path)
        if not p:
            return "I don't see anything downloading in your Downloads folder right now."
        st = {"path": p, "size": p.stat().st_size, "t": time.time()}
        d = _download_state(st)
        pid = "track-download"
        pulls.pull("tracker", d, id=pid, title="Download", ttl=180, live=True, auto=False)
        pulls.keep_live(pid, lambda: _gate(_download_state(st)), every=1, for_secs=6 * 3600, ttl=180)
        return f"Watching {p.name}. It's up on the desktop; I'll keep it updated until it finishes."
    if kind == "flight":
        if not query:
            return "Which flight?"
        cs = _callsign(query)
        trail = []
        try:
            d = _flight(cs, trail)
        except Exception as e:
            return f"The flight feed didn't answer ({type(e).__name__}). I can search the web for it instead."
        if not d:
            return f"{query.upper()} isn't broadcasting right now (not in the air yet, landed, or out of receiver range)."
        pid = f"track-flight-{cs}"
        pulls.pull("tracker", d, id=pid, title=f"Flight {query.upper()}", ttl=900, live=True, auto=False)
        pulls.keep_live(pid, lambda: _gate(_flight(cs, trail)), every=5, for_secs=16 * 3600, ttl=900)
        return f"{query.upper()}: {d['main']}, {'; '.join(d['lines'][1:])}. Tracking it on the desktop."
    return "I can track a score, a download, or a flight."


def _gate(d):
    """(pulls.Loop stops refreshing once a result says done, after showing it.)"""
    return d
