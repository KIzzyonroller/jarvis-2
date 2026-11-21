"""
"What he knows about you": every single thing he keeps, in one place, where you can read it, change it or delete it.

Settings > What he knows (or "show me everything you know about me"). Each section says where it's stored, and
nothing here is ever sent anywhere: it's all files in Documents\\Jarvis on this PC (plus his settings file).
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

import config


def _n(x):
    return len(x) if x else 0


def _safe(fn, default=None):
    try:
        return fn()
    except Exception as e:
        print(f"[knows] {e}")
        return default


def sections(core=None):
    """[{id, title, about, where, items: [{id, text, sub, editable}], actions: [...]}]"""
    import tools
    out = []
    mem = _safe(tools.memories, []) or []
    out.append({"id": "memory", "title": "Things he remembers", "where": "memory.json",
                "about": "Facts about you he uses in every conversation.",
                "items": [{"id": m["id"], "text": m["text"], "sub": (m.get("added") or "")[:10], "editable": True}
                          for m in reversed(mem)], "actions": ["clear"]})
    import extras
    lingo = _safe(extras.lingo, {}) or {}
    out.append({"id": "lingo", "title": "Your words", "where": "lingo.json", "about": "Your slang and nicknames.",
                "items": [{"id": k, "text": f"“{k}” = {v['means']}", "sub": v.get("added", ""), "editable": True,
                           "value": v["means"]} for k, v in lingo.items()], "actions": ["clear"]})
    jokes = _safe(extras.jokes, []) or []
    out.append({"id": "jokes", "title": "Inside jokes", "where": "jokes.json", "about": "Things that made you both laugh.",
                "items": [{"id": j["id"], "text": j["text"], "sub": j.get("added", "")} for j in jokes], "actions": ["clear"]})
    import birthdays
    bd = _safe(birthdays._load, []) or []
    out.append({"id": "birthdays", "title": "Birthdays", "where": "birthdays.json", "about": "People's birthdays he reminds you about.",
                "items": [{"id": b["name"], "text": f"{b['name']}: {b.get('month')}/{b.get('day')}" + (f" ({b['note']})" if b.get("note") else ""),
                           "sub": ""} for b in bd], "actions": []})
    rt = _safe(tools.routines, {}) or {}
    out.append({"id": "routines", "title": "Routines", "where": "routines.json", "about": "Your own commands: say the name and he does the steps.",
                "items": [{"id": k, "text": k, "sub": (v if isinstance(v, str) else json.dumps(v))[:160]} for k, v in rt.items()], "actions": []})
    words = _safe(lambda: tools.VOCAB.load() or [], []) or []
    out.append({"id": "words", "title": "Words he listens for", "where": "vocab.json",
                "about": "Names and words he's learned to hear right.", "items": [{"id": w, "text": w, "sub": ""} for w in words],
                "actions": ["clear"]})
    import triggers
    tr = _safe(triggers.load, []) or []
    out.append({"id": "triggers", "title": "Triggers", "where": "triggers.json", "about": "Things he does by himself.",
                "items": [{"id": r["id"], "text": triggers.describe(r), "sub": ""} for r in tr], "actions": []})
    import pricewatch
    pw = _safe(pricewatch._load, []) or []
    out.append({"id": "prices", "title": "Price watches", "where": "price_watch.json", "about": "Prices he's keeping an eye on.",
                "items": [{"id": w["id"], "text": w["label"], "sub": w["target"][:80]} for w in pw], "actions": []})
    import voiceid
    vs = _safe(voiceid.status, {}) or {}
    guests = list((_safe(voiceid.guests, {}) or {}).keys())
    vitems = ([{"id": "owner", "text": "Your voiceprint", "sub": "256 numbers describing your voice, not a recording"}]
              if vs.get("enrolled") else []) + [{"id": g, "text": f"{g}'s voiceprint (guest)", "sub": ""} for g in guests]
    out.append({"id": "voices", "title": "Voices", "where": "voice_id.json, voice_guests.json",
                "about": "Used to tell your voice from other people's. No recordings are kept.", "items": vitems, "actions": []})
    hist_n = _safe(lambda: core.history.count() if core is not None and getattr(core, "history", None) else 0, 0)
    out.append({"id": "history", "title": "Conversation history", "where": "history.db",
                "about": f"Every line you've said to each other ({hist_n:,} lines), so he can find past conversations.",
                "items": [], "count": hist_n, "actions": ["clear"]})
    act_dir = config.JARVIS_DIR / "activity"
    days = sorted(act_dir.glob("*.jsonl")) if act_dir.exists() else []
    out.append({"id": "activity", "title": "Activity memory", "where": "activity\\",
                "about": f"Which apps and windows you used and when ({len(days)} days kept), for \"what was I doing\".",
                "items": [], "count": len(days), "actions": ["clear"]})
    import shotsearch
    shots = _safe(shotsearch._load, {}) or {}
    out.append({"id": "shots", "title": "Screenshot text", "where": "screenshot_index.json",
                "about": f"The words read from {len(shots)} of your screenshots (not the pictures).", "items": [],
                "count": len(shots), "actions": ["clear"]})
    import cliphist
    out.append({"id": "clips", "title": "Clipboard history", "where": "memory only",
                "about": f"{len(cliphist.ITEMS)} recent copies, gone when he closes.", "items": [], "count": len(cliphist.ITEMS),
                "actions": ["clear"]})
    import gamemode
    plays = _safe(gamemode._read_play, []) or []
    out.append({"id": "play", "title": "Play time", "where": "play_log.jsonl", "about": f"{len(plays)} game sessions and results.",
                "items": [], "count": len(plays), "actions": ["clear"]})
    jdir = config.JARVIS_DIR / "Jarvis Journal.txt"
    out.append({"id": "journal", "title": "Journal", "where": "Jarvis Journal.txt", "about": "Your journal entries (yours to keep: open it to edit).",
                "items": [], "count": 1 if jdir.exists() else 0, "actions": ["open"]})
    crashes = list((config.JARVIS_DIR / "crashes").glob("*.json")) if (config.JARVIS_DIR / "crashes").exists() else []
    out.append({"id": "crashes", "title": "Crash reports", "where": "crashes\\", "about": f"{len(crashes)} saved (never sent unless you send them).",
                "items": [], "count": len(crashes), "actions": ["clear"]})
    return out


def act(core, section, action, item=None, value=None):
    """Delete / edit / clear one thing. Returns a short message."""
    import tools
    s, a = section, action
    if s == "memory":
        if a == "delete":
            return tools.forget(item)
        if a == "edit":
            return tools.edit_memory(item, value)
        if a == "clear":
            return tools.forget("everything")
    if s == "lingo":
        import extras
        if a == "delete":
            return extras.lingo_tool("remove", item)
        if a == "edit":
            return extras.lingo_tool("add", item, value)
        if a == "clear":
            (config.JARVIS_DIR / "lingo.json").unlink(missing_ok=True)
            return "Cleared."
    if s == "jokes":
        import extras
        if a == "delete":
            return extras.joke_tool("remove", id=item)
        if a == "clear":
            (config.JARVIS_DIR / "jokes.json").unlink(missing_ok=True)
            return "Cleared."
    if s == "birthdays" and a == "delete":
        import birthdays
        return birthdays.remove(item)
    if s == "routines" and a == "delete":
        return tools.delete_routine(item)
    if s == "words":
        with tools.VOCAB.lock:
            words = tools.VOCAB.load() or []
            tools.VOCAB.save([] if a == "clear" else [w for w in words if w != item])
        tools._VOCAB_CACHE["t"] = 0
        return "Removed."
    if s == "triggers" and a == "delete":
        import triggers
        return triggers.remove(item)
    if s == "prices" and a == "delete":
        import pricewatch
        return pricewatch.remove(item)
    if s == "voices" and a == "delete":
        import voiceid
        if item == "owner":
            voiceid.forget()
            return "Forgot your voice."
        return voiceid.forget_guest(item)
    if s == "history" and a == "clear" and core is not None and getattr(core, "history", None):
        core.history.clear()
        return "Conversation history erased."
    if s == "activity" and a == "clear" and core is not None:
        core.activity_action("wipe", None)          # asks you first, then says what happened
        return ""
    if s == "shots" and a == "clear":
        (config.JARVIS_DIR / "screenshot_index.json").unlink(missing_ok=True)
        return "Screenshot text erased (he'll re-read them over time unless you switch it off in Settings)."
    if s == "clips" and a == "clear":
        import cliphist
        return cliphist.tool("clear")
    if s == "play" and a == "clear":
        (config.JARVIS_DIR / "play_log.jsonl").unlink(missing_ok=True)
        return "Play time erased."
    if s == "crashes" and a == "clear":
        import crashreport
        return crashreport.tool("clear")
    if s == "plugins":
        import plugins
        if a == "enable":
            return plugins.enable(item, tools._confirm)
        if a == "disable":
            return plugins.disable(item) + " (Takes effect when he restarts.)"
        if a == "folder":
            return plugins.tool("folder")
    if s == "journal" and a == "open":
        p = config.JARVIS_DIR / "Jarvis Journal.txt"
        if p.exists():
            os.startfile(str(p))
            return "Opened."
        return "No journal yet."
    return "Can't do that here."


def summary(core=None):
    """For 'what do you know about me': counts plus the memories themselves."""
    secs = sections(core)
    parts = []
    for s in secs:
        n = len(s["items"]) if s["items"] else s.get("count", 0)
        if n:
            parts.append(f"{s['title'].lower()}: {n}")
    mem = next(s for s in secs if s["id"] == "memory")["items"]
    return ("Everything I keep, all on this PC: " + "; ".join(parts) + ". " +
            ("What I remember about you: " + "; ".join(m["text"] for m in mem[:40]) + "." if mem else "") +
            " All of it is in Settings > What he knows, where they can edit or delete any of it.")
