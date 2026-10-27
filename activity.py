"""
Activity memory: what you've been doing on this PC, so he can answer "what was I working on yesterday
afternoon?", "how long was I in Blender today?", "when did I last have the budget spreadsheet open?" and
"reopen what I had going on Friday".

What it keeps: every few seconds, which app is in front and its window title ("mug.blend - Blender",
"#general | Friends - Discord"). That's all. No screenshots, no keystrokes, no page contents, nothing typed.

Privacy, on purpose:
  * OFF until you switch it on (Settings > Activity memory, or "turn on activity memory").
  * Stays on this PC in Documents\\Jarvis\\Activity, one small file per day, deleted after 14 days (you can change
    that). Nothing is sent anywhere until you ask him about it; then only the summary he needs goes to Claude.
  * Never logged: private/incognito windows, password managers, the lock and sign-in screens, Windows security
    prompts, Jarvis himself, and anything you add to "Never log" (apps or words, like "bank, tax").
  * Things that look like passwords, card numbers or keys in a title are blanked, same as conversation history.
  * "Pause activity memory for an hour", "forget my activity from today", "wipe my activity memory".
  * Discord bot chats can't reach it (other people), and neither can background jobs.
"""
import json
import os
import re
import struct
import sys
import threading
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import config

SAMPLE_SECS = 5
IDLE_SECS = 5 * 60          # no mouse or keyboard this long: still logged (watching something), marked idle
AWAY_SECS = 30 * 60         # this long: you're away, nothing's logged
CHUNK_SECS = 10 * 60        # long stretches are saved in pieces, so a crash loses at most ten minutes
SKIP_EXES = {"keepass.exe", "keepassxc.exe", "1password.exe", "bitwarden.exe", "lastpass.exe", "dashlane.exe",
             "enpass.exe", "nordpass.exe", "protonpass.exe", "roboform.exe", "keeper.exe", "lockapp.exe",
             "logonui.exe", "consent.exe", "credentialuibroker.exe", "searchhost.exe", "searchapp.exe",
             "shellexperiencehost.exe", "startmenuexperiencehost.exe", "textinputhost.exe", "jarvis.exe",
             "snippingtool.exe", "screenclippinghost.exe", "msedgewebview2.exe"}
PRIVATE = re.compile(r"(?i)\b(inprivate|incognito|private browsing|private window|tor browser)\b")
SECRETISH = re.compile(r"(?i)\b(sk-[a-z0-9_-]{12,}|gsk_[a-z0-9]{12,}|[a-f0-9]{32,}|eyJ[a-z0-9_-]{20,})\b")
FILE_RE = re.compile(r"(?i)([\w\-. ()\[\]&',+#~]{1,120}?\.(?:docx?|xlsx?|xlsm|pptx?|pdf|txt|md|rtf|odt|ods|csv|json|"
                     r"blend|fbx|obj|stl|glb|gltf|uproject|umap|psd|kra|xcf|ai|indd|afphoto|afdesign|png|jpe?g|gif|"
                     r"webp|svg|mp4|mov|mkv|wav|mp3|flac|aep|prproj|drp|py|js|ts|tsx|jsx|html|css|c|cpp|h|hpp|cs|"
                     r"java|kt|lua|gd|rs|go|rb|php|sql|ipynb|ino|scad|f3d|step|3mf|gcode|sln|unitypackage))\b")
NEVER_OPEN = {".exe", ".bat", ".cmd", ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".msi", ".scr", ".com", ".reg",
              ".lnk", ".hta", ".cpl", ".jar", ".py", ".sh"}
PARTS = {"morning": (5, 12), "afternoon": (12, 17), "evening": (17, 22), "night": (20, 28), "tonight": (17, 28)}
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def folder():
    return config.JARVIS_DIR / "Activity"


def enabled():
    return (os.environ.get("JARVIS_ACTIVITY") or "false").lower() == "true"


def keep_days():
    try:
        return max(1, min(365, int(float(os.environ.get("JARVIS_ACTIVITY_DAYS") or 14))))
    except ValueError:
        return 14


def skip_words():
    raw = os.environ.get("JARVIS_ACTIVITY_SKIP") or ""
    return [w.strip().lower() for w in re.split(r"[,;\n]", raw) if len(w.strip()) >= 2]


# ======================================================================== titles
def tidy(title):
    """'(3) ● tools.py - jarvis - Visual Studio Code' -> 'tools.py - jarvis - Visual Studio Code', secrets blanked."""
    t = " ".join(str(title or "").split())
    t = re.sub(r"^\(\d+\+?\)\s*", "", t)
    t = re.sub(r"^[●•*]\s*", "", t)
    t = re.sub(r"\s*[●•]\s*", " ", t)
    t = re.sub(r"\*(\s+[-–—|])", r"\1", t)
    try:
        import history
        t = history.redact(t)
    except Exception:
        pass
    t = SECRETISH.sub("[removed]", t)
    return t[:160].strip()


def short_title(title, app):
    """Drop the app's own name off the end: 'mug.blend - Blender 4.2' -> 'mug.blend'."""
    parts = re.split(r"(\s+[-–—|]\s+)", title or "")      # keeps the separators at odd positions
    words = {w for w in re.findall(r"[a-z0-9]+", (app or "").lower()) if len(w) > 2}
    while len(parts) > 2 and (words & set(re.findall(r"[a-z0-9]+", parts[-1].lower()))
                              or re.search(r"(?i)\b(google chrome|microsoft.? edge|mozilla firefox|brave|opera)\b",
                                           parts[-1])):
        parts = parts[:-2]
    out = "".join(parts).strip()
    return out if out and out.lower() != (app or "").lower() else ""


def files_in(title):
    return [m.group(1).strip(" -") for m in FILE_RE.finditer(title or "")]


# ======================================================================== time spans
def span(when="today", now=None):
    """'today', 'yesterday afternoon', 'this morning', 'last 2 hours', 'friday', 'last week', '2026-10-20'
    -> (start, end, label)."""
    now = now or datetime.now()
    t0 = datetime.combine(now.date(), datetime.min.time())
    w = " ".join(str(when or "today").lower().replace(",", " ").split())
    w = re.sub(r"^(on|from|during|over|in)\s+", "", w)
    m = re.match(r"^(?:the\s+)?(?:last|past)\s+(\d+|an?|one|few|couple of)?\s*(minute|min|hour|hr|day)s?$", w)
    if m:
        n = {"a": 1, "an": 1, "one": 1, "few": 3, "couple of": 2, None: 1}.get(m.group(1))
        n = n if n is not None else int(m.group(1))
        unit = m.group(2)
        if unit.startswith("d"):
            return t0 - timedelta(days=n - 1), now, f"the last {n} day{'s' if n != 1 else ''}"
        d = timedelta(minutes=n) if unit.startswith("m") else timedelta(hours=n)
        u = "minute" if unit.startswith("m") else "hour"
        return now - d, now, (f"the last {n} {u}s" if n != 1 else f"the last {u}")
    if w in ("", "today", "so far today", "all day"):
        return t0, now, "today"
    if w in ("this week", "the week"):
        return t0 - timedelta(days=now.weekday()), now, "this week"
    if w == "last week":
        a = t0 - timedelta(days=now.weekday() + 7)
        return a, a + timedelta(days=7), "last week"
    if w in ("now", "just now", "recently", "lately"):
        return now - timedelta(minutes=45), now, "the last 45 minutes"
    m = re.match(r"^(this|yesterday|today|last|(?:last\s+)?(?:" + "|".join(DAYS) + r"))?\s*(morning|afternoon|"
                 r"evening|night|tonight)?$", w)
    if m and (m.group(1) or m.group(2)):
        day_word, part = m.group(1) or "today", m.group(2)
        if day_word == "last" and part == "night":
            day_word = "yesterday"
        if day_word in ("this", "today"):
            d = t0
        elif day_word == "yesterday":
            d = t0 - timedelta(days=1)
        elif day_word == "last":
            d = t0 - timedelta(days=1)
        else:
            name = day_word.split()[-1]
            back = (now.weekday() - DAYS.index(name)) % 7
            if day_word.startswith("last") and back == 0:
                back = 7
            d = t0 - timedelta(days=back)
        label = "today" if d == t0 else "yesterday" if d == t0 - timedelta(days=1) else f"{d:%A}"
        if not part:
            return d, min(d + timedelta(days=1), now), label
        h0, h1 = PARTS[part]
        a, b = d + timedelta(hours=h0), d + timedelta(hours=h1)
        if part == "tonight":
            lab = "tonight" if label == "today" else f"{label} evening"
        elif part == "night" and label == "yesterday":
            lab = "last night"
        else:
            lab = {"today": f"this {part}", "yesterday": f"yesterday {part}"}.get(label, f"{label} {part}")
        return a, min(b, now), lab
    try:
        d = datetime.fromisoformat(w)
        d = datetime.combine(d.date(), datetime.min.time())
        return d, min(d + timedelta(days=1), now), f"{d:%A %B} {d.day}"
    except ValueError:
        pass
    return t0, now, "today"


def clock(t):
    return t.strftime("%I:%M %p").lstrip("0")


def dur(secs):
    m = int(round(secs / 60))
    if m < 1:
        return "under a minute"
    if m < 60:
        return f"{m} min"
    h, m = divmod(m, 60)
    return f"{h} h {m} min" if m else f"{h} h"


# ======================================================================== the tracker
class Tracker:
    def __init__(self, path=None, sampler=None, idle=None, log=print):
        self.dir = Path(path or folder())
        self.sampler = sampler or _sample
        self.idle = idle or _idle_secs
        self.log = log
        self.cur = None
        self.paused_until = 0.0
        self.lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    def start(self):
        if self.running:
            return
        self._stop = threading.Event()             # a fresh one: an old loop still waking up keeps its own, set
        self.prune()
        self._thread = threading.Thread(target=self._loop, args=(self._stop,), daemon=True, name="activity")
        self._thread.start()

    def stop(self):
        self._stop.set()
        self.flush()

    def pause(self, minutes=None):
        with self.lock:
            self.paused_until = time.time() + (float(minutes) * 60 if minutes else 10 * 365 * 86400)
            self.flush()

    def resume(self):
        with self.lock:
            self.paused_until = 0.0

    @property
    def paused(self):
        return time.time() < self.paused_until

    def _loop(self, stop):
        last_prune = time.time()
        while not stop.wait(SAMPLE_SECS):
            try:
                self.feed(time.time(), None if self.paused else self.sampler(), self.idle())
            except Exception as e:
                self.log(f"[activity] {type(e).__name__}: {e}")
            if time.time() - last_prune > 6 * 3600:
                last_prune = time.time()
                self.prune()

    def feed(self, now, sample, idle_secs):
        """One sample: (exe, app, title) or None (away, locked, private, skipped)."""
        with self.lock:
            if sample is None or idle_secs >= AWAY_SECS or self.paused:
                self.flush(end=now - (idle_secs if idle_secs >= AWAY_SECS else 0))
                return
            exe, app, title = sample
            title = tidy(title)
            passive = idle_secs >= IDLE_SECS
            c = self.cur
            if (c and c["exe"] == exe and c["title"] == title and c.get("idle", False) == passive
                    and now - c["e"] <= SAMPLE_SECS * 3 and now - c["s"] < CHUNK_SECS):
                c["e"] = now
                return
            self.flush(end=now if c and now - c["e"] <= SAMPLE_SECS * 3 else None)
            self.cur = {"s": now, "e": now, "exe": exe, "app": app, "title": title}
            if passive:
                self.cur["idle"] = True

    def flush(self, end=None):
        with self.lock:
            c, self.cur = self.cur, None
            if not c:
                return
            c["e"] = max(c["e"], min(end if end else c["e"] + SAMPLE_SECS, c["e"] + SAMPLE_SECS))
            if c["e"] - c["s"] < 2:
                return
            self._write(c)

    def _write(self, c):
        self.dir.mkdir(parents=True, exist_ok=True)
        day = datetime.fromtimestamp(c["s"]).strftime("%Y-%m-%d")
        rec = {"s": round(c["s"], 1), "e": round(c["e"], 1), "app": c["app"], "exe": c["exe"], "title": c["title"]}
        if c.get("idle"):
            rec["idle"] = True
        with open(self.dir / f"{day}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def prune(self):
        cutoff = date.today() - timedelta(days=keep_days())
        for p in self.dir.glob("*.jsonl") if self.dir.exists() else []:
            try:
                if date.fromisoformat(p.stem) < cutoff:
                    p.unlink()
            except (ValueError, OSError):
                continue

    def now(self):
        with self.lock:
            return dict(self.cur) if self.cur else None

    # ------------------------------------------------------------------ reading it back
    def sessions(self, a, b):
        """Every stretch between a and b (datetimes), clipped to the range, oldest first."""
        ta, tb = a.timestamp(), b.timestamp()
        out = []
        d = a.date() - timedelta(days=1)
        while d <= b.date():
            p = self.dir / f"{d:%Y-%m-%d}.jsonl"
            if p.exists():
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r["e"] > ta and r["s"] < tb:
                        r["s"], r["e"] = max(r["s"], ta), min(r["e"], tb)
                        out.append(r)
            d += timedelta(days=1)
        c = self.now()
        if c and c["e"] > ta and c["s"] < tb:
            c["s"], c["e"] = max(c["s"], ta), min(c["e"] + SAMPLE_SECS, tb)
            out.append(c)
        out.sort(key=lambda r: r["s"])
        return out

    def forget(self, when=None):
        """Delete a stretch ('today', 'the last hour') or everything (when=None / 'all')."""
        with self.lock:
            self.cur = None
            if not self.dir.exists():
                return 0
            if when in (None, "", "all", "everything"):
                n = 0
                for p in self.dir.glob("*.jsonl"):
                    p.unlink(missing_ok=True)
                    n += 1
                return n
            a, b, _ = span(when)
            ta, tb = a.timestamp(), b.timestamp()
            n = 0
            d = a.date() - timedelta(days=1)
            while d <= b.date():
                p = self.dir / f"{d:%Y-%m-%d}.jsonl"
                if p.exists():
                    keep = []
                    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                        try:
                            r = json.loads(line)
                        except ValueError:
                            continue
                        if r["e"] > ta and r["s"] < tb:
                            n += 1
                            if r["s"] < ta - 2:              # keep the part before the range
                                keep.append({**r, "e": ta})
                            if r["e"] > tb + 2:              # and after it
                                keep.append({**r, "s": tb})
                        else:
                            keep.append(r)
                    if keep:
                        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")
                    else:
                        p.unlink(missing_ok=True)
                d += timedelta(days=1)
            return n

    def size(self):
        if not self.dir.exists():
            return 0, 0
        files = list(self.dir.glob("*.jsonl"))
        return len(files), sum(p.stat().st_size for p in files)


# ======================================================================== summaries
def summarize(sessions, label, a, b):
    if not sessions:
        return f"Nothing logged for {label}." + ("" if enabled() else " Activity memory is off.")
    total = sum(r["e"] - r["s"] for r in sessions)
    idle = sum(r["e"] - r["s"] for r in sessions if r.get("idle"))
    apps = defaultdict(float)
    titles = defaultdict(lambda: defaultdict(float))
    for r in sessions:
        d = r["e"] - r["s"]
        apps[r["app"]] += d
        st = short_title(r["title"], r["app"])
        if st:
            titles[r["app"]][st] += d
    lines = [f"{label[:1].upper() + label[1:]} ({clock(datetime.fromtimestamp(sessions[0]['s']))} to "
             f"{clock(datetime.fromtimestamp(sessions[-1]['e']))}): about {dur(total)} on the PC"
             + (f", {dur(idle)} of it idle with something open" if idle >= 300 else "") + "."]
    for app, secs in sorted(apps.items(), key=lambda kv: -kv[1])[:8]:
        if secs < 60:
            continue
        top = sorted(titles[app].items(), key=lambda kv: -kv[1])[:4]
        bits = ", ".join(f"{t[:70]} ({dur(s)})" for t, s in top if s >= 30)
        lines.append(f"- {app} {dur(secs)}" + (f": {bits}" if bits else ""))
    lines.append("Timeline: " + timeline(sessions))
    return "\n".join(lines)


def timeline(sessions, gap=10 * 60, max_blocks=12):
    blocks = []
    for r in sessions:
        if blocks and r["s"] - blocks[-1]["e"] <= gap:
            b = blocks[-1]
            b["e"] = max(b["e"], r["e"])
        else:
            b = {"s": r["s"], "e": r["e"], "apps": defaultdict(float), "titles": defaultdict(float)}
            blocks.append(b)
        b["apps"][r["app"]] += r["e"] - r["s"]
        st = short_title(r["title"], r["app"])
        if st:
            b["titles"][st] += r["e"] - r["s"]
    blocks = [b for b in blocks if b["e"] - b["s"] >= 180]
    if len(blocks) > max_blocks:
        blocks = sorted(sorted(blocks, key=lambda b: -(b["e"] - b["s"]))[:max_blocks], key=lambda b: b["s"])
    out = []
    for b in blocks:
        top = sorted(b["apps"].items(), key=lambda kv: -kv[1])
        main = top[0][0] + (f" and {top[1][0]}" if len(top) > 1 and top[1][1] > 0.25 * top[0][1] else "")
        t = sorted(b["titles"].items(), key=lambda kv: -kv[1])
        what = f" ({t[0][0][:50]})" if t else ""
        out.append(f"{clock(datetime.fromtimestamp(b['s']))} to {clock(datetime.fromtimestamp(b['e']))} "
                   f"{main}{what}")
    return "; ".join(out) if out else "short bits only."


def search(sessions, query):
    words = [w for w in re.findall(r"[a-z0-9]+", (query or "").lower()) if len(w) > 1]
    if not words:
        return "Search for what?"
    hits = defaultdict(lambda: {"secs": 0.0, "last": 0.0, "first": 1e18})
    for r in sessions:
        hay = f"{r['app']} {r['title']}".lower()
        if all(w in hay for w in words):
            k = (r["app"], short_title(r["title"], r["app"]) or r["app"])
            h = hits[k]
            h["secs"] += r["e"] - r["s"]
            h["last"] = max(h["last"], r["e"])
            h["first"] = min(h["first"], r["s"])
    if not hits:
        return f"Nothing matching '{query}' in what's logged."
    today = date.today()
    lines = []
    for (app, t), h in sorted(hits.items(), key=lambda kv: -kv[1]["last"])[:10]:
        last = datetime.fromtimestamp(h["last"])
        when = "today" if last.date() == today else "yesterday" if last.date() == today - timedelta(days=1) \
            else f"{last:%A %B} {last.day}"
        lines.append(f"- {app}: {t[:80]}, {dur(h['secs'])} in all, last {when} at {clock(last)}")
    return "\n".join(lines)


# ======================================================================== reopening
def recent_dir():
    return Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Recent"


def lnk_target(path):
    """Where a Windows shortcut (.lnk) points (no COM needed: reads the file format directly)."""
    try:
        data = Path(path).read_bytes()
        if len(data) < 0x4C or struct.unpack_from("<I", data, 0)[0] != 0x4C:
            return None
        flags = struct.unpack_from("<I", data, 0x14)[0]
        pos = 0x4C
        if flags & 0x01:                                    # HasLinkTargetIDList
            pos += 2 + struct.unpack_from("<H", data, pos)[0]
        if not flags & 0x02:                                # no LinkInfo
            return None
        li = pos
        hsize, liflags, _vol, lbp, _net, suffix = struct.unpack_from("<IIIIII", data, li + 4)
        if not liflags & 0x01:
            return None

        def cstr(off, wide=False):
            if wide:
                end = off
                while end + 1 < len(data) and data[end:end + 2] != b"\x00\x00":
                    end += 2
                return data[off:end].decode("utf-16-le", "replace")
            end = data.index(b"\x00", off)
            return data[off:end].decode("mbcs" if sys.platform == "win32" else "latin-1", "replace")
        if hsize >= 0x24:
            lbpu, sufu = struct.unpack_from("<II", data, li + 28)
            base = cstr(li + lbpu, True) if lbpu else cstr(li + lbp)
            tail = cstr(li + sufu, True) if sufu else cstr(li + suffix)
        else:
            base, tail = cstr(li + lbp), cstr(li + suffix)
        return base + tail if base else None
    except Exception:
        return None


def resolve_file(name, recent=None):
    """'report.docx' -> its full path, from Windows' Recent files list."""
    d = Path(recent or recent_dir())
    if not d.is_dir():
        return None
    for cand in (d / f"{name}.lnk", d / f"{Path(name).stem}.lnk"):
        if cand.exists():
            t = lnk_target(cand)
            if t and Path(t).name.lower() == name.lower() and Path(t).exists():
                return t
    return None


def reopen_plan(sessions, max_files=6, max_apps=5, recent=None):
    """What was going on: files (with paths where Windows remembers them) and the apps they were in."""
    files = defaultdict(float)
    file_app = {}
    apps = defaultdict(float)
    for r in sessions:
        d = r["e"] - r["s"]
        apps[(r["app"], r["exe"])] += d
        for f in files_in(r["title"]):
            files[f] += d
            file_app[f] = r["exe"]
    plan, covered, missing = [], set(), []
    for f, secs in sorted(files.items(), key=lambda kv: -kv[1]):
        if len([p for p in plan if p["kind"] == "file"]) >= max_files or secs < 60:
            break
        p = resolve_file(f, recent)
        if p and Path(p).suffix.lower() not in NEVER_OPEN:
            plan.append({"kind": "file", "name": f, "path": p})
            covered.add(file_app.get(f))
        elif Path(f).suffix.lower() not in NEVER_OPEN:
            missing.append(f)
    for (app, exe), secs in sorted(apps.items(), key=lambda kv: -kv[1]):
        if len([p for p in plan if p["kind"] == "app"]) >= max_apps or secs < 120:
            break
        if exe in covered or exe in ("explorer.exe",):
            continue
        plan.append({"kind": "app", "name": app})
    return plan, missing


# ======================================================================== Windows: what's in front
def _idle_secs():
    if sys.platform != "win32":
        return 0.0
    import ctypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    li = LASTINPUTINFO()
    li.cbSize = ctypes.sizeof(li)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
        return 0.0
    return max(0, (ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000.0


def _sample():
    """(exe, app name, window title) for the window in front, or None when nothing should be logged."""
    if sys.platform != "win32":
        return None
    import ctypes
    import psutil
    u = ctypes.windll.user32
    h = u.GetForegroundWindow()
    if not h:
        return None
    n = u.GetWindowTextLengthW(h)
    buf = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, buf, n + 1)
    title = buf.value.strip()
    pid = ctypes.c_ulong()
    u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    try:
        exe = psutil.Process(pid.value).name().lower()
    except Exception:
        return None
    if pid.value == os.getpid():
        return None
    return judge(exe, title)


def judge(exe, title):
    """The privacy rules, in one place (also used by the tests)."""
    exe = (exe or "").lower()
    if not title or exe in SKIP_EXES or PRIVATE.search(title):
        return None
    try:
        import tools
        if title in tools.SELF_TITLES:
            return None
    except Exception:
        pass
    if title in ("Program Manager", "Task Switching", "Task View"):
        return None
    if exe == "applicationframehost.exe":                 # Store apps: the title is the app
        app = re.split(r"\s+[-–—|]\s+", title)[-1][:40]
    else:
        try:
            import closer
            app = closer._nice(exe)
        except Exception:
            app = exe.removesuffix(".exe").capitalize()
    hay = f"{exe} {app} {title}".lower()
    if any(w in hay for w in skip_words()):
        return None
    return exe, app, title
