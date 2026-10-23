"""
Instant commands: the everyday stuff, done locally in a few milliseconds with
no call to Claude at all. "Pause", "next song", "volume 30", "open Spotify",
"what time is it", "lock the PC", "set a timer for 5 minutes"...

Only exact, simple phrasings match. Anything longer or combined ("open Spotify
and play something chill") goes to Claude as usual, so nothing gets misread
as a shortcut. If a shortcut fails (an app it can't find), Claude gets it.
"""
import re
import threading
from datetime import datetime

import tools

LEAD = re.compile(r"^(?:(?:hey|ok|okay|yo|um|uh|so|and|alright|right|now|please|just|quickly|real quick|"
                  r"can you|could you|would you|will you|can u|go ahead and|i want you to|i need you to)\s+)+")
TAIL = re.compile(r"(?:\s+(?:please|for me|now|thanks|thank you|real quick|quickly|right now|mate|buddy))+$")
WORDNUM = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
           "nine": 9, "ten": 10, "fifteen": 15, "twenty": 20, "twenty five": 25, "thirty": 30, "forty": 40,
           "forty five": 45, "fifty": 50, "sixty": 60, "seventy": 70, "seventy five": 75, "eighty": 80,
           "ninety": 90, "hundred": 100, "a hundred": 100, "one hundred": 100, "half": 50, "max": 100,
           "maximum": 100, "full": 100}
NUM = r"(\d{1,3}|" + "|".join(sorted(WORDNUM, key=len, reverse=True)) + r")"
COMPOUND = re.compile(r"\b(and|then|also|after|but|while|if|because)\b")


# recognize() runs the same rules with _DRY.on: every check passes or fails exactly as for real, but
# nothing is executed. (Before this, asking "is this a quick command?" ran the command, so an instant
# command fired up to four times: four Spotify windows, four skipped songs.)
_DRY = threading.local()
_DRY.on = False
HIT = ("", "(would handle)")


def _n(s):
    s = s.strip()
    return int(s) if s.isdigit() else WORDNUM.get(s)


def normalize(text):
    t = text.lower().strip()
    t = re.sub(r"[“”\"!?,;]", " ", t)
    t = re.sub(r"\.(?=\s|$)", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    for _ in range(2):
        t = LEAD.sub("", t).strip()
        t = TAIL.sub("", t).strip()
    return t


# Each rule: (pattern, function(match) -> (spoken line or None, toast/log line))
def _vol_set(m):
    v = _n(m.group(1))
    if v is None or v > 100:
        return None
    if _DRY.on:
        return HIT
    tools.set_volume(level=v)
    return f"Volume {v}.", f"Volume {v}%"


def _vol_step(m):
    up = bool(re.search(r"\b(up|louder)\b", m.group(0)))
    big = bool(re.search(r"\b(lot|way|much)\b", m.group(0)))
    if _DRY.on:
        return HIT
    tools.media_control("volume_up" if up else "volume_down", steps=10 if big else 5)
    return None, "Volume up" if up else "Volume down"


def _mute_sound(m):
    on = m.group(1) == "mute"
    if _DRY.on:
        return HIT
    tools.set_volume(mute=on)
    return None, "Sound muted" if on else "Sound unmuted"


def _media(key, label):
    def f(m):
        if _DRY.on:
            return HIT
        tools.media_control(key)
        return None, label
    return f


def _open(m):
    target = m.group(1).strip()
    if COMPOUND.search(target) or len(target.split()) > 4 or target in ("it", "that", "this", "something", "the app"):
        return None
    if re.search(r"\b(play|playing|song|music by|video|search|for me|i|that|which|where|from|with|about|last|latest|recent|new)\b", target):
        return None
    if _DRY.on:
        return HIT
    out = tools.open_thing(target)
    if out.startswith(("Couldn't", "Open what", "Unknown")) or "doesn't exist" in out or "outside the folders" in out:
        return None                                        # let Claude figure it out
    nice = re.sub(r"^Opened (settings: )?", "", out.split(".")[0]).strip() or target
    return f"Opening {nice}.", out


def _close(m):
    target = m.group(1).strip()
    if COMPOUND.search(target) or len(target.split()) > 3 or target in ("it", "that", "this", "everything", "all"):
        return None
    if _DRY.on:
        return HIT
    out = tools.close_app(target)
    if out.startswith("No running app"):
        return f"{target.title()} isn't running.", out
    if out.startswith("Too many"):
        return None
    return f"Closing {target}." if "closed" in out else None, out


def _time(m):
    now = datetime.now()
    return f"It's {now.strftime('%I:%M %p').lstrip('0')}.", "Time"


def _date(m):
    now = datetime.now()
    return f"It's {now.strftime('%A, %B')} {now.day}.", "Date"


def _lock(m):
    if _DRY.on:
        return HIT
    tools.system_power("lock")
    return None, "Locked"


def _screenshot(m):
    if _DRY.on:
        return HIT
    out = tools.screenshot()
    return "Screenshot saved.", out


def _desktop(m):
    if _DRY.on:
        return HIT
    tools.window_control("show_desktop")
    return None, "Desktop"


def _bright(m):
    v = _n(m.group(1))
    if v is None or v > 100:
        return None
    if _DRY.on:
        return HIT
    out = tools.brightness(v)
    return (f"Brightness {v}." if "%" in out or "set" in out.lower() else out), out


def _mode(m):
    dark = next(g for g in m.groups() if g) == "dark"
    if re.search(r"\b(off|disable)\b", m.group(0)):
        dark = not dark
    if _DRY.on:
        return HIT
    tools.dark_mode(dark)
    return ("Dark mode." if dark else "Light mode."), "Dark mode" if dark else "Light mode"


def _timer(m):
    amount = m.group(1)
    n = float(amount) if re.match(r"^\d+(\.\d+)?$", amount) else _n(amount)
    if not n:
        return None
    unit = m.group(2)
    mins = n / 60 if unit.startswith("s") else n * 60 if unit.startswith("h") else n
    if _DRY.on:
        return HIT
    out = tools.set_reminder("Timer's up", in_minutes=mins)
    label = f"{int(n) if n == int(n) else n} {unit.rstrip('s')}{'' if n == 1 else 's'}"
    return f"Timer set for {label}.", out


VAGUE = {"it", "that", "this", "something", "anything", "some music", "music", "a song", "a video", "something good"}


def _youtube(m):
    q = m.group(1).strip()
    if q in VAGUE or COMPOUND.search(q):
        return None                                        # "play something on YouTube": Claude picks
    if _DRY.on:
        return HIT
    import youtube
    out = youtube.play(query=q)
    if not out.startswith("Playing"):
        return None
    return f"Playing {youtube.short_title(youtube.NOW.get('title', q)) or q}.", out


def _spotify(m):
    q = m.group(1).strip()
    if q in VAGUE or COMPOUND.search(q):
        return None
    if _DRY.on:
        return HIT
    import spotify
    out = spotify.control("play", q)
    if out.startswith("Playing"):
        return out.split(" by ")[0].rstrip(".") + ".", out
    if "in the Spotify app" in out:
        return "It's up in Spotify. Hit play.", out
    return None


NETFLIX_WHERE = r"(?: (on the web|on web|in (?:the |a |my )?browser|on the website|in the app|on the app|in the netflix app))?"


def _netflix(m):
    groups = [g for g in m.groups()]
    where_txt = groups[-1] or ""
    q = groups[0].strip() if len(groups) == 2 and groups[0] else ""
    if q and (q in VAGUE or COMPOUND.search(q)):
        return None
    if _DRY.on:
        return HIT
    import netflix
    where = "app" if "app" in where_txt else "web" if where_txt else "auto"
    out = netflix.open_netflix(q, where)
    if out.startswith("The Netflix app isn't installed"):
        return "The Netflix app isn't installed. Want the website?", out
    return ("Netflix, on the web." if "netflix.com" in out and not q else
            f"Here's {q} on Netflix." if q else "Opening Netflix."), out


NUMWORD = r"(\d+(?:\.\d+)?|" + "|".join(sorted(WORDNUM, key=len, reverse=True)) + r")"
RULES = [
    (r"^(?:play|put on|pull up|show me|watch|find and play) (.+?) on youtube$", _youtube),
    (r"^(?:play|put on|open|pull up|start) (.+?) on spotify$", _spotify),
    (r"^(?:open|launch|start|pull up|bring up|go to) netflix" + NETFLIX_WHERE + r"$", _netflix),
    (r"^(?:play|put on|watch|pull up|find|search for|search|look up) (.+?) on netflix" + NETFLIX_WHERE + r"$", _netflix),
    (rf"^(?:set |turn |put |change )?(?:the )?(?:volume|sound)(?: (?:to|at|down to|up to))? {NUM}(?: ?%| percent)?$", _vol_set),
    (rf"^(?:set |turn |put )?(?:the )?volume (?:up|down) to {NUM}(?: ?%| percent)?$", _vol_set),
    (r"^(?:turn |crank )?(?:the )?(?:volume|sound|music|it) (?:way )?(up|down)(?: a (?:bit|little|lot|notch))?$", _vol_step),
    (r"^(?:turn it|turn that) (up|down)(?: a (?:bit|little|lot))?$", _vol_step),
    (r"^(?:a (?:bit|little) |way |much )?(louder|quieter|softer)$", _vol_step),
    (r"^(mute|unmute) (?:the )?(?:sound|audio|volume|speakers|computer|pc|music)$", _mute_sound),
    (r"^(?:pause|resume|unpause|play|stop)(?: (?:the )?(?:music|song|video|track|it|that|playback|spotify|youtube))?$",
     _media("play_pause", "Play / pause")),
    (r"^(?:next|skip)(?: (?:this |that |the )?(?:song|track|one|video))?$|^skip it$|^next song please$", _media("next", "Next")),
    (r"^(?:previous|last|go back(?: a)?|back)(?: (?:song|track|one))$|^previous$|^play the last song$|^go back a song$",
     _media("previous", "Previous")),
    (r"^(?:open|launch|start|run|fire up|load up|boot up|pull up|bring up)(?: up)? (?:the |my )?(.+?)(?: app| application)?$", _open),
    (r"^(?:close|quit|exit|kill) (?:the |my )?(.+?)(?: app| application)?$", _close),
    (r"^(?:what(?:'s| is) the time|what time is it|time|what time is it right now|got the time)$", _time),
    (r"^(?:what(?:'s| is) (?:the |today's )?date(?: today)?|what day is it(?: today)?|what(?:'s| is) today)$", _date),
    (r"^lock (?:the |my )?(?:pc|computer|screen|it|laptop)$", _lock),
    (r"^(?:take a |take |grab a )?screenshot(?: (?:of )?(?:this|that|my screen|the screen))?$", _screenshot),
    (r"^(?:show (?:the |my )?desktop|minimize (?:everything|all(?: windows| the windows)?)|hide everything)$", _desktop),
    (rf"^(?:set |turn |put )?(?:the |screen )?brightness(?: (?:to|at|up to|down to))? {NUM}(?: ?%| percent)?$", _bright),
    (r"^(?:turn on |enable |switch to |go |use )?(dark|light) mode(?: on)?$|^turn (?:off|on) (dark|light) mode$|^(?:disable) (dark|light) mode$", _mode),
    (rf"^(?:set |start )?(?:a |an )?timer (?:for )?{NUMWORD} ?(seconds?|secs?|minutes?|mins?|hours?|hrs?)$", _timer),
    (rf"^(?:set |start )?(?:a |an )?{NUMWORD}[ -](second|sec|minute|min|hour)s? timer$", _timer),
]
RULES = [(re.compile(p), f) for p, f in RULES]


def recognize(text):
    """Would match() handle this? Never does anything. Safe to call as often as you like."""
    _DRY.on = True
    try:
        return match(text) is not None
    finally:
        _DRY.on = False


def match(text):
    """DOES the command. Returns (spoken line or None, log line) if this was handled instantly, else None.
    Call it once per command; use recognize() to just check."""
    if not hasattr(_DRY, "on"):
        _DRY.on = False
    t = normalize(text)
    if not t or len(t.split()) > 9:
        return None
    for pat, fn in RULES:
        m = pat.match(t)
        if not m:
            continue
        try:
            return fn(m)
        except Exception as e:
            print(f"[instant] {t!r} failed ({e}); handing it to Claude")
            return None
    return None
