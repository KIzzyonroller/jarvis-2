"""
Changing their voices live: which voice, how fast, how deep. Per persona (Jarvis and Ultron separately), applied
the moment you change it (no restart), and remembered in Documents\\Jarvis\\voices.json.

From the Settings panel (Voice section, with a Preview button) or by asking: "Jarvis, talk a bit faster",
"use a deeper voice", "try an American voice", "put your voice back to normal".
Voice choice applies to the Kokoro voice (the normal one); speed and pitch apply to every engine he can use.
"""
import json
import re

import config
import personas

SPEED = (0.6, 1.6)
PITCH = (0.7, 1.3)
ACCENTS = {"a": "American", "b": "British", "e": "Spanish", "f": "French", "h": "Hindi", "i": "Italian",
           "j": "Japanese", "p": "Portuguese", "z": "Chinese"}
LANGS = {"a": "en-us", "b": "en-gb"}
_DEFAULTS = {k: {"voice": p.get("voice"), "speed": p.get("speed", 1.0), "pitch": p.get("pitch", 1.0), "lang": p.get("lang")}
             for k, p in personas.PERSONAS.items()}


def _path():
    return config.JARVIS_DIR / "voices.json"


def _load():
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(d):
    _path().parent.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps(d, indent=1), encoding="utf-8")


def describe(voice_id):
    """bm_lewis -> 'Lewis (British male)'."""
    m = re.match(r"^([a-z])([fm])_(\w+)$", voice_id or "")
    if not m:
        return voice_id
    accent = ACCENTS.get(m.group(1), m.group(1).upper())
    return f"{m.group(3).title()} ({accent} {'male' if m.group(2) == 'm' else 'female'})"


def english_voices(available):
    """The English voices (the others only work for their own languages)."""
    return sorted(v for v in (available or []) if re.match(r"^[ab][fm]_", v))


def apply_saved():
    """At startup: put the saved choices onto the personas."""
    for key, o in _load().items():
        if key in personas.PERSONAS:
            _apply(key, o)


def _apply(key, o):
    p = personas.PERSONAS[key]
    for k in ("voice", "speed", "pitch"):
        if o.get(k) is not None:
            p[k] = o[k]
    if o.get("voice"):
        p["lang"] = LANGS.get(o["voice"][0], p.get("lang"))


def current(key):
    p = personas.PERSONAS[key]
    return {"voice": p.get("voice"), "speed": round(float(p.get("speed", 1.0)), 2), "pitch": round(float(p.get("pitch", 1.0)), 2)}


def set_voice(key, voice=None, speed=None, pitch=None, available=None):
    """Returns (ok, message). Values are clamped to sensible ranges."""
    if key not in personas.PERSONAS:
        return False, f"There's no {key}."
    o = _load().get(key, {})
    if voice:
        v = voice.strip().lower()
        if available and v not in available:
            match = [a for a in english_voices(available) if v in a or v == a.split("_", 1)[-1]]
            if not match:
                return False, f"There's no voice called {voice}. Options: " + ", ".join(english_voices(available)[:20])
            v = match[0]
        o["voice"] = v
    if speed is not None:
        o["speed"] = round(min(max(float(speed), SPEED[0]), SPEED[1]), 2)
    if pitch is not None:
        o["pitch"] = round(min(max(float(pitch), PITCH[0]), PITCH[1]), 2)
    d = _load()
    d[key] = o
    _save(d)
    _apply(key, o)
    c = current(key)
    return True, f"{personas.PERSONAS[key]['name']}: {describe(c['voice'])}, speed {c['speed']}, pitch {c['pitch']}."


def reset(key):
    d = _load()
    d.pop(key, None)
    _save(d)
    base = _DEFAULTS.get(key, {})
    p = personas.PERSONAS[key]
    for k in ("voice", "speed", "lang"):
        if base.get(k) is not None:
            p[k] = base[k]
    p["pitch"] = base.get("pitch", 1.0)
    return f"{p['name']}'s voice is back to normal."
