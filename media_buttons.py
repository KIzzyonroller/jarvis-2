"""
Pressing Play and Shuffle inside music apps when there's no proper way to tell them to (Spotify without Premium,
the Apple Music app, the Apple Music / Spotify websites).

How: Windows UI Automation, the accessibility system screen readers use. Every button in those apps has a
name ("Play", "Play Blinding Lights", "Enable shuffle"...), so he finds the right one and presses it directly.
No mouse movement, no stealing focus, works behind a game. Then he checks Windows' media info to confirm
something actually started.

If an app's buttons can't be found that way, the tool tells Claude to fall back to looking at the screen and
clicking with the mouse (the screen and mouse tools), unless you're in a fullscreen game.
"""
import re
import sys
import time

APPS = {
    "spotify": {"exe": ("spotify.exe",), "title": None},
    "apple music": {"exe": ("applemusic.exe", "itunes.exe"), "title": None},
    "web spotify": {"exe": ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe"),
                    "title": r"spotify"},
    "web apple music": {"exe": ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe"),
                        "title": r"apple music"},
}
PLAY_RE = re.compile(r"^(play|resume)\b", re.I)
PAUSE_RE = re.compile(r"^pause\b", re.I)
SHUFFLE_ON_RE = re.compile(r"^(enable shuffle|turn on shuffle|shuffle off\b|shuffle( play| all)?$)", re.I)   # pressing turns it on
SHUFFLE_IS_ON_RE = re.compile(r"^(disable shuffle|turn off shuffle|shuffle on\b)", re.I)                    # it's on already


def available():
    if sys.platform != "win32":
        return False
    try:
        import uiautomation  # noqa: F401
        return True
    except Exception:
        return False


def _windows(app):
    """Top-level windows belonging to that app."""
    import psutil
    import uiautomation as auto
    spec = APPS[app]
    out = []
    for w in auto.GetRootControl().GetChildren():
        try:
            name = psutil.Process(w.ProcessId).name().lower()
        except Exception:
            continue
        if name not in spec["exe"]:
            continue
        if spec["title"] and not re.search(spec["title"], w.Name or "", re.I):
            continue
        out.append(w)
    return out


def _buttons(win, max_depth=40, limit=4000):
    import uiautomation as auto
    out = []
    for c, depth in auto.WalkControl(win, maxDepth=max_depth):
        if len(out) > limit:
            break
        try:
            if c.ControlTypeName in ("ButtonControl", "CheckBoxControl") and c.Name:
                r = c.BoundingRectangle
                if r.width() > 0 and r.height() > 0:
                    out.append(c)
        except Exception:
            continue
    return out


def _press(c):
    try:
        c.GetInvokePattern().Invoke()
        return True
    except Exception:
        pass
    try:
        c.GetTogglePattern().Toggle()
        return True
    except Exception:
        pass
    try:
        c.Click(simulateMove=False)
        return True
    except Exception:
        return False


def _area(c):
    r = c.BoundingRectangle
    return r.width() * r.height()


def find_play(buttons, hint=""):
    """The page's main Play button: one naming what was asked for, else the biggest Play button
    (the big one on a song/playlist page, not the small one in the player bar)."""
    plays = [b for b in buttons if PLAY_RE.match(b.Name.strip())]
    if not plays:
        return None
    words = [w for w in re.findall(r"[a-z0-9']+", (hint or "").lower()) if len(w) > 2]
    if words:
        named = [b for b in plays if sum(w in b.Name.lower() for w in words) >= max(1, len(words) // 2)]
        if named:
            return max(named, key=_area)
    return max(plays, key=_area)


def snapshot(app):
    """The buttons on screen now, to tell later when the app has moved on to the page we asked for."""
    if not available():
        return None
    try:
        return frozenset(b.Name.strip() for w in _windows(app) for b in _buttons(w))
    except Exception:
        return None


def _named_play(btns, hint):
    words = [w for w in re.findall(r"[a-z0-9']+", (hint or "").lower()) if len(w) > 2]
    if not words:
        return None
    named = [b for b in btns if PLAY_RE.match(b.Name.strip())
             and sum(w in b.Name.lower() for w in words) >= max(1, len(words) // 2)]
    return max(named, key=_area) if named else None


def _wait_buttons(app, timeout, hint="", before=None):
    """Wait for the app's page to be ready: its window is up, it has moved on from the page it showed before
    (before = snapshot() taken before opening the link), and either a Play button naming what we asked for is
    there or the buttons have stopped changing. A fixed sleep used to press buttons on a half-loaded page."""
    start = time.time()
    end = start + timeout
    last, steady = None, 0
    wins, btns = [], []
    while True:
        wins = _windows(app)
        btns = [b for w in wins for b in _buttons(w)]
        names = frozenset(b.Name.strip() for b in btns)
        moved = before is None or len(names ^ before) >= 3
        if btns and hint and _named_play(btns, hint) is not None:
            return wins, btns                        # the thing we asked for is right there
        if btns and moved:
            if last is not None and abs(len(names) - last) <= max(1, int(last * 0.05)):
                steady += 1
            else:
                steady = 0
            if steady >= 2 and time.time() - start >= 1.0:
                return wins, btns
            last = len(names)
        if time.time() > end:
            return wins, btns
        time.sleep(0.5)


def playing(app_words=("spotify", "applemusic", "itunes", "chrome", "msedge", "firefox")):
    """Does Windows say one of these apps is playing right now?"""
    try:
        import netflix
        for s in netflix.media_sessions():
            if s["playing"] and any(w in s["app"].lower().replace(" ", "") for w in app_words):
                return True
    except Exception:
        pass
    return None                     # unknown (media info unavailable)


def press_play(app, hint="", shuffle=None, timeout=12.0, before=None):
    """Returns (done, message). shuffle: True/False to set it first, None to leave it.
    before: snapshot() from just before the link was opened, so it waits for the new page."""
    if not available():
        return False, "button pressing isn't available on this PC"
    wins, btns = _wait_buttons(app, timeout, hint, before)
    if not wins:
        return False, f"the {app} window isn't open"
    if not btns:
        return False, f"couldn't see any buttons in {app} (it may still be loading)"
    note = ""
    if shuffle is not None:
        ok, note = _set_shuffle_in(btns, shuffle)
        btns = [b for w in wins for b in _buttons(w)]
    if any(PAUSE_RE.match(b.Name.strip()) and _area(b) >= 1600 for b in btns) and not hint:
        return True, "it's already playing" + (f"; {note}" if note else "")
    target = find_play(btns, hint)
    if target is None:
        return False, "couldn't find a Play button" + (f" ({note})" if note else "")
    if not _press(target):
        return False, "found the Play button but couldn't press it"
    for _ in range(10):
        time.sleep(0.4)
        if playing():
            return True, f"pressed {target.Name.strip()!r}, it's playing" + (f"; {note}" if note else "")
    return True, f"pressed {target.Name.strip()!r}" + (f"; {note}" if note else "")


def _set_shuffle_in(btns, on):
    is_on = [b for b in btns if SHUFFLE_IS_ON_RE.match(b.Name.strip())]
    can_on = [b for b in btns if SHUFFLE_ON_RE.match(b.Name.strip()) and b not in is_on]
    if on and is_on:
        return True, "shuffle was already on"
    if not on and not is_on:
        return True, "shuffle was already off"
    pick = (max(can_on, key=_area) if can_on else None) if on else max(is_on, key=_area)
    if pick is None:
        return False, "couldn't find the shuffle button"
    if _press(pick):
        time.sleep(0.3)
        return True, f"shuffle {'on' if on else 'off'}"
    return False, "couldn't press shuffle"


def set_shuffle(app, on=True, timeout=6.0):
    if not available():
        return False, "button pressing isn't available on this PC"
    wins, btns = _wait_buttons(app, timeout)
    if not wins:
        return False, f"the {app} window isn't open"
    if not btns:
        return False, f"couldn't see any buttons in {app} (it may still be loading)"
    return _set_shuffle_in(btns, on)


def mouse_fallback(app, what="the Play button"):
    """What to tell Claude when buttons can't be pressed directly."""
    import tools
    game = tools.fullscreen_app()
    if game:
        return (f" I couldn't press {what} without taking over the screen, and the user is in {game}, so don't use "
                "the mouse; tell them it's ready for them to press play.")
    return (f" To press {what} anyway: use the screen tool on '{app.replace('web ', '')}' (detail high), then the mouse tool "
            "to click it (look_after=true), and check it's playing. Don't click anything else.")
