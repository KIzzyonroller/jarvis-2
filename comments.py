"""
Screen comments (the "Comments on what you're doing" option): now and then he says one short line about what
you're up to, going only by the app and window name in front (the same private-window and "never log" rules as
activity memory: private browsing, password managers and your skip list are never looked at). No screenshots.

He stays quiet when:
  * you're in a fullscreen game or video, or the window looks like a call or meeting
  * he's busy (listening, thinking, talking) or you've been away from the keyboard for a couple of minutes
  * nothing has changed since the last remark, or it's too soon (Rarely: 40 min, Sometimes: 15, Often: 6)

The line comes from the small local brain when that's on and ready (free), otherwise from the fast Claude model
(well under a cent each, and never past the daily spending limit).
"""
import re
import threading
import time

import config
import prefs

GAP = {"rarely": 40 * 60, "sometimes": 15 * 60, "often": 6 * 60}
CALLS = re.compile(r"\b(call|meeting|huddle|webinar|zoom|teams|interview|on air|live|recording)\b", re.I)
CALL_EXES = {"zoom.exe", "ms-teams.exe", "teams.exe", "webex.exe", "ciscocollabhost.exe", "skype.exe", "obs64.exe"}


class Commenter:
    def __init__(self, core):
        self.core = core
        self._stop = threading.Event()
        self.last_t = time.time()           # no remark in the first few minutes after start
        self.last_key = None
        self.recent = []
        self.seen_since = {}                # app -> when it came to the front (a remark waits until you've settled in)

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="screen-comments").start()
        return self

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.wait(30):
            if not prefs.get("screen_comments"):
                continue
            try:
                self._maybe()
            except Exception as e:
                print(f"[comments] {e}")

    def _maybe(self):
        import activity
        import tools
        now = time.time()
        if now - self.last_t < GAP.get(prefs.get("comment_rate"), GAP["sometimes"]):
            return
        if self.core.state not in ("idle", "standby") or getattr(self.core, "muted", False):
            return
        if activity._idle_secs() > 120 or tools.fullscreen_app():
            return
        s = activity._sample()
        if not s:
            return
        exe, app, title = s
        if exe in CALL_EXES or CALLS.search(title):
            return
        key = (app, activity.short_title(title, app))
        first = self.seen_since.setdefault(app, now)
        if now - first < 90 or key == self.last_key:     # just switched, or nothing new to say anything about
            return
        line = self._line(app, activity.short_title(title, app))
        if not line:
            return
        self.last_t, self.last_key = now, key
        self.recent = (self.recent + [line])[-6:]
        self.seen_since = {app: first}
        print(f"[comments] {line}")
        self.core.say_line(line)

    def _line(self, app, title):
        persona = self.core.persona_key
        name = "Ultron" if persona == "ultron" else "Jarvis"
        style = ("sardonic, theatrical, amused by humans, never cruel" if persona == "ultron"
                 else "dry, warm British wit, understated")
        lang = " Use the language the user usually speaks to you in." if prefs.get("languages") else ""
        avoid = ("Don't repeat or closely echo these earlier remarks: " + " / ".join(self.recent[-4:]) + ".") if self.recent else ""
        prompt = (f"You are {name}, the user's desktop AI ({style}). You glance at their screen. The app in front is "
                  f"{app}" + (f", and the window is about: {title[:80]}" if title else "") + ". Say ONE short spoken "
                  f"remark about what they're doing, at most 15 words: playful or helpful, never nagging, never "
                  f"reading out names, numbers or anything personal from the title. No quotes, no emojis.{lang} {avoid}")
        lane = getattr(self.core, "extras", None) and self.core.extras.part("localbrain")
        if lane is not None and lane.ok and not lane.gaming and prefs.get("local_brain"):
            out = lane.ask(prompt, persona, config.ADDRESS_AS, lambda d: None, remember=False)
            if out:
                return self._clean(out)
        return self._claude(prompt)

    def _claude(self, prompt):
        import usage
        if usage.over_budget() or not config.FAST_MODEL:
            return None
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            r = client.messages.create(model=config.FAST_MODEL, max_tokens=60,
                                       messages=[{"role": "user", "content": prompt}])
            try:
                usage.record_claude(config.FAST_MODEL, r.usage)
            except Exception:
                pass
            return self._clean("".join(b.text for b in r.content if getattr(b, "type", "") == "text"))
        except Exception as e:
            print(f"[comments] couldn't come up with one: {e}")
            return None

    @staticmethod
    def _clean(text):
        t = (text or "").strip().strip('"“”').split("\n")[0].strip()
        if not t or len(t.split()) > 24:
            return None
        return t
