"""
Discord messages, read from Windows' own notification store.

Why this way: Discord doesn't let apps read your messages unless you run a "self-bot" on your account,
which breaks Discord's rules and can get it banned. But Discord already shows your messages as Windows
notifications, and Windows keeps those in a small database on your PC
(%LOCALAPPDATA%\\Microsoft\\Windows\\Notifications\\wpndatabase.db). Jarvis reads new Discord
entries from there. Nothing is logged into, and nothing leaves your PC unless you ask him a question
about a message (then that message goes to Claude to answer you).

What he sees is exactly what pops up for you: DMs, group chats and pings, depending on Discord's own
notification settings. Discord only sends notifications when you're not looking at Discord, so a chat
you have open won't be read out (same as it doesn't pop up).
"""
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET
from pathlib import Path

APPS = ("discord",)                       # Discord, Discord PTB, Discord Canary
EPOCH_DELTA = 11644473600                 # seconds between 1601 (Windows FILETIME) and 1970


def db_path():
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "Microsoft" / "Windows" / "Notifications" / "wpndatabase.db"


def _filetime(v):
    try:
        return int(v) / 1e7 - EPOCH_DELTA
    except (TypeError, ValueError):
        return time.time()


def parse_payload(payload):
    """Toast XML -> (title, body). Discord: title = who (and where), body = the message."""
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", "replace")
    try:
        root = ET.fromstring(payload)
        texts = [("".join(t.itertext()) or "").strip() for t in root.iter("text")]
    except ET.ParseError:                 # malformed XML: still get the text out rather than drop the message
        import html
        texts = [html.unescape(re.sub(r"<[^>]*>", "", t)).strip()
                 for t in re.findall(r"<text[^>]*>(.*?)</text>", payload, re.S)]
    texts = [t for t in texts if t]
    if not texts:
        return None, None
    return texts[0], " ".join(texts[1:]).strip()


def split_sender(title):
    """'Alex (#general, My Server)' -> ('Alex', 'general'); 'Alex' -> ('Alex', None)."""
    m = re.match(r"^(.*?)\s*\((#?[^,)]+)(?:,\s*([^)]+))?\)\s*$", title or "")
    if m:
        return m.group(1).strip() or title, m.group(2).lstrip("#").strip()
    return (title or "Someone").strip(), None


def speakable(text, words=24):
    """Make a message sound right out loud: links, mentions and emoji codes tidied, length capped."""
    t = re.sub(r"https?://\S+", "a link", text or "")
    t = re.sub(r"<a?:(\w+):\d+>|:(\w+):", lambda m: (m.group(1) or m.group(2)).replace("_", " "), t)
    t = re.sub(r"<@!?\d+>", "someone", t)
    t = re.sub(r"\s+", " ", t).strip()
    w = t.split()
    return " ".join(w[:words]) + ("..." if len(w) > words else "") if w else "sent something"


class DiscordWatcher:
    """Polls the notification store every few seconds. on_message(msg) for each new Discord message.
    msg = {"id", "time", "sender", "channel", "text"}."""

    def __init__(self, on_message=None, poll=3.0, log=print):
        self.on_message = on_message or (lambda m: None)
        self.poll = poll
        self.log = log
        self.path = db_path()
        self.last_id = None
        self.recent = []                  # the last day of messages, for "what did I miss"
        self.read_upto = time.time()      # "what did I miss" starts from here
        self._sig = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.ok = sys.platform == "win32" and self.path.exists()

    # ---------------------------------------------------------------- reading the store
    def _connect(self):
        """Read-only straight from the live file; if Windows has it locked, read a quick copy."""
        try:
            con = sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro", uri=True, timeout=2)
            con.execute("SELECT 1 FROM Notification LIMIT 1")
            return con, None
        except sqlite3.Error:
            pass
        tmp = Path(tempfile.mkdtemp(prefix="jarvis-wpn-"))
        for suffix in ("", "-wal", "-shm"):
            src = Path(str(self.path) + suffix)
            if src.exists():
                try:
                    shutil.copy2(src, tmp / (self.path.name + suffix))
                except OSError:
                    pass
        return sqlite3.connect(str(tmp / self.path.name), timeout=2), tmp

    def fetch(self, after_id):
        con, tmp = self._connect()
        try:
            rows = con.execute(
                "SELECT n.Id, n.ArrivalTime, n.Payload, h.PrimaryId FROM Notification n "
                "JOIN NotificationHandler h ON n.HandlerId = h.RecordId "
                "WHERE n.Id > ? AND (n.Type IS NULL OR n.Type = 'toast') ORDER BY n.Id", (after_id or 0,)).fetchall()
        finally:
            con.close()
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)
        out = []
        for nid, arrival, payload, app in rows:
            if not any(a in str(app or "").lower() for a in APPS):
                continue
            title, body = parse_payload(payload)
            if not title:
                continue
            sender, channel = split_sender(title)
            out.append({"id": int(nid), "time": _filetime(arrival), "sender": sender, "channel": channel, "text": body or ""})
        max_id = max([int(r[0]) for r in rows], default=after_id or 0)
        return out, max_id

    def _changed(self):
        sig = []
        for suffix in ("", "-wal"):
            try:
                st = os.stat(str(self.path) + suffix)
                sig.append((st.st_mtime_ns, st.st_size))
            except OSError:
                sig.append(None)
        if sig == self._sig:
            return False
        self._sig = sig
        return True

    # ---------------------------------------------------------------- running
    def start(self):
        if not self.ok:
            return False
        try:                              # remember the last day, but only announce what's new from now on
            msgs, max_id = self.fetch(0)
            self.recent = [m for m in msgs if time.time() - m["time"] < 86400][-200:]
            self.last_id = max_id
        except Exception as e:
            self.log(f"[discord] can't read Windows notifications: {type(e).__name__}: {e}")
            self.ok = False
            return False
        threading.Thread(target=self._loop, daemon=True, name="discord-watch").start()
        return True

    def _loop(self):
        fails = 0
        while not self._stop.wait(self.poll):
            try:
                if not self._changed():
                    continue
                msgs, self.last_id = self.fetch(self.last_id)
                fails = 0
            except Exception as e:
                fails += 1
                if fails in (1, 20):
                    self.log(f"[discord] notification read failed ({type(e).__name__}); will keep trying")
                continue
            for m in msgs:
                with self._lock:
                    self.recent = (self.recent + [m])[-200:]
                try:
                    self.on_message(m)
                except Exception as e:
                    self.log(f"[discord] announce failed: {e}")

    def stop(self):
        self._stop.set()

    # ---------------------------------------------------------------- questions
    def since(self, t):
        with self._lock:
            return [m for m in self.recent if m["time"] >= t]

    def unread(self, mark=True):
        msgs = self.since(self.read_upto)
        if mark:
            self.read_upto = time.time()
        return msgs

    def search(self, who=None, hours=24, limit=15):
        msgs = self.since(time.time() - hours * 3600)
        if who:
            w = who.lower()
            msgs = [m for m in msgs if w in m["sender"].lower() or w in (m["channel"] or "").lower()]
        return msgs[-limit:]


def summary(msgs, max_items=4):
    """Spoken roundup: 'Three Discord messages: Alex said ..., Sam said ...'."""
    if not msgs:
        return "No new Discord messages."
    by = []
    for m in msgs:
        if m["sender"] not in by:
            by.append(m["sender"])
    n = len(msgs)
    head = f"{n} Discord message{'s' if n != 1 else ''}"
    if n <= max_items:
        parts = [f"{m['sender']}{' in ' + m['channel'] if m['channel'] else ''} said: {speakable(m['text'], 16)}" for m in msgs]
        return head + ". " + " ".join(p if p.endswith((".", "!", "?", "...")) else p + "." for p in parts)
    names = ", ".join(by[:3]) + (f" and {len(by) - 3} others" if len(by) > 3 else "")
    last = msgs[-1]
    return f"{head}, from {names}. The latest, from {last['sender']}: {speakable(last['text'], 16)}"


def as_text(msgs):
    """For Claude (only when you ask about them)."""
    if not msgs:
        return "No Discord messages found in Windows notifications for that."
    lines = []
    for m in msgs:
        when = time.strftime("%a %H:%M", time.localtime(m["time"]))
        lines.append(f"[{when}] {m['sender']}{' (#' + m['channel'] + ')' if m['channel'] else ''}: {m['text']}")
    return "Discord messages (from Windows notifications; only what popped up for the user):\n" + "\n".join(lines)
