"""
Her journal for you: a plain text file on your desktop ("Juno Journal.txt") that you can open, edit, or delete
any time.

  * Once a day (from the hour you pick, 10 PM by default) she asks you one question about your day. Your answer goes
    in the file under today's date, in your words. "Skip" or "not tonight" and nothing's written.
  * "Journal: today I finally finished the hallway scene" adds an entry whenever you like.
  * "What did I write last week?" / "when did I start the Unreal project?" - she reads it back and searches it.

Nothing leaves the PC except what she reads to answer you (like any other conversation). Anyone at your PC can open
the file, so don't keep anything in it you wouldn't want seen.
"""
import random
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import config

QUESTIONS = [
    "What was the best part of today?",
    "Anything today you'd do differently?",
    "What did you get done today that you're glad about?",
    "What's on your mind tonight?",
    "Who made today better, even a little?",
    "What's one thing you want to remember about today?",
    "What annoyed you today? Get it out.",
    "What are you looking forward to tomorrow?",
    "Rate today out of ten. Why that number?",
    "Learn anything new today?",
]
HEADER = re.compile(r"^== (.+) ==$")


def desktop():
    """The real Desktop folder (it moves into OneDrive when OneDrive backup is on)."""
    try:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf) == 0 and buf.value:   # CSIDL_DESKTOPDIRECTORY
            return Path(buf.value)
    except Exception:
        pass
    for p in (config.HOME / "OneDrive" / "Desktop", config.HOME / "Desktop"):
        if p.is_dir():
            return p
    return config.HOME


def path():
    custom = (config.JOURNAL_FILE or "").strip().strip('"')
    if custom:
        return Path(custom).expanduser()
    return desktop() / "Juno Journal.txt"


def _day_title(d):
    return d.strftime("%A, %B ") + str(d.day) + d.strftime(", %Y")


def add(text, question=None, when=None):
    """Append an entry under today's date (the date heading is added once a day)."""
    text = (text or "").strip()
    if not text:
        return "Nothing to write."
    when = when or datetime.now()
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    title = f"== {_day_title(when.date())} =="
    old = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    chunk = ""
    if title not in old:
        chunk += ("\n" if old and not old.endswith("\n\n") else "") + title + "\n"
    stamp = when.strftime("%I:%M %p").lstrip("0")
    if question:
        chunk += f"[{stamp}] {question}\n{text}\n\n"
    else:
        chunk += f"[{stamp}] {text}\n\n"
    if not old:
        chunk = ("Juno's journal for you. Plain text: edit or delete anything. She adds to the bottom.\n\n" + chunk)
    with p.open("a", encoding="utf-8") as f:
        f.write(chunk)
    return f"Written in your journal ({p.name})."


def entries():
    """[(date, text)] parsed from the file."""
    p = path()
    if not p.exists():
        return []
    out, cur, buf = [], None, []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m = HEADER.match(line.strip())
        if m:
            if cur:
                out.append((cur, "\n".join(buf).strip()))
            try:
                cur = datetime.strptime(m.group(1), "%A, %B %d, %Y").date()
            except ValueError:
                cur = None
            buf = []
        elif cur:
            buf.append(line)
    if cur:
        out.append((cur, "\n".join(buf).strip()))
    return out


def read(days=7, search=None):
    es = entries()
    if not es:
        return f"The journal's empty so far ({path().name} on your desktop)."
    if search:
        s = search.lower()
        hits = [(d, t) for d, t in es if s in t.lower()]
        if not hits:
            return f"Nothing in the journal mentions '{search}'."
        es = hits[-10:]
    else:
        since = date.today() - timedelta(days=int(days or 7))
        es = [(d, t) for d, t in es if d >= since] or es[-3:]
    return "\n\n".join(f"{_day_title(d)}:\n{t}" for d, t in es)[:6000]


def written_today():
    return any(d == date.today() for d, _ in entries())


def question(core=None):
    """Tonight's question: one from the list, or (sometimes) one about something that actually happened today."""
    if core is not None and random.random() < 0.5:
        try:
            import moments
            apps = moments.today_on_pc(core)
            import gamemode
            last = gamemode.WATCH.last_session if gamemode.WATCH else None
            if last and last.get("ended", 0) > datetime.combine(date.today(), datetime.min.time()).timestamp() and last["minutes"] >= 30:
                return f"You played {last['name']} for a while today. How'd it go?"
            if apps and apps[0][1] >= 90:
                app, mins = apps[0]
                return f"You spent a lot of today in {app}. What were you working on?"
        except Exception:
            pass
    return random.choice(QUESTIONS)


def open_file():
    import os
    p = path()
    if not p.exists():
        add("Started the journal.")
    os.startfile(str(p))
    return f"Opened {p.name}."
