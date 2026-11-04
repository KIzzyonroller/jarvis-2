"""
The secret code: "up up down down left right left right B A start", said out loud or typed (or the keys pressed
in the window). It used to call up the little desktop companion; that's gone. Now it's the switch for the merged
form: Jarvis and Ultron fused into one, which arrives with the desktop characters.
"""
import re

_WORD = {"bee": "b", "be": "b", "bea": "b", "ay": "a", "eh": "a", "hey": "a", "uh": "a", "ba": "b a", "bay": "b a",
         "lift": "left", "write": "right", "rite": "right", "wright": "right", "dawn": "down", "start": "start"}


def is_code(text):
    """'up up down down left right left right B A start', however speech recognition spells it."""
    words = [_WORD.get(w, w) for w in re.findall(r"[a-z]+", (text or "").lower())]
    s = " ".join(words)
    s = re.sub(r"\b(jarvis|ultron|hey|okay|ok|um|uh)\b", " ", s)
    s = " ".join(s.split())
    return bool(re.search(r"\bup up down down left right left right b ?a( start)?\b", s)) and "start" in s.split()[-3:]
