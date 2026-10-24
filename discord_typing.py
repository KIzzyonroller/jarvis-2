"""
Sending a Discord message AS YOU, by typing into your own Discord app (not the bot).

Only when all of these are true:
  * you've switched it on (Settings > Discord bot > "Let him type in my Discord app"; off by default),
  * you asked for it ("send Alex 'running late' from my Discord"),
  * you approve the card, which shows exactly who it goes to and the exact text. Every message, every time:
    there's no "always allow" for messages sent as you.

How: brings the Discord app to the front, opens Discord's quick switcher (Ctrl+K), types the channel or person,
checks the window title really switched to them (if not, it stops without sending), pastes the message and
presses Enter. It's you typing, just faster; it never touches your login or token. Even so, Discord's rules
frown on automating user accounts, so it's deliberately one message at a time, only on request.
"""
import re
import time

import app_ready
import config

EXES = ("discord.exe", "discordptb.exe", "discordcanary.exe")
DENIED = "DENIED"


def enabled():
    return config.DISCORD_TYPE


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s or "").lower())


def _discord_window():
    import psutil
    import tools
    for w in tools._windows():
        if app_ready.SPLASH_RE.match((w.title or "").strip()):
            continue                                        # the updater, not Discord itself
        try:
            if psutil.Process(tools._wpid(w._hWnd)).name().lower() in EXES:
                return w
        except Exception:
            continue
    return None


def send(target, text, confirm):
    """confirm(title, detail) -> bool. Returns a sentence (or DENIED)."""
    import tools
    if not enabled():
        return ("Typing in the user's own Discord is switched off. They can turn it on in Settings > Discord bot "
                "('Let him type in my Discord app'). Offer the bot instead if it's set up.")
    if not tools.IS_WINDOWS:
        return "That only works on Windows."
    target = re.sub(r"^\s*(dm:|@|#)\s*", "", str(target or "")).strip()
    text = str(text or "").strip()
    if not target or not text:
        return "Who to, and what should it say?"
    if len(text) > 2000:
        return "Discord messages max out at 2000 characters; shorten it."
    w = _discord_window()
    if w is None:
        # closed (or only its updater is showing): open it and wait until it has really loaded, past the
        # "Checking for updates" window, before touching anything
        _, state, _ = app_ready.ensure("discord", front=True, timeout=45)
        w = _discord_window()
        if w is None or state in ("failed", "no window"):
            return "The Discord app isn't open and didn't start, so nothing was sent."
        if state == "loading":
            return "Discord was still loading after 45 seconds, so nothing was sent. Try again in a moment."
    game = tools.fullscreen_app()
    detail = (f"To: {target}\n\n{text}\n\nThis is sent from YOUR Discord account, as you."
              + (f"\nDiscord will come to the front over {game} for a second." if game else ""))
    if not confirm(f"Send as you on Discord to {target}", detail):
        return DENIED
    import pyautogui
    prev = tools._fg()
    tools._GUARD["id"] += 1                                  # we're moving focus on purpose
    tools._activate(w)
    if not tools._wait_front(w, timeout=2.0):
        return "Couldn't bring Discord to the front, so nothing was sent."
    before = (w.title or "")
    pyautogui.hotkey("ctrl", "k")
    time.sleep(0.6)
    tools._paste(target)
    time.sleep(1.0)                                          # let the switcher find matches
    pyautogui.press("enter")
    time.sleep(1.2)
    title = _title(w)
    if _norm(target) not in _norm(title):
        pyautogui.press("escape")
        return (f"Discord's quick switcher didn't land on {target} (the window says '{title or before}'), so I didn't "
                "send anything. Check the exact channel or name.")
    if tools._fg() != getattr(w, "_hWnd", None):
        return "Focus moved away from Discord before sending, so I didn't send it."
    tools._paste(text)
    time.sleep(0.25)
    pyautogui.press("enter")
    time.sleep(0.3)
    if game and prev:
        try:
            tools._force_foreground(prev)                   # back to the game
        except Exception:
            pass
    return f"Sent to {target} from your Discord: \"{text[:120]}\""


def _title(w):
    try:
        import pygetwindow as gw
        for x in gw.getAllWindows():
            if getattr(x, "_hWnd", None) == getattr(w, "_hWnd", 0):
                return x.title or ""
    except Exception:
        pass
    return w.title or ""
