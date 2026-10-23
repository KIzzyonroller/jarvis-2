"""
Long-term conversation memory: everything you and he say (and Discord messages he sees), kept in a
small searchable database on your PC (Documents\\Jarvis\\history.db). He searches it when you refer to
something from an earlier conversation ("what was that game Alex recommended?", "what did we decide
about the Blender model last week?").

  * Local only. Nothing is sent anywhere until he searches it to answer you, and then only the matches.
  * Anything that looks like a password, API key or card number is blanked out before it's saved.
  * Kept for JARVIS_HISTORY_DAYS (default 365) days. "Delete my conversation history" wipes it.
"""
import re
import sqlite3
import threading
import time

import config

REDACT = [
    (re.compile(r"\b(sk-ant-[\w-]{10,}|sk-[\w-]{20,}|gsk_[\w-]{20,}|ghp_[\w]{20,}|xox[abpr]-[\w-]{10,}|AKIA[0-9A-Z]{16})\b"), "[key removed]"),
    (re.compile(r"(?i)\b(password|passcode|pin|passwd)\s*(is|:|=)\s*\S+"), r"\1 \2 [removed]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[number removed]"),
]
STOP = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "was", "what", "that", "this", "it", "me",
        "my", "you", "we", "i", "did", "do", "about", "with", "at", "be", "are", "from", "by", "last", "week", "time"}


def redact(text):
    for pat, rep in REDACT:
        text = pat.sub(rep, text)
    return text


class History:
    def __init__(self, path=None):
        self.path = path or (config.JARVIS_DIR / "history.db")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(self.path), check_same_thread=False, timeout=5)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, ts REAL, who TEXT, text TEXT)")
        self.fts = True
        try:
            self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(text, who, content='messages', content_rowid='id')")
            self.db.executescript("""
                CREATE TRIGGER IF NOT EXISTS m_ai AFTER INSERT ON messages BEGIN
                  INSERT INTO messages_fts(rowid, text, who) VALUES (new.id, new.text, new.who); END;
                CREATE TRIGGER IF NOT EXISTS m_ad AFTER DELETE ON messages BEGIN
                  INSERT INTO messages_fts(messages_fts, rowid, text, who) VALUES ('delete', old.id, old.text, old.who); END;""")
        except sqlite3.OperationalError:
            self.fts = False                      # this Python's SQLite has no full-text search: plain matching
        self.db.commit()
        self._last = None
        self.prune()

    def add(self, who, text, ts=None):
        text = redact((text or "").strip())
        if not text or len(text) < 2:
            return
        key = (who, text)
        if self._last and self._last[0] == key and time.time() - self._last[1] < 3:
            return                                # the same line reported twice
        self._last = (key, time.time())
        with self.lock:
            self.db.execute("INSERT INTO messages (ts, who, text) VALUES (?,?,?)", (ts or time.time(), who, text[:4000]))
            self.db.commit()

    def prune(self):
        days = getattr(config, "HISTORY_DAYS", 365)
        if days and days > 0:
            with self.lock:
                self.db.execute("DELETE FROM messages WHERE ts < ?", (time.time() - days * 86400,))
                self.db.commit()

    def clear(self):
        with self.lock:
            self.db.execute("DELETE FROM messages")
            if self.fts:
                self.db.execute("INSERT INTO messages_fts(messages_fts) VALUES ('rebuild')")
            self.db.commit()
            self.db.execute("VACUUM")

    def count(self):
        return self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    def search(self, query, days=None, who=None, limit=10):
        """Best matches, each with the line right after it (usually the answer), newest first among equals."""
        words = [w for w in re.findall(r"[\w']+", (query or "").lower()) if w not in STOP and len(w) > 1]
        since = time.time() - days * 86400 if days else 0
        rows = []
        with self.lock:
            if words and self.fts:
                q = " OR ".join('"' + w.replace('"', "") + '"*' for w in words[:8])
                sql = ("SELECT m.id, m.ts, m.who, m.text FROM messages_fts f JOIN messages m ON m.id = f.rowid "
                       "WHERE messages_fts MATCH ? AND m.ts >= ? ORDER BY bm25(messages_fts) + (? - m.ts) / 8640000.0 LIMIT ?")
                rows = self.db.execute(sql, (q, since, time.time(), limit * 3)).fetchall()
            elif words:
                cond = " OR ".join("LOWER(text) LIKE ?" for _ in words[:8])
                rows = self.db.execute(f"SELECT id, ts, who, text FROM messages WHERE ({cond}) AND ts >= ? ORDER BY ts DESC LIMIT ?",
                                       [f"%{w}%" for w in words[:8]] + [since, limit * 3]).fetchall()
            else:                                 # no keywords: just the most recent conversation
                rows = self.db.execute("SELECT id, ts, who, text FROM messages WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
                                       (since, limit)).fetchall()
            if who:
                w = who.lower()
                rows = [r for r in rows if w in r[2].lower()]
            out, seen = [], set()
            for rid, ts, wh, tx in rows:
                if rid in seen:
                    continue
                seen.add(rid)
                nxt = self.db.execute("SELECT id, ts, who, text FROM messages WHERE id > ? ORDER BY id LIMIT 1", (rid,)).fetchone()
                item = {"ts": ts, "who": wh, "text": tx}
                if nxt and nxt[1] - ts < 600 and nxt[2] != wh:
                    item["reply"] = {"who": nxt[2], "text": nxt[3]}
                    seen.add(nxt[0])
                out.append(item)
                if len(out) >= limit:
                    break
        return out


def as_text(items, query=""):
    if not items:
        return f"Nothing in past conversations matches '{query}'." if query else "No past conversations saved yet."
    lines = []
    for it in items:
        when = time.strftime("%a %b %d %H:%M", time.localtime(it["ts"]))
        line = f"[{when}] {it['who']}: {it['text'][:400]}"
        if it.get("reply"):
            line += f"\n    -> {it['reply']['who']}: {it['reply']['text'][:300]}"
        lines.append(line)
    return "From past conversations (newest matches may be most relevant):\n" + "\n".join(lines)
