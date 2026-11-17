"""
Game mode: she notices when you're playing and gets out of the way.

  * A game is something running from a game library folder (Steam, Epic, Riot, Xbox/Game Pass, GOG, EA, Ubisoft,
    Battle.net), anything you add in Settings, or anything you tell her is a game. Alt-tabbing out doesn't end it:
    the session lasts until the game closes.
  * While you play: no conversation starters, check-ins, song comments, break reminders or rain alerts, she keeps
    answers short, and Discord messages are only read out from the people you pick (Settings, or "let Kai through
    while I'm gaming"). Everything else waits in the log.
  * When the game closes after a real session (20 minutes or more), she asks how it went.

She only knows the game's name and how long it ran. Nothing reads the game's memory or screen, and nothing is ever
clicked or typed into it.
"""
import os
import random
import re
import threading
import time

import json
from datetime import date, datetime
import config

LIB_DIRS = re.compile(r"\\(steamapps\\common|epic games|riot games|xboxgames|gog galaxy\\games|gog games|ea games|"
                      r"origin games|ubisoft game launcher\\games|ubisoft\\ubisoft game launcher\\games|battle\.net|"
                      r"blizzard|rockstar games|bethesda\.net launcher\\games|amazon games\\library|"
                      r"itch\\apps|modifiablewindowsapps)\\([^\\]+)", re.I)
NOT_GAMES = {"steam.exe", "steamwebhelper.exe", "epicgameslauncher.exe", "riotclientservices.exe", "riotclientux.exe",
             "battle.net.exe", "galaxyclient.exe", "eadesktop.exe", "origin.exe", "upc.exe", "ubisoftconnect.exe",
             "gamebar.exe", "crashreportclient.exe", "unrealcefsubprocess.exe", "easyanticheat.exe",
             "easyanticheat_eos.exe", "beservice.exe", "vgtray.exe", "launcher.exe"}
CHECKIN_MINUTES = 20


def _extra():
    return {x.strip().lower() if x.strip().lower().endswith(".exe") else x.strip().lower() + ".exe"
            for x in (config.GAME_EXTRA or "").split(",") if x.strip()}


def _allow():
    return [x.strip().lower() for x in (config.GAME_ALLOW or "").split(",") if x.strip()]


def _nice(name):
    n = re.sub(r"\.exe$", "", name, flags=re.I)
    n = re.sub(r"[-_](win64|shipping|x64|dx11|dx12|vulkan)\b", "", n, flags=re.I)
    n = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", n).replace("_", " ").strip()
    return n or name


def _fg_process():
    """(pid, exe name, exe path, window title) of the app in front."""
    import ctypes
    from ctypes import wintypes as wt
    import psutil
    u = ctypes.windll.user32
    h = u.GetForegroundWindow()
    if not h:
        return None
    pid = wt.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    n = u.GetWindowTextLengthW(h)
    buf = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, buf, n + 1)
    try:
        p = psutil.Process(pid.value)
        return pid.value, p.name(), p.exe(), buf.value
    except Exception:
        return None


def identify(exe_name, exe_path, title=""):
    """The game's name if this looks like a game, else None."""
    low = (exe_name or "").lower()
    if low in NOT_GAMES:
        return None
    if low in _extra():
        return (title or "").strip() or _nice(exe_name)
    m = LIB_DIRS.search(exe_path or "")
    if m:
        folder = m.group(2)
        if folder.lower() in ("steamapps", "common", "games", "content"):
            folder = _nice(exe_name)
        return re.sub(r"\s+", " ", folder).strip()
    return None


class GameWatch:
    def __init__(self, core):
        self.core = core
        self.current = None              # {"name", "pid", "exe", "since", "manual"}
        self._stop = threading.Event()
        self.last_session = None

    def start(self):
        if os.name == "nt":
            threading.Thread(target=self._loop, daemon=True, name="game-watch").start()
        return self

    def stop(self):
        self._stop.set()

    def name(self):
        return self.current["name"] if self.current else None

    # -------------------------------------------------------------- wins and losses you tell him about
    def result(self, kind):
        """'win' / 'loss', from what you say ("we lost again", "gg we won"). He can't see the game itself."""
        rs = self.results = getattr(self, "results", [])
        rs.append((time.time(), kind, self.name()))
        del rs[:-50]
        _log_play({"t": time.time(), "result": kind, "game": self.name()})
        self._maybe_break()                         # between matches is the moment for a break nudge

    def _maybe_break(self):
        """Long sitting? Suggest a break, once per session, right after a match (never mid-game)."""
        try:
            limit = int(os.environ.get("JARVIS_PLAY_BREAK", "180") or 0)
        except ValueError:
            limit = 180
        cur = self.current
        if not limit or not cur or cur.get("break_nudged"):
            return
        mins = (time.time() - cur["since"]) / 60
        if mins < limit:
            return
        cur["break_nudged"] = True
        w, l = self.record()
        span = f"{mins / 60:.1f} hours".replace(".0 ", " ")
        line = random.choice([f"That's {span} of {cur['name']}. Good moment for a five-minute break before the next one?",
                              f"{span[0].upper() + span[1:]} straight. Water, stretch, then back in?"])
        self.core.events.put(("moment", {"line": line, "cards": [{"title": "Break?", "big": span,
                                                                    "text": f"{w}W {l}L so far" if w or l else cur["name"]}]}))

    def loss_streak(self):
        """Losses in a row, counting only the last 3 hours."""
        n = 0
        for t, k, _ in reversed(getattr(self, "results", [])):
            if time.time() - t > 3 * 3600 or k != "loss":
                break
            n += 1
        return n

    def record(self):
        rs = [r for r in getattr(self, "results", []) if time.time() - r[0] < 12 * 3600]
        w, l = sum(1 for r in rs if r[1] == "win"), sum(1 for r in rs if r[1] == "loss")
        return w, l

    # -------------------------------------------------------------- you can tell him too
    def set_manual(self, name):
        """'I'm playing X' / 'game mode on': quiet until you say it's over (or 4 hours)."""
        if name:
            self._begin({"name": name, "pid": None, "exe": None, "since": time.time(), "manual": True})
        elif self.current:
            self._end()

    def _loop(self):
        import psutil
        self._stop.wait(15)
        while not self._stop.wait(5):
            if not config.GAME_DETECT and not (self.current and self.current.get("manual")):
                if self.current:
                    self._end(quiet=True)
                continue
            try:
                cur = self.current
                if cur:
                    if cur.get("manual"):
                        if time.time() - cur["since"] > 4 * 3600:
                            self._end(quiet=True)
                    elif not psutil.pid_exists(cur["pid"]):
                        self._end()
                    continue
                fg = _fg_process()
                if not fg:
                    continue
                pid, exe, path, title = fg
                name = identify(exe, path, title)
                if name:
                    self._begin({"name": name, "pid": pid, "exe": exe, "since": time.time(), "manual": False})
            except Exception as e:
                print(f"[game] {e}")

    def _begin(self, info):
        self.current = info
        print(f"[game] playing {info['name']}")
        self.core.emit({"type": "game", "on": True, "name": info["name"]})
        try:
            if getattr(self.core, "history", None) is not None:
                self.core.history.add("Game", f"Started playing {info['name']}")
        except Exception:
            pass
        try:
            import pulls
            pulls.game_briefing(info["name"])          # friends on, queues, latest patch: up while it loads
        except Exception as e:
            print(f"[game] briefing: {e}")
        try:
            import triggers
            triggers.on_game(info["name"])             # "when I open DBD, ..."
        except Exception as e:
            print(f"[game] triggers: {e}")
        threading.Thread(target=self._patch_alert, args=(info["name"],), daemon=True).start()
        hub = getattr(self.core, "glass", None)
        if hub is not None and hub.connected():
            try:
                hub.game_card(info["name"])
            except Exception as e:
                print(f"[game] glass card: {e}")

    def _end(self, quiet=False):
        cur, self.current = self.current, None
        if not cur:
            return
        mins = (time.time() - cur["since"]) / 60
        if mins >= 1:
            _log_play({"t": time.time(), "game": cur["name"], "start": cur["since"], "minutes": round(mins, 1)})
        self.last_session = {"name": cur["name"], "minutes": round(mins), "ended": time.time()}
        print(f"[game] stopped {cur['name']} after {mins:.0f} min")
        self.core.emit({"type": "game", "on": False, "name": cur["name"], "minutes": round(mins)})
        try:
            if getattr(self.core, "history", None) is not None:
                self.core.history.add("Game", f"Stopped playing {cur['name']} after {round(mins)} minutes")
        except Exception:
            pass
        if not quiet and config.GAME_CHECKIN and mins >= CHECKIN_MINUTES:
            threading.Thread(target=self._checkin, args=(cur["name"], mins), daemon=True).start()

    def _patch_alert(self, name):
        """The game updated in the last two days and he hasn't told you yet: say the gist while it loads."""
        if os.environ.get("JARVIS_PATCH_ALERTS", "true").lower() == "false":
            return
        try:
            import steam
            app = steam.appid_for(name)
            if not app:
                return
            items = steam.news(app, 3)
        except Exception as e:
            print(f"[game] patch check: {e}")
            return
        import re as _re
        fresh = [it for it in items if time.time() - it.get("date", 0) < 2 * 86400
                 and _re.search(r"patch|update|hotfix|fix|notes|balance", (it.get("title", "") + " " + it.get("feedlabel", "")), _re.I)]
        if not fresh:
            return
        it = fresh[0]
        st = steam._load()                                   # shared with the background patch check: never told twice
        seen = st.setdefault("seen_news", {})
        if seen.get(str(app)) == it.get("gid"):
            return
        seen[str(app)] = it.get("gid")
        steam._save(st)
        body = steam._clean(it.get("contents", ""))
        bits = [x.strip(" -•*") for x in _re.split(r"[\r\n]+", body) if 10 < len(x.strip()) < 120][:3]
        when = "today" if time.time() - it.get("date", 0) < 86400 else "yesterday"
        line = f"Heads up, {name} got a patch {when}" + (f": {bits[0].rstrip('.')}" if bits else f": {it.get('title', '')}") + \
            (". There's more on your screen." if len(bits) > 1 else ".")
        self.core.events.put(("moment", {"line": line, "cards": [{"title": f"{name} patch", "list": [
            {"time": "", "text": b} for b in bits] or [{"time": "", "text": it.get("title", "")}]}]}))

    def stats(self, days=1):
        """Play time and wins/losses for today (days=1) or the last N days."""
        rows = _read_play()
        cut = time.time() - days * 86400 if days > 1 else datetime.combine(date.today(), datetime.min.time()).timestamp()
        mins, games, w, l = 0.0, {}, 0, 0
        for r in rows:
            if r["t"] < cut:
                continue
            if "minutes" in r:
                mins += r["minutes"]
                games[r["game"]] = games.get(r["game"], 0) + r["minutes"]
            elif r.get("result") == "win":
                w += 1
            elif r.get("result") == "loss":
                l += 1
        if self.current:
            live = (time.time() - self.current["since"]) / 60
            if self.current["since"] >= cut:
                mins += live
                games[self.current["name"]] = games.get(self.current["name"], 0) + live
        return {"minutes": round(mins), "games": {k: round(v) for k, v in sorted(games.items(), key=lambda x: -x[1])},
                "wins": w, "losses": l, "playing": self.name(),
                "session": round((time.time() - self.current["since"]) / 60) if self.current else 0}

    def _checkin(self, name, mins):
        """Ask how it went, once you're back (not if you went straight into another game, a call or went quiet)."""
        import moments
        for _ in range(40):                                      # up to ~10 minutes to find a good moment
            if self._stop.wait(15):
                return
            if self.current:
                return
            if not moments._busy_or_away(self.core, (1, 300)):
                break
        else:
            return
        span = f"{mins / 60:.1f} hours".replace(".0 ", " ") if mins >= 60 else f"{round(mins)} minutes"
        line = random.choice([
            f"{span[0].upper() + span[1:]} of {name}. How'd it go?",
            f"Welcome back. How was {name}?",
            f"That was a {span} {name} session. Win some, lose some?",
            f"Done with {name}? Tell me how it went.",
        ])
        self.core.events.put(("moment", {"line": line, "cards": [{"title": name, "big": span, "text": "game session"}]}))


def _play_file():
    return config.JARVIS_DIR / "play_log.jsonl"


def _log_play(row):
    try:
        with open(_play_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except Exception as e:
        print(f"[game] log: {e}")


def _read_play():
    try:
        return [json.loads(l) for l in _play_file().read_text(encoding="utf-8").splitlines()[-3000:] if l.strip()]
    except Exception:
        return []


WATCH = None


def start(core):
    global WATCH
    if WATCH is None:
        WATCH = GameWatch(core).start()
    return WATCH


def playing():
    """Name of the game you're in (even alt-tabbed), or None."""
    return WATCH.name() if WATCH is not None else None


def allow_discord(sender):
    """While gaming, is this person allowed to interrupt?"""
    s = (sender or "").lower()
    return any(a and (a == s or a in s) for a in _allow())
