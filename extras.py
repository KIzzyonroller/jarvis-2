"""
Smaller things he does on his own, kept out of moments.py so that file stays readable.

  * Ambient lines: now and then, one line that fits his scene (the station, the archive...), the time and the weather.
    Rare by default, never mid-game, mid-call, while muted, in quiet hours or while you're typing hard.
  * The weekly letter: Sunday evening he writes you a letter about your week (a Word file on your desktop),
    pulls it up, and says one line about it.
  * Inside jokes: things that made you both laugh, remembered so he can bring them back (sparingly).
"""
import json
import os
import random
import re
import threading
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import config

CORE = None


def _write(system, ask, model=None, max_tokens=200):
    """One short text from Claude, no tools. None on any failure."""
    import usage
    client = getattr(getattr(CORE, "brain", None), "client", None)
    if client is None:
        return None
    model = model or config.FAST_MODEL or config.MODEL
    try:
        msg = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                     messages=[{"role": "user", "content": ask}])
        try:
            usage.record_claude(model, msg.usage)
        except Exception:
            pass
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    except Exception as e:
        print(f"[extras] {e}")
        return None
    return None if not text or text.upper().startswith("SKIP") else text


def _flag(key, value=None):
    try:
        return CORE._state_flag(key) if value is None else CORE._state_flag(key, value)
    except Exception:
        return None


# ================================================================== inside jokes
def _jokes_file():
    return config.JARVIS_DIR / "jokes.json"


def jokes():
    try:
        return json.loads(_jokes_file().read_text(encoding="utf-8"))
    except Exception:
        return []


def joke_tool(action="list", text=None, id=None):
    a = (action or "list").lower()
    items = jokes()
    if a == "add":
        t = " ".join(str(text or "").split())[:200]
        if not t:
            return "What's the joke? (Short: what it's about and why it's funny.)"
        items = [j for j in items if j["text"].lower() != t.lower()]
        items.append({"id": uuid.uuid4().hex[:5], "text": t, "added": date.today().isoformat(), "used": 0})
        _jokes_file().write_text(json.dumps(items[-60:], indent=1), encoding="utf-8")
        return "Saved as an inside joke. Use it rarely: once it's forced it's dead."
    if a == "remove":
        q = (id or text or "").lower()
        keep = [j for j in items if j["id"] != q and q not in j["text"].lower()]
        _jokes_file().write_text(json.dumps(keep, indent=1), encoding="utf-8")
        return "Dropped." if len(keep) < len(items) else "No joke like that saved."
    if a == "used":
        for j in items:
            if j["id"] == id or (text and text.lower() in j["text"].lower()):
                j["used"] = j.get("used", 0) + 1
                j["last"] = time.time()
        _jokes_file().write_text(json.dumps(items, indent=1), encoding="utf-8")
        return "Noted."
    if not items:
        return "No inside jokes saved yet."
    return "Inside jokes: " + "; ".join(f"[{j['id']}] {j['text']}" for j in items)


def jokes_note():
    """For the stable part of the system prompt: the running jokes, freshest first, ones used lately left out."""
    items = [j for j in jokes() if time.time() - j.get("last", 0) > 2 * 86400]
    if not items:
        return ""
    items = sorted(items, key=lambda j: j.get("used", 0))[:12]
    return ("\n\nINSIDE JOKES you share with them (bring ONE back only when it genuinely fits, maybe once a day at "
            "most; never explain it; then call jokes action used): " + "; ".join(f"[{j['id']}] {j['text']}" for j in items))


# ================================================================== their slang and nicknames
def _lingo_file():
    return config.JARVIS_DIR / "lingo.json"


def lingo():
    try:
        return json.loads(_lingo_file().read_text(encoding="utf-8"))
    except Exception:
        return {}


def lingo_tool(action="list", term=None, meaning=None):
    """Their words: 'the squad' = Leo, Ana and Max; 'my main' = Wraith in Apex; 'the spot' = the taco place."""
    a = (action or "list").lower()
    items = lingo()
    if a == "add":
        t = " ".join(str(term or "").lower().split())[:40]
        m = " ".join(str(meaning or "").split())[:200]
        if not t or not m:
            return "Which word, and what does it mean to them?"
        items[t] = {"means": m, "added": date.today().isoformat()}
        _lingo_file().write_text(json.dumps(items, indent=1), encoding="utf-8")
        try:
            import tools
            if len(t.split()) <= 4 and not t.isascii() or any(ch.isupper() for ch in (term or "")):
                tools.learn_word(term)                # names: listen for the spelling too
        except Exception:
            pass
        return f"Got it: \"{t}\" means {m}."
    if a == "remove":
        t = " ".join(str(term or "").lower().split())
        if items.pop(t, None) is None:
            return f"I don't have \"{t}\" saved."
        _lingo_file().write_text(json.dumps(items, indent=1), encoding="utf-8")
        return f"Forgot \"{t}\"."
    if not items:
        return "No slang or nicknames saved yet."
    return "Their words: " + "; ".join(f"\"{k}\" = {v['means']}" for k, v in items.items())


def lingo_note():
    items = lingo()
    if not items:
        return ""
    return ("\n\nTHEIR WORDS (their slang and nicknames; understand them, and use them back naturally when it fits): " +
            "; ".join(f"\"{k}\" = {v['means']}" for k, v in list(items.items())[:60]))


# ================================================================== ambient lines
def _ambient_gap():
    if config.LITE:
        return 0
    m = os.environ.get("JARVIS_AMBIENT", "rare").lower()
    return {"off": 0, "rare": 4 * 3600, "sometimes": 100 * 60}.get(m, 4 * 3600)


def ambient(core):
    """Returns True when it said something."""
    gap = _ambient_gap()
    if not gap:
        return False
    now = time.time()
    try:
        last = float(_flag("ambient_at") or 0)
    except (TypeError, ValueError):
        last = 0
    if now - last < gap * random.uniform(0.8, 1.4):
        return False
    import moments
    import personas
    if moments._busy_or_away(core, (20, 900)):         # not while you're actively typing, not when you've gone
        return False
    _flag("ambient_at", str(now))
    lore = personas.LORE.get(config.DESK_SCENE, "")
    try:
        import deskfacts
        facts = deskfacts.gather(core).get(config.DESK_SCENE, {})
    except Exception:
        facts = {}
    ask = (f"[Ambient line. Nobody asked you anything. It's {datetime.now():%A %I:%M %p}. Your world right now: {lore} "
           f"Live details: {json.dumps(facts)[:400]}. Say ONE short line (under 20 words) that fits that world and the "
           "moment, like something you'd mutter while working: an observation, a small event in your scene, a dry "
           "remark. Not a question that needs an answer. No greetings, no 'just checking in'. If nothing good comes, "
           "reply SKIP.]")
    line = _write(personas.character(config.ADDRESS_AS) + "\nSpoken aloud: plain words only.", ask, max_tokens=60)
    if not line:
        return False
    core.events.put(("moment", {"line": line, "cards": []}))
    return True


# ================================================================== weekly letter
def _week_facts(core):
    facts = []
    end = datetime.now()
    start = end - timedelta(days=7)
    act = getattr(core, "activity", None)
    if act is not None:
        try:
            import activity
            facts.append("PC TIME THIS WEEK:\n" + activity.summarize(act.sessions(start, end), "this week", start, end))
        except Exception:
            pass
    try:
        import gamemode
        if gamemode.WATCH is not None:
            s = gamemode.WATCH.stats(days=7)
            if s["minutes"]:
                facts.append(f"GAMING: {s['minutes'] // 60}h {s['minutes'] % 60}m; " +
                             ", ".join(f"{g} {m}m" for g, m in list(s["games"].items())[:5]) +
                             (f"; results they told you about: {s['wins']}W {s['losses']}L" if s["wins"] or s["losses"] else ""))
    except Exception:
        pass
    h = getattr(core, "history", None)
    if h is not None:
        try:
            rows = [r for r in h.search("", days=7, who="You", limit=200) if r["ts"] >= start.timestamp()]
            if rows:
                facts.append("THINGS THEY SAID TO YOU THIS WEEK (sample):\n" +
                             "\n".join(f"- {datetime.fromtimestamp(r['ts']):%a}: {r['text'][:140]}" for r in rows[:40]))
        except Exception:
            pass
    try:
        import journal
        j = journal.read(7)
        if j and "empty" not in j[:40]:
            facts.append("THEIR JOURNAL THIS WEEK:\n" + j[:3000])
    except Exception:
        pass
    try:
        import stocks
        facts.append("PAPER PORTFOLIO: " + stocks.paper_report())
    except Exception:
        pass
    try:
        import birthdays
        facts.append("BIRTHDAYS COMING: " + birthdays.upcoming(3))
    except Exception:
        pass
    return "\n\n".join(facts)


def letter(core, force=False):
    """Write the letter now. Returns (message, path or None)."""
    import personas
    facts = _week_facts(core)
    if not facts.strip():
        return "There's not enough from this week to write about (activity memory and history are both empty).", None
    ask = ("Write your weekly letter to them, from you, about their week. Facts you have:\n\n" + facts[:14000] +
           "\n\nWrite it like a real letter from someone who's been in the room all week: 250 to 450 words, warm but "
           "honest, specific (use real details from above, not generic praise), a bit of humour, one or two honest "
           "observations they might not want to hear (too many late nights, a game that's clearly tilting them, "
           "something they keep putting off), and one thing to look forward to next week. No headings, no bullet "
           "points, no em dashes. Start with 'Dear' and their name or how you address them, sign off as yourself. "
           "Never invent events that aren't in the facts.")
    text = _write(personas.character(config.ADDRESS_AS), ask, model=config.MODEL, max_tokens=900)
    if not text:
        return "Couldn't write the letter (Claude didn't answer).", None
    text = text.replace("—", ", ").replace("–", "-")
    try:
        import documents
        desk = Path(os.path.expanduser("~")) / "Desktop"
        if not desk.exists():
            desk = config.JARVIS_DIR
        path = desk / f"Letter from Jarvis - {date.today():%B %d}.docx"
        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        path = documents.make("docx", str(path), {"title": f"Week of {(date.today() - timedelta(days=6)):%B %d}",
                                                  "blocks": [{"p": x} for x in paras]})
    except Exception as e:
        print(f"[letter] couldn't save docx: {e}")
        path = config.JARVIS_DIR / f"letter-{date.today():%Y-%m-%d}.txt"
        path.write_text(text, encoding="utf-8")
    try:
        import pulls
        pulls.file(path, path.suffix.lstrip("."), text=text)
    except Exception as e:
        print(f"[letter] preview: {e}")
    return f"Letter written: {path}", path


def weekly_letter(core):
    """Sunday from 6pm, once. True when it ran."""
    if os.environ.get("JARVIS_LETTER", "true").lower() == "false":
        return False
    now = datetime.now()
    if now.weekday() != 6 or now.hour < 18:
        return False
    day = now.strftime("%Y-%m-%d")
    if _flag("letter_written") == day:
        return False
    import moments
    if moments._busy_or_away(core, (3, 600)):
        return False
    _flag("letter_written", day)

    def run():
        msg, path = letter(core)
        print(f"[letter] {msg}")
        if path:
            core.events.put(("moment", {"line": "I wrote you a letter about your week. It's on your desktop, take a look "
                                                "when you've got a minute.", "cards": []}))
    threading.Thread(target=run, daemon=True, name="weekly-letter").start()
    return True


def start(core):
    global CORE
    CORE = core
