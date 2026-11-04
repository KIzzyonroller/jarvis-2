"""
Live options: things you switch on and off from the System panel ("Options") or by asking him, that take effect
right away (no restart). Kept in JarvisData\\prefs.json. Settings (keys, accounts) stay in settings.py.

Each option has a key, a label, a kind (bool / choice / number), help text and a default. Anything can watch an
option with on_change(key, fn).
"""
import json
import os
import threading

import config

FILE = config.DATA_DIR / "prefs.json"

# (group, key, label, kind, default, help, options)
SCHEMA = [
    ("Graphics card", "hearing_device", "Hearing runs on", "choice", "auto",
     "Graphics card needs NVIDIA's libraries (Set up below, about 1 GB, once). Takes effect next start.",
     [("auto", "Auto"), ("cpu", "Processor"), ("cuda", "Graphics card")]),
    ("Graphics card", "voice_device", "His voice runs on", "choice", "auto",
     "The graphics card has to pass a test first; if it fails or is slower, Auto stays on the processor.",
     [("auto", "Auto"), ("cpu", "Processor"), ("gpu", "Graphics card")]),

    ("On your desktop", "desktop", "Show them on the desktop", "bool", False,
     "They live on your desktop: walking the taskbar, sitting on windows, peeking from the edges.", None),
    ("On your desktop", "desktop_who", "Who's out", "choice", "persona", "",
     [("persona", "Whoever's talking"), ("jarvis", "Jarvis"), ("ultron", "Ultron"), ("both", "Both")]),
    ("On your desktop", "hud_mode", "His window", "choice", "window",
     "Just him: no window, only the figure. When he needs to show you something he throws it open.",
     [("window", "Window and figure"), ("character", "Just him")]),
    ("On your desktop", "desktop_size", "Size", "choice", "m", "",
     [("s", "Small"), ("m", "Medium"), ("l", "Large")]),
    ("On your desktop", "roam", "Wander around", "bool", True, "Off: they stay where you put them.", None),
    ("On your desktop", "perch", "Sit on windows", "bool", True, "Ride along on top of the window you're using.", None),
    ("On your desktop", "peek", "Peek from the edges", "bool", True, "", None),
    ("On your desktop", "nap", "Nap when you're away", "bool", True, "", None),
    ("On your desktop", "dance", "Dance to music", "bool", True, "Moves with whatever your PC is playing.", None),
    ("On your desktop", "hover_fade", "Fade when the mouse is over them", "bool", True,
     "Clicks go straight through them. Hold Ctrl to grab one and move it.", None),
    ("On your desktop", "summon_fx", "Entrances when opening apps", "bool", True,
     "Ultron reaches out and tears it open, Jarvis throws a ring of light from his staff.", None),
    ("On your desktop", "clones", "Clones", "bool", False,
     "Lets you say \"clone yourself\" for a few little copies running around. \"Clones away\" sends them off.", None),

    ("Extras", "screen_comments", "Comments on what you're doing", "bool", False,
     "Now and then he says something about what's on screen (from window names only). Never during games, "
     "fullscreen video or calls.", None),
    ("Extras", "comment_rate", "How often", "choice", "sometimes", "",
     [("rarely", "Rarely"), ("sometimes", "Sometimes"), ("often", "Often")]),
    ("Extras", "safety", "Safety", "choice", "balanced",
     "How much needs your OK. Hard stops (shutting down, deleting, payments) always ask, whatever this says.",
     [("careful", "Careful: ask about everything that changes something"), ("balanced", "Balanced"),
      ("relaxed", "Relaxed: only ask about risky things")]),
    ("Extras", "languages", "Other languages", "bool", False,
     "He understands and answers in the language you speak. Hearing gets a little slower (a bigger model).", None),
    ("Extras", "language", "Language", "choice", "auto", "",
     [("auto", "Whatever I speak"), ("es", "Español"), ("fr", "Français"), ("it", "Italiano"),
      ("pt", "Português"), ("hi", "Hindi"), ("en", "English")]),

    ("Brain", "local_brain", "Small brain on this PC", "bool", False,
     "Quick chat and simple questions answered on your PC for free (needs Ollama, about 1.5 GB). Anything that "
     "needs tools or real thinking still goes to Claude. Unloads itself while you game.", None),
    ("Brain", "local_model", "Local model", "choice", "qwen3:1.7b", "",
     [("qwen3:1.7b", "Qwen3 1.7B (fits 4 GB cards)"), ("qwen3:4b", "Qwen3 4B (needs 6 GB+)"),
      ("llama3.2:3b", "Llama 3.2 3B")]),

    ("Hands and voice", "own_pointer", "His own pointer", "bool", False,
     "When he clicks things for you he uses his own pointer where the app allows it, and puts yours back exactly "
     "where it was when it doesn't.", None),
    ("Hands and voice", "mic_voice", "Speak into my mic", "bool", False,
     "Plays his voice into VB-CABLE so Discord, games and calls hear him. Install VB-CABLE first (free).", None),
    ("Hands and voice", "mic_device", "Virtual mic", "text", "CABLE Input",
     "The playback device his voice goes into. VB-CABLE's is \"CABLE Input\".", None),
    ("Hands and voice", "mic_also_speakers", "Also play him on my speakers", "bool", True, "", None),
]
HIDDEN = {"merged": False, "desktop_pos": None}       # set by code, never shown as options
DEFAULTS = {k: d for _, k, _, _, d, _, _ in SCHEMA} | HIDDEN
_KINDS = {k: (kind, opts) for _, k, _, kind, _, _, opts in SCHEMA}

_lock = threading.RLock()
_values = {}
_watchers = {}
_loaded = False


def _load():
    global _loaded
    with _lock:
        if _loaded:
            return
        try:
            data = json.loads(FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _values.update({k: v for k, v in data.items() if k in DEFAULTS})
        except Exception:
            pass
        _loaded = True


def _save():
    try:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(_values, indent=1), encoding="utf-8")
        os.replace(tmp, FILE)
    except Exception as e:
        print(f"[prefs] couldn't save: {e}")


def get(key):
    _load()
    with _lock:
        return _values.get(key, DEFAULTS.get(key))


def coerce(key, value):
    """The value as the option's type, or raises ValueError with a sentence to show."""
    kind, opts = _KINDS.get(key, ("any", None))
    if kind == "bool":
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("on", "true", "yes", "1", "enable", "enabled"):
                return True
            if v in ("off", "false", "no", "0", "disable", "disabled"):
                return False
            raise ValueError(f"{key} is on or off.")
        return bool(value)
    if kind == "choice":
        v = str(value).strip()
        keys = [k for k, _ in opts]
        if v in keys:
            return v
        low = v.lower()
        for k, label in opts:                     # "graphics card", "careful", "spanish"...
            if low == k.lower() or low == label.lower() or low in label.lower().split(":")[0]:
                return k
        names = {"spanish": "es", "french": "fr", "italian": "it", "portuguese": "pt", "english": "en",
                 "gpu": "cuda" if key == "hearing_device" else "gpu", "graphics": "cuda" if key == "hearing_device" else "gpu",
                 "processor": "cpu", "small": "s", "medium": "m", "large": "l"}
        if names.get(low) in keys:
            return names[low]
        raise ValueError(f"{key} must be one of: {', '.join(label for _, label in opts)}.")
    if kind == "number":
        return float(value)
    return value


def set(key, value, save=True):
    """Sets an option and tells whoever's watching. Returns the stored value."""
    _load()
    if key not in DEFAULTS:
        raise KeyError(key)
    value = coerce(key, value)
    with _lock:
        old = _values.get(key, DEFAULTS[key])
        _values[key] = value
        if save:
            _save()
        fns = list(_watchers.get(key, ())) + list(_watchers.get("*", ()))
    if old != value:
        for fn in fns:
            try:
                fn(key, value)
            except Exception as e:
                print(f"[prefs] {key} watcher failed: {e}")
    return value


def on_change(key, fn):
    """fn(key, value) whenever key changes ('*' for every option)."""
    with _lock:
        _watchers.setdefault(key, []).append(fn)


def view():
    """Everything the Options section needs to draw itself."""
    _load()
    out = []
    for group, key, label, kind, default, help_, opts in SCHEMA:
        out.append({"group": group, "key": key, "label": label, "kind": kind, "value": get(key), "help": help_,
                    "options": [{"v": k, "label": l} for k, l in opts] if opts else None})
    return out


def describe():
    """Short text of every option and its value, for him to read when asked."""
    lines = []
    for item in view():
        v = item["value"]
        if item["kind"] == "bool":
            v = "on" if v else "off"
        elif item["options"]:
            v = next((o["label"] for o in item["options"] if o["v"] == v), v)
        lines.append(f"{item['key']} ({item['label']}): {v}")
    return "\n".join(lines)


def env_or_pref(env_name, key):
    """A setting that can be forced from .env (for people who already set it there), otherwise the option."""
    v = os.environ.get(env_name)
    return v.lower() if v else str(get(key)).lower()
