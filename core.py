"""
The engine. Owns the brains, voice, ears, reminders and telemetry, and talks
to whatever frontend is attached (the HUD app, or the plain console) through
a single emit(event_dict) function.

Events sent to the frontend:
  boot      {line}                         startup log line
  ready     {model, voice}                 boot finished
  persona   {key, name, wordmark}          Jarvis <-> Ultron
  state     {state}                        idle | listening | thinking | speaking | awaiting
  level     {v}                            mic level 0..1
  heard     {text, addressed}              something the mic transcribed
  msg       {role, text}                   role: user | jarvis | system   ("jarvis" = whichever AI is active)
  caption   {text}                         the sentence being spoken right now
  voice     {v}                            loudness of the AI's voice 0..1
  turn_start / turn_end {id, text, secs, interrupted}
  activity  {id, kind, data, t}            live progress: thinking, tool_pending, tool_start, tool_done
  reply_delta {id, text}                   reply text as it streams in
  tool      {name, args, result}
  telemetry {...}
  reminders {items}
  alert     {text}                         reminder fired
  toast     {text}
  confirm   {id, title, detail, timeout}   approval needed
  confirm_done {id, approved}
  quit      {}
"""
import difflib
import json
import queue
import random
import re
import threading
import time
import traceback
import uuid
from datetime import datetime, timedelta

import config
import personas
import briefing
import intents
import notifications
import usage
import permissions
import tools
import settings
import voice_settings
from voice import Speaker

# Only "quit" really shuts him down. Everything that sounds like "close" just hides the window.
QUIT_WORDS = {"quit", "quit yourself", "quit the app", "quit app", "quit now", "quit please"}
HIDE_WORDS = {"close", "close yourself", "close the app", "close up", "close down", "close the window",
              "exit", "goodbye", "bye", "go away", "hide", "hide yourself", "minimize", "minimise",
              "minimize yourself", "minimise yourself", "power down", "shut yourself down", "go offline",
              "that's all", "that'll be all", "dismissed", "you can go", "leave", "get lost"}
MUTE_WORDS = {"mute", "mute yourself", "mute the mic", "mute mic", "mute microphone", "stop listening",
              "don't listen", "go deaf", "cover your ears", "mic off", "turn off the mic", "turn your mic off",
              "turn off your mic", "privacy mode"}
DICTATE_START = {"dictate", "start dictating", "start dictation", "dictation mode", "dictation", "take dictation",
                 "type what i say", "type for me", "type what i'm saying", "dictation on"}
DICTATE_STOP = {"stop dictating", "stop dictation", "end dictation", "done dictating", "stop typing",
                "finish dictation", "dictation off", "that's it", "stop", "end"}
BRIEF_WORDS = {"brief me", "briefing", "morning briefing", "daily briefing", "give me a briefing", "good morning",
               "catch me up", "status report", "give me a status report", "what did i miss", "morning"}
SHOW_WORDS = {"come back", "show yourself", "show up", "open up", "pop up", "restore", "unminimize",
              "bring yourself back", "where are you", "show me yourself", "come here"}
RESET_WORDS = {"reset", "forget everything", "new conversation", "clear memory", "clear your memory"}
STOP_WORDS = {"stop", "shut up", "enough", "cancel", "quiet", "be quiet", "never mind", "nevermind",
              "hold on", "wait", "stop talking", "ok stop", "okay stop", "that's enough"}
YES_WORDS = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "confirmed", "approve",
             "approved", "affirmative", "proceed", "authorize", "authorized", "authorise", "do", "go"}
NO_HINTS = {"no", "nope", "nah", "don't", "dont", "not", "cancel", "stop", "deny", "abort", "negative"}
FILLERS = {"hey", "hi", "ok", "okay", "yo", "oh", "um", "uh", "so", "and", "hello", "alright", "right", "a"}
TRAILING_POLITE = {"please", "thanks", "now", "mate", "buddy"}
# Words that mean you're probably not done talking yet
DANGLING = {"and", "or", "but", "to", "the", "a", "an", "for", "with", "of", "then", "because", "so", "like",
            "um", "uh", "my", "your", "in", "on", "at", "from", "into", "about", "if", "that", "this", "is", "can",
            "could", "would", "please", "also", "plus", "what", "how", "open", "play", "set", "find", "turn"}
# Requests that need the big model: seeing, files, building, multi-step work, real reasoning.
HEAVY_HINTS = re.compile(r"\b(screen|see|look|watch|camera|webcam|file|folder|document|pdf|download|blender|model|3d|"
                         r"print|click|mouse|drag|scroll|type|write|draft|email|message|code|script|powershell|command|"
                         r"install|uninstall|explain|why|how (do|does|can|would|should|to)|compare|research|summari[sz]e|"
                         r"analy[sz]e|debug|fix|error|plan|delete|move|copy|rename|routine|dictat|translate|calculate|"
                         r"math|essay|story|poem|recipe|steps|guide|then|after that|and then)\b", re.I)
# Requests that will take a few seconds (tools, web, vision): worth an instant "On it."
SLOW_HINTS = re.compile(r"\b(weather|forecast|news|search|look ?up|google|latest|score|scores|price|stock|who won|"
                        r"screen|look at|see|camera|find|file|folder|blender|model|build|make me|create|write|draft|"
                        r"explain|install|research|summari[sz]e|compare|organi[sz]e|clean up|routine)\b", re.I)
DETAIL_HINTS = re.compile(r"\b(detail|detailed|explain|tell me (more|everything|about)|in full|read (it|that|me|out)|"
                          r"list|step by step|walk me through|summari[sz]e|long version)\b", re.I)
ECHO_TAIL = 1.0          # seconds after he stops talking that the room (and the mic) can still carry his voice

# Conversation history
HISTORY_CLEAR = {"delete my conversation history", "forget our conversations", "forget all our conversations",
                 "clear your memory of our conversations", "delete our chat history", "clear conversation history",
                 "wipe our conversation history", "delete your conversation history"}
USAGE_ASK = {"how much have you cost today", "how much have you cost", "how much have i spent", "how much have i spent today",
             "what have you cost me", "what's my spending", "whats my spending", "how much money have you used",
             "how much money have you used today", "what's the bill", "whats the bill", "how much have we spent"}
BUDGET_RE = re.compile(r"^(?:set|raise|change|increase|lower|bump|put)\s+(?:my |the |your |our )?(?:daily )?(?:budget|spending limit|limit|spend limit)"
                       r"\s+(?:up |down )?to\s+\$?(\d+(?:\.\d+)?)\s*(?:dollars?|bucks)?(\s+(?:for )?today(?: only)?)?$")
JOB_STATUS = {"what are you working on", "how's the background job going", "hows the background job going",
              "background job status", "status of the background job", "what's running in the background",
              "whats running in the background", "any background jobs", "how are the background jobs going"}
JOB_CANCEL = {"cancel the background job", "cancel background jobs", "stop the background job", "stop background jobs",
              "cancel all background jobs", "stop working on that in the background"}
CONNECTOR_RELOAD = {"reload your connectors", "reload connectors", "reconnect your connectors", "refresh connectors",
                    "refresh your connectors", "reload mcp"}
CONNECTOR_LIST = {"what connectors do you have", "list your connectors", "what apps are you connected to",
                  "what are you connected to", "which connectors are connected"}
UPDATE_WORDS = {"update yourself", "install the update", "update", "check for updates", "is there an update",
                "upgrade yourself", "update jarvis", "update ultron", "install your update", "install the new version",
                "are there any updates", "any updates"}
UPDATE_RE = re.compile(r"^(?:(?:can|could|would|will) you |please |go |)(?:check|look|search)(?: for| if there(?:'s| is| are))? (?:an |any |a |your |your own |new |the )*(?:personal )?updates?\b"
                       r"|^(?:(?:can|could) you |please |go |)update (?:yourself|jarvis|ultron|you)\b"
                       r"|^(?:do you have|is there|are there|got) (?:an |any |a )?(?:new )?updates?(?: for you| for yourself)?$"
                       r"|\byour own (?:personal )?updates?\b")
ROLLBACK_WORDS = {"undo the update", "roll back", "rollback", "roll back the update", "revert the update",
                  "go back to the old version", "go back to the last version", "undo your update"}
DISCORD_CHECK = {"read my discord messages", "read my discord", "any new discord messages", "any discord messages",
                 "what did i miss on discord", "check discord", "check my discord", "read discord", "new discord messages",
                 "do i have any discord messages", "any messages on discord", "did anyone message me on discord",
                 "read me my discord messages", "what's new on discord", "whats new on discord"}
DISCORD_OFF = {"stop reading my discord messages", "don't read my discord messages", "dont read my discord messages",
               "stop reading discord", "stop reading my messages", "don't read my messages", "dont read my messages",
               "be quiet about discord", "stop announcing discord messages", "discord announcements off"}
DISCORD_ON = {"read my discord messages out loud", "start reading my discord messages", "read discord messages out loud",
              "read my messages out loud", "announce my discord messages", "discord announcements on",
              "tell me when i get discord messages", "read new discord messages"}
EMAIL_ANNOUNCE_ON = {"tell me when i get emails", "tell me when i get an email", "read new emails out loud",
                     "announce my emails", "email announcements on", "tell me about new emails"}
EMAIL_ANNOUNCE_OFF = {"stop telling me about emails", "stop announcing emails", "email announcements off",
                      "don't tell me about emails", "dont tell me about emails", "be quiet about emails"}
SPOTIFY_STATUS = {"spotify status", "check spotify", "is spotify working", "is spotify set up", "what's up with spotify",
                  "whats up with spotify", "why isn't spotify working", "why isnt spotify working"}
DISCORD_BOT_STATUS = {"discord bot status", "is your discord bot online", "is the discord bot online",
                      "is the discord bot working", "what's up with the discord bot", "whats up with the discord bot",
                      "check the discord bot", "is the bot online"}
DISCORD_SEND_ON = {"turn on discord sending", "enable discord sending", "let you send discord messages",
                   "you can send discord messages", "allow discord messages", "discord sending on", "turn discord sending on"}
DISCORD_SEND_OFF = {"turn off discord sending", "disable discord sending", "stop sending discord messages",
                    "don't send discord messages", "dont send discord messages", "discord sending off", "turn discord sending off"}
AUTOSTART_ON = {"start with windows", "start when windows starts", "launch on startup", "start on startup", "open on startup",
                "run at startup", "run on startup", "start when my computer starts", "start when my pc starts",
                "make yourself a startup app", "add yourself to startup", "start automatically", "launch with windows"}
AUTOSTART_OFF = {"don't start with windows", "dont start with windows", "stop starting with windows", "remove yourself from startup",
                 "don't launch on startup", "dont launch on startup", "don't start automatically", "dont start automatically",
                 "turn off startup", "disable startup", "stop launching on startup"}

# Talking to both at once
DUO_ON_WORDS = {"both of you", "you two", "you both", "both", "duo", "duo mode", "team up", "join in", "join",
                "both of you join in", "join the conversation", "bring ultron in", "bring jarvis in", "bring him in",
                "talk together", "together", "both of you together", "group mode", "group chat", "everyone",
                "talk to both of you", "i want to talk to both of you", "both of you talk"}
DUO_OFF_WORDS = {"just you", "only you", "solo", "solo mode", "one at a time", "just one of you", "only one of you",
                 "just", "only", "by yourself", "just you now", "only you now", "leave", "you can go", "dismissed"}
GROUP_RE = re.compile(r"\b(both of you|you two|you both|each of you|the two of you|you guys|y'?all)\b", re.I)
SWITCH_RE = re.compile(r"\b(switch|swap|change|flip|hand)\b.*\b(other|next|ultron|jarvis|ai|assistant|personality|persona|over)\b"
                       r"|\b(let me|i want to|can i) (talk|speak) (to|with) (ultron|jarvis|the other)\b"
                       r"|\bbring (back )?(ultron|jarvis)\b", re.I)


def _words(t):
    return re.findall(r"[a-z0-9']+", t.lower())


def is_yes(text):
    w = _words(text)
    if not w or any(x in NO_HINTS for x in w):
        return False
    return w[0] in YES_WORDS or " ".join(w[:2]) in {"go ahead", "do it"}


ALWAYS_RE = re.compile(r"\b(always|don'?t ask (me )?(that )?again|stop asking|never ask)\b", re.I)


def is_always(text):
    """"Yes, always" / "always allow" / "don't ask again": approve and stop asking for this kind of thing."""
    w = _words(text)
    if not w or w[0] in {"no", "nope", "nah", "deny", "cancel", "abort", "negative"}:
        return False
    return bool(ALWAYS_RE.search(text))


def is_no(text):
    w = _words(text)
    return bool(w) and (w[0] in NO_HINTS or "don't" in w or "dont" in w)


def is_stop(text):
    return " ".join(_words(text)) in STOP_WORDS


def _alias(tok):
    t = tok.lower().strip("'")
    if t.endswith("'s"):
        return None      # "Jarvis's ..." is talking ABOUT him, not to him
    for key, p in personas.PERSONAS.items():
        if t in p["aliases"]:
            return key
        if len(t) >= 5 and difflib.SequenceMatcher(None, t, key).ratio() >= 0.8:
            return key
    return None


def keep_end(rest, text):
    """find_address strips punctuation; put back the ? or . Whisper heard at the end (it tells us you're done)."""
    end = text.rstrip()[-1:] if text.strip() else ""
    return rest + end if rest and end in ".?!" and not rest.endswith((".", "?", "!")) else rest


def find_address(text):
    """If the AI is addressed by name at the START or END ("Jarvis, open X" / "open X, Jarvis"),
    return (persona_key, the rest of the sentence). Otherwise (None, text)."""
    toks = [(m.group(0), m.start(), m.end()) for m in re.finditer(r"[A-Za-z']+", text)]
    if not toks:
        return None, text
    i = 0
    while i < len(toks) - 1 and i < 3 and toks[i][0].lower() in FILLERS:
        i += 1
    key = _alias(toks[i][0])
    if key:
        return key, text[toks[i][2]:].strip(" ,.!?;:-")
    j = len(toks) - 1
    if j > 0 and toks[j][0].lower() in TRAILING_POLITE:
        j -= 1
    key = _alias(toks[j][0])
    if key:
        return key, text[:toks[j][1]].strip(" ,.!?;:-")
    return None, text


QUESTION_START = {"what", "whats", "what's", "who", "whos", "who's", "when", "where", "why", "how", "hows", "how's",
                  "is", "are", "can", "could", "do", "does", "did", "should", "will", "would", "which", "was", "were"}


def looks_complete(text):
    """Is this a finished command or question (so he can answer right away), judging by the words and by
    the punctuation Whisper adds when it hears your voice drop at the end of a sentence?"""
    w = _words(text)
    content = [x for x in w if x not in FILLERS]
    if not content:
        return False                                   # just his name: you're probably about to say more
    whole = " ".join(w)
    if (whole in QUIT_WORDS or whole in HIDE_WORDS or whole in SHOW_WORDS or whole in MUTE_WORDS
            or whole in RESET_WORDS or whole in STOP_WORDS or whole in BRIEF_WORDS or whole in DICTATE_START
            or whole in DUO_ON_WORDS or is_yes(text) or is_no(text)):
        return True
    s = text.rstrip()
    if s.endswith((",", "-", "...", "…", ":")) or w[-1] in DANGLING:
        return False
    if intents.recognize(text):
        return True
    if s.endswith(("?", "!", ".")) and len(content) >= 2:
        return True
    return len(content) >= 3 and w[0] in QUESTION_START and s.endswith("?")


RECAP_RE = re.compile(
    r"^\s*(done|all done|all set|there you go|there we go|okay,? done|sorted|finished|complete|it'?s done)\b"
    r"|^\s*(i'?ve|i have|i)\s+(just\s+)?(opened|started|launched|set|turned|put|closed|paused|resumed|skipped|played|queued|"
    r"switched|muted|unmuted|changed|made|created|sent|saved|minimized|maximized|locked|pulled up|brought up)\b"
    r"|^\s*[\w' ]{1,40}\b(is|are|'s)\s+(now\s+)?(open|opened|playing|running|up|on|off|set|closed|paused|muted|done)\s*[.!]*\s*$", re.I)
NEWS_RE = re.compile(r"\b(but|couldn'?t|can'?t|failed|error|didn'?t|unable|however|instead|wasn'?t|isn'?t|not)\b", re.I)


def is_recap(sentence, said_before):
    """After he's already said what he's doing ("Opening Spotify."), is this sentence just the same news again
    ("Done." / "I've opened Spotify." / "Spotify's open.")? Failures, numbers and anything new are never dropped,
    and if he said nothing before acting, the confirmation is kept (it's the only thing you'd hear)."""
    s = (sentence or "").strip()
    before = (said_before or "").strip()
    if not s or not before or len(s.split()) > 16 or NEWS_RE.search(s):
        return False
    if set(re.findall(r"\d+", s)) - set(re.findall(r"\d+", before)):
        return False                                        # a number he hadn't said yet is news
    if RECAP_RE.search(s):
        return True
    stem = lambda w: re.sub(r"(ing|ed|es|s)$", "", w) if len(w) > 4 else w
    words = lambda t: {stem(w) for w in re.findall(r"[a-z']{3,}", t.lower())} - {"the", "your", "you", "for", "now", "and", "just", "it's"}
    a, b = words(s), words(before)
    return bool(a) and len(a & b) / len(a) >= .6


from settings import write_env  # noqa: E402  (kept here for older callers)


class Core:
    def __init__(self, emit, voice=True):
        self._emit_out = emit
        self._turn_who = {}
        self._confirm_lock = threading.Lock()
        try:
            import history
            self.history = history.History()
            tools.set_history(self.history)
        except Exception as e:
            print(f"[history] conversation memory unavailable: {e}")
            self.history = None
        self.want_voice = voice
        self.events = queue.Queue()
        self.brains = {}
        st = self._load_state()
        self.persona_key = st.get("persona", "jarvis")
        self.duo = bool(st.get("duo", False))   # "both of you" mode: every request goes to both
        self._duo_once = None             # lead key for a one-off duo turn ("Jarvis and Ultron?" then the question)
        self._duo_capture = None          # tool results from the lead, handed to the second
        if self.persona_key not in personas.PERSONAS:     # e.g. left on a retired persona
            self.persona_key = "jarvis"
            self._save_state()
        self.listener = None
        try:
            voice_settings.apply_saved()             # voices you picked in Settings (or by asking)
        except Exception as e:
            print(f"[voice] couldn't load saved voice choices: {e}")
        self.speaker = Speaker(
            on_state=self._speaker_state,
            on_level=lambda v: self.emit({"type": "voice", "v": round(v, 3)}),
            on_sentence=self._on_sentence,
        )
        self.speaker.on_envelope = lambda env, step, delay: self.emit({"type": "voice_env", "env": env, "step": step,
                                                                         "delay": round(delay, 3)})
        self.speaker.set_persona(personas.PERSONAS[self.persona_key])
        tools.set_voice_core(self)
        # Don't start answering while you're still talking (you might be adding to the question)
        self.speaker.wait_user = lambda: ((self._user_talking or time.time() < self._utt_pending_until)
                                          and self.state != "awaiting")
        self.state = "booting"
        self._turn = None
        self._pending = None
        self._plock = threading.Lock()
        self._stop = threading.Event()
        self._engaged_until = 0.0
        self._engaged_from = 0.0
        self._talk_engaged = False
        self._voice_on, self._voice_off_at = False, 0.0
        self.muted = False
        self._mute_timer = None
        self._dictation = None            # {"window": title, "last": text} while dictating
        self._alerted = set()
        self._ram_hot = 0
        self._last_ram_alert = 0.0
        self._hold = None                 # a command he's heard but is giving you a beat to finish
        self._user_talking = False
        self._utt_pending_until = 0.0
        self._hold_lock = threading.Lock()
        self._spoken = []                 # (time, sentence) recently said; used to ignore his own echo
        self._wake_audio = {}
        self.brain_error = None
        self.on_quit = lambda: None
        self.on_minimize = lambda: False   # set by the app; returns True if it hid a window
        self.on_restore = lambda: False
        tools.set_confirm_handler(self.confirm)
        tools.set_dictation_handler(lambda window=None: self.events.put(("dictate", window)))
        tools.set_mute_handler(lambda minutes: self.set_muted(True, minutes=minutes, speak=False))
        tools.set_self_window_handler(lambda show: self.on_restore() if show else self.on_minimize())

    # ================================================================ persona
    @property
    def persona(self):
        return personas.PERSONAS[self.persona_key]

    @property
    def brain(self):
        return self._brain_for(self.persona_key)

    def _brain_for(self, key):
        if self.brain_error:
            return None
        if key not in self.brains:
            from brain import Brain
            self.brains[key] = Brain(persona=key, on_tool=self._on_tool)
        return self.brains[key]

    def _state_file(self):
        return config.JARVIS_DIR / "state.json"

    def _load_state(self):
        try:
            return json.loads(self._state_file().read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_state(self):
        try:
            self._state_file().parent.mkdir(parents=True, exist_ok=True)
            self._state_file().write_text(json.dumps({"persona": self.persona_key, "duo": self.duo}), encoding="utf-8")
        except Exception:
            pass

    def _emit_persona(self):
        p = self.persona
        self.emit({"type": "persona", "key": self.persona_key, "name": p["name"], "wordmark": p["wordmark"]})

    def _become(self, key, voice=True):
        """Hand the floor to one of them: HUD theme, voice, echo filter all follow."""
        if key == self.persona_key:
            if voice:
                self.speaker.set_persona(self.persona)
            return
        self.persona_key = key
        if voice:
            self.speaker.set_persona(self.persona)
        self._emit_persona()

    # ================================================================ lifecycle
    def start(self):
        threading.Thread(target=self._boot, daemon=True, name="boot").start()

    def shutdown(self):
        if getattr(self, "_shut", False):
            return
        self._shut = True
        self._stop.set()
        self.interrupt()
        if self.listener:
            self.listener.stop()
        tools.REMINDERS.stop()

    def _log(self, line):
        print(line)
        self.emit({"type": "boot", "line": line})

    def _purge_retired(self):
        """Juno was retired: remove every trace she left on disk (memories about her, her cached
        voice, and the saved 'last persona' if it was her). Safe to run every boot."""
        removed = []
        try:
            mem = tools.memories()
            keep = [m for m in mem if not re.search(r"\b(juno|juneau)\b", m.get("text", ""), re.I)]
            if len(keep) != len(mem):
                tools.MEMORY.save(keep)
                removed.append(f"{len(mem) - len(keep)} memories")
            r = tools.routines()
            keep_r = {k: v for k, v in r.items() if not re.search(r"\b(juno|juneau)\b", f"{k} {v.get('steps', '')}", re.I)}
            if len(keep_r) != len(r):
                tools.ROUTINES.save(keep_r)
                removed.append(f"{len(r) - len(keep_r)} routines")
            for f in config.CACHE_DIR.glob("wake_juno_*"):
                f.unlink(missing_ok=True)
                removed.append(f.name)
        except Exception as e:
            print(f"[purge] {e}")
        if removed:
            print(f"[purge] removed Juno data: {', '.join(removed)}")

    def _boot(self):
        config.JARVIS_DIR.mkdir(parents=True, exist_ok=True)
        self._purge_retired()
        self._emit_persona()
        self.emit({"type": "duo", "on": self.duo})
        self._log("INITIALIZING CORE SYSTEMS")
        # Faster startup: the voice loads at the same time as everything else instead of after it
        self._log("LOADING VOICE SYNTHESIS")
        voice_loader = threading.Thread(target=self.speaker.prepare, kwargs={"log": self._log},
                                        daemon=True, name="voice-load")
        voice_loader.start()
        try:
            import health
            for prob in health.onnx_problems():
                self._log(f"REPAIR NEEDED: {prob}. RUN fix_gpu.bat")
                self.emit({"type": "msg", "role": "system",
                           "text": f"Speech libraries need a repair: {prob}. Close Jarvis and double-click fix_gpu.bat."})
        except Exception:
            pass
        try:
            _ = self.brain
            self._log(f"NEURAL LINK ESTABLISHED  [{config.MODEL}]")
        except SystemExit as e:
            self.brain_error = str(e)
            self._log(f"NEURAL LINK FAILED: {e}")
            if not config.ANTHROPIC_API_KEY or "paste-yours" in config.ANTHROPIC_API_KEY:
                self.brain_error = "He needs a Claude API key. Click API keys in the System panel (or paste it in the setup card)."
                self.emit_key_status(reason="")
            else:
                self.emit({"type": "msg", "role": "system", "text": str(e)})
        except Exception as e:
            self.brain_error = str(e)
            self._log(f"NEURAL LINK FAILED: {e}")

        # First run: nothing else starts until setup is done. No microphone, no talking, no background
        # services, so he can't half-work (and repeat "I need a key" at everything he hears) before he's ready.
        if not self._has_key():
            voice_loader.join()
            threading.Thread(target=self._loop, daemon=True, name="core").start()     # typing still answers
            self._log("SETUP NEEDED  [ADD YOUR CLAUDE API KEY]")
            self.emit({"type": "ready", "model": config.MODEL, "voice": False, "setup": True})
            self.set_state("idle")
            self.emit_key_status(reason="")
            return
        voice_loader.join()
        self._first_voice_download()

        threading.Thread(target=self._loop, daemon=True, name="core").start()
        threading.Thread(target=self._telemetry, daemon=True, name="telemetry").start()
        tools.REMINDERS.start(on_due=lambda msg, late: self.events.put(("reminder", (msg, late))))
        self._log(f"TOOL MATRIX ONLINE  [{len(tools.TOOL_SPECS) + 1} capabilities]")
        if tools.IS_WINDOWS:
            threading.Thread(target=tools._start_apps, daemon=True, name="app-index").start()


        if self.want_voice:
            self._log("LOADING SPEECH RECOGNITION")
            try:
                from speech import Listener
                self.listener = Listener(
                    log=self._log,
                    on_utterance=self.on_utterance,
                    on_speech=self._on_speech,
                    on_level=lambda v: self.emit({"type": "level", "v": round(v, 3)}),
                    on_peek=self._peek,
                    stream_gate=lambda t: (not self.muted and not self._dictation and self._maybe_for_us(t)),
                    needs_careful=lambda t: not self._is_quick_cmd(t),
                )
                self.listener.expecting = lambda: (self._hold is not None or self._turn is not None
                                                   or self._engaged() or self._pending is not None)
                self.listener.start()
                self._log('ALWAYS LISTENING  [SAY "JARVIS" OR "ULTRON"]')
                self._start_hotkey()
            except Exception as e:
                self.listener = None
                self._log(f"MICROPHONE OFFLINE: {type(e).__name__}: {e}")
        else:
            self._log("VOICE INPUT DISABLED")

        self._log(f"VOICE SYNTHESIS ONLINE  [{self.speaker.engine_name.upper()}]")
        self._wake_for(self.persona_key)
        self.emit({"type": "ready", "model": config.MODEL, "voice": self.listener is not None})
        threading.Thread(target=self._warm_phrases, daemon=True, name="phrase-warm").start()
        self.set_state("idle")
        h = datetime.now().hour
        part = "morning" if 4 <= h < 12 else "afternoon" if 12 <= h < 18 else "evening"
        self._emit_autostart()
        self._start_discord()
        self._start_discord_bot()
        self._start_email()
        self._start_netflix()
        threading.Thread(target=self._start_connectors, daemon=True, name="connectors-start").start()
        self._start_jobs()
        for old in (config.BASE_DIR / "creator.id", config.JARVIS_DIR / "voiceprint.json"):
            try:                                # left over from removed features (owner PC, voice lock)
                old.unlink()
            except OSError:
                pass
        last_seen = self._state_flag("last_seen") or 0
        threading.Thread(target=self._wake_watch, daemon=True, name="wake-watch").start()
        if not self.brain_error:
            if self._briefing_due():
                self._brief_from = last_seen
                self.events.put(("brief", None))
            else:
                self.events.put(("say", self.persona["greeting"].format(part=part, address=config.ADDRESS_AS)))
        self._update_check()

    # ================================================================ state helpers
    def set_state(self, s):
        self.state = s
        self.emit({"type": "state", "state": s})

    def _rest_state(self):
        if self._dictation:
            return "dictating"
        return "listening" if self._engaged() else "idle"

    def _engage(self, seconds=None):
        """Accept the next thing said without the name. The window is how long you have to START talking:
        a sentence you began inside it counts however long it takes to transcribe."""
        secs = seconds or config.FOLLOW_UP_TIMEOUT
        now = time.time()
        self._engaged_from, self._engaged_until = now, now + secs
        self._talk_engaged = False
        threading.Timer(secs + 0.1, self._expire_listening).start()

    def _expire_listening(self):
        if time.time() < self._engaged_until or self.state != "listening":
            return
        if self._talk_engaged and time.time() < self._engaged_until + 20:
            threading.Timer(0.5, self._expire_listening).start()     # your sentence is still coming in: still listening
            return
        self.set_state(self._rest_state())

    def _engaged(self):
        """Is he taking things said without his name right now (or the sentence you're in the middle of)?"""
        return time.time() < self._engaged_until or self._talk_engaged

    def _started_engaged(self, ended, audio):
        """Did this sentence START while the window was open? (It may have finished, or been transcribed,
        after it closed: on a slow PC that's what made him ignore you and drop back to standby.)"""
        if time.time() < self._engaged_until:
            return True
        if not self._engaged_until:
            return False
        start = ended - (len(audio) / 16000 if audio is not None else 0.0)
        return ended >= self._engaged_from and start <= self._engaged_until + 0.4

    def _speaker_state(self, s):
        if s == "speaking":
            self._voice_on = True
        elif self._voice_on:
            self._voice_on, self._voice_off_at = False, time.time()
        if s == "speaking":
            if self._turn:
                self._turn["spoke"] = True
            if self.state != "awaiting":
                self.set_state("speaking")
        elif s == "waiting" and self._turn:
            self.set_state("thinking")

    def _on_sentence(self, text, who=None):
        self._spoken.append((time.time(), text))
        self._spoken = self._spoken[-20:]
        ev = {"type": "caption", "text": text}
        if who:
            ev["who"] = who                     # in Both mode, the HUD steps whoever's actually talking forward
        self.emit(ev)

    def _on_tool(self, name, args, result):
        self.emit({"type": "tool", "name": name, "args": args, "result": result})
        if self._duo_capture is not None:
            self._duo_capture.append(f"{name.replace('_', ' ')} ({str(result)[:90]})")
        if name == "reminders":
            self._emit_reminders()
        if name == "memory":
            self._emit_knowledge()

    def speak(self, text):
        self.speaker.say(text)

    # ================================================================ wake reply ("Yes?")
    def _wake_for(self, key):
        if key in self._wake_audio:
            return self._wake_audio[key]
        p = personas.PERSONAS[key]
        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        items = []
        sig = "{voice}-{speed}-{pitch}".format(voice=p.get("voice"), speed=p.get("speed"), pitch=p.get("pitch", 1.0))
        sig = re.sub(r"[^a-z0-9.-]+", "", sig.lower())      # a changed voice gets fresh "Yes?" recordings
        for phrase in p["wake_replies"]:
            safe = re.sub(r"[^a-z0-9]+", "_", phrase.lower()).strip("_") or "wake"
            items.append((phrase, self.speaker.cache(phrase, path=config.CACHE_DIR / f"wake_{key}_{sig}_{safe}.mp3")))
        self._wake_audio[key] = items
        return items

    def _wake(self):
        self._engage()
        self.set_state("listening")
        items = self._wake_for(self.persona_key)
        if not items:
            return
        phrase, audio = random.choice(items)
        self._spoken.append((time.time(), phrase))
        self.emit({"type": "caption", "text": phrase})
        if audio is not None:
            self.speaker.play(audio)
        else:
            self.speaker.say(phrase)
        self._engage()          # the window starts after he's finished saying it
        self.set_state("listening")

    # ================================================================ echo filter
    def _is_echo(self, text, started=None):
        """True if the mic just heard the AI's own voice (speakers, no headphones).
        started: when this sentence began. If he'd already been quiet for a moment by then, it's you,
        even when you repeat his words back ("want me to play Blinding Lights?" "play Blinding Lights")."""
        now = time.time()
        words = _words(text)
        if not words:
            return True
        if (started is not None and not self._voice_on and started > self._voice_off_at + ECHO_TAIL
                and not (self._turn and self._turn.get("spoke"))):
            return False
        recent = [s for (t, s) in self._spoken if now - t < 15]
        if self._turn and self._turn.get("stream"):
            recent += self._turn["stream"].spoken[-4:]
        recent_words = set()
        for s in recent:
            sw = _words(s)
            recent_words.update(sw)
            if difflib.SequenceMatcher(None, words, sw).ratio() >= 0.6:
                return True
        overlap = 0.6 if self.persona.get("effect") else 0.8     # Ultron's metallic voice transcribes messily
        if len(words) >= 3 and sum(w in recent_words for w in words) / len(words) >= overlap:
            return True
        return False

    # ================================================================ input
    def _maybe_for_us(self, text):
        """Cheap check on the fast transcript: could this be aimed at the AI? (name, near-name,
        or we're expecting an answer). If yes, it's worth the accurate second pass."""
        if self._hold or self._turn or self._engaged():
            return True
        toks = _words(text)
        edge = toks[:4] + toks[-3:]
        for t in edge:
            if _alias(t):
                return True
            for name in personas.PERSONAS:
                if len(t) >= 3 and (difflib.SequenceMatcher(None, t, name).ratio() >= 0.6
                                    or t.startswith(name[:3])):
                    return True
        return False

    def on_utterance(self, text, ended=None, audio=None, refined=False, timing=None):
        """Everything the mic hears comes through here."""
        if timing is not None:
            self._timing = timing
        try:
            self._on_utterance(text, ended, audio, refined)
        finally:
            self._utt_pending_until = 0.0         # decided what to do with it: he may talk again
            if not self._user_talking:
                self._talk_engaged = False

    def _on_utterance(self, text, ended=None, audio=None, refined=False):
        ended = ended or time.time()
        started = ended - len(audio) / 16000 if audio is not None else None
        if self.muted:
            return
        if self._is_echo(text, started):
            print(f"[heard own voice, ignored] {text}")
            return
        if self._dictation:
            if audio is not None and self.listener:
                text = self.listener.refine(audio) or text       # accuracy matters when it's being typed
            key, rest = find_address(text)
            said = " ".join(_words(rest if key else text))
            if (key and (said in DICTATE_STOP or is_stop(rest))) or said in ("stop dictating", "stop dictation", "end dictation"):
                self.events.put(("dictate_stop", None))
            else:
                self._dictate(text)
            return
        with self._plock:
            awaiting_answer = self._pending is not None
        quick_cmd = self._is_quick_cmd(text)
        if quick_cmd:
            refined = True                   # "pause", "volume 30"... the fast transcript is plenty, skip the slow pass
        if (audio is not None and self.listener and not refined and self.listener.careful_too_slow(len(audio) / 16000)):
            print("[voice] careful pass would be too slow on this PC; using the quick transcript")
            refined = True
        if audio is not None and self.listener and not refined and not awaiting_answer and self._maybe_for_us(text):
            t0 = time.time()
            better = self.listener.refine(audio)          # careful second pass, only for speech aimed at him
            if getattr(self, "_timing", None) is not None:
                self._timing["careful"] = self._timing.get("careful", 0) + time.time() - t0
            if better and better.lower().strip(" .!?,") not in ("", "you", "thank you"):
                if better != text:
                    print(f"[refined] {text!r} -> {better!r}")
                text = better
                if self._is_echo(text, started):
                    return
        key, rest = find_address(text)

        with self._plock:
            pending = self._pending
        if pending:
            answer = rest if key else text
            if is_always(answer) or is_yes(answer) or is_no(answer):
                self.emit({"type": "msg", "role": "user", "text": text})
                self.resolve_confirm(pending["id"], is_always(answer) or is_yes(answer), always=is_always(answer))
                return
            if not pending.get("job"):
                return               # mid-request card: only an answer counts
            # a background job's card is up, but this is something else: handle it normally

        engaged = self._started_engaged(ended, audio)
        turn = self._turn
        self.emit({"type": "heard", "text": text, "addressed": bool(key or engaged or turn)})

        if turn:
            if key or is_stop(text):
                print(f"[interrupt] {text}")
                self.interrupt()
                if key and key != self.persona_key:
                    self.events.put(("switch", (key, rest, "voice", ended)))
                elif key and rest and not is_stop(rest):
                    self.events.put(("text", ("voice", rest, ended)))
                elif key and not rest:
                    self.events.put(("wake", None))
                return
            if (not turn["spoke"] and turn["source"] == "voice"
                    and ended - turn["utt_end"] <= config.MERGE_SECONDS + 3):
                # you paused mid-command and kept going: start over with the whole thing
                print(f"[merge] {turn['text_in']!r} + {text!r}")
                self.interrupt()
                self.events.put(("text", ("voice", f"{turn['text_in']} {text}", ended)))
                return
            print(f"[heard while busy, ignored] {text}")
            return

        if self._hold:                    # still finishing a command: this is the rest of it
            self._hold_command(None, keep_end(rest, text) if key else text, ended)
            return
        if key:
            self._hold_command(key, keep_end(rest, text), ended)
            return
        if engaged:
            self._engaged_until, self._talk_engaged = 0, False
            self._hold_command(None, text, ended)
            return
        print(f"[heard, not addressed] {text}")

    def _is_quick_cmd(self, text):
        k0, r0 = find_address(text)
        return bool((k0 or self._engaged()) and intents.recognize(r0 if k0 else text))

    def _peek(self, fast_text, audio, addressed=False):
        """A quick look at what you've said after a short pause. Returns the careful transcript if
        it's a finished request aimed at him (so the sentence ends now), else None (keep listening)."""
        if self.muted or self._dictation:
            return None
        turn = self._turn
        if turn and turn["spoke"]:
            return None                        # he's already answering: interrupting is the normal path's job
        with self._plock:
            pending = self._pending
        if pending and (is_always(fast_text) or is_yes(fast_text) or is_no(fast_text)):
            return fast_text
        if pending and not pending.get("job"):
            return None
        if addressed:                        # live transcription already confirmed it's for him; this is just the ending
            if looks_complete(fast_text):
                print(f"[quick finish] ...{fast_text!r}")
                return fast_text
            return None
        if not self._maybe_for_us(fast_text):
            return None
        text = fast_text                     # the careful pass runs once, after the sentence ends
        if self._is_echo(text):
            return None
        key, rest = find_address(text)
        engaged = self._engaged() or self._hold is not None or turn is not None
        if not key and not engaged:
            return None
        if looks_complete(keep_end(rest, text) if key else text):
            print(f"[quick finish] {text!r}")
            return text
        return None

    # ================================================================ "let me finish"
    def _hold_for(self, text, name_only=False):
        if name_only:
            return config.HOLD_NAME_ONLY
        w = _words(text)
        if not w or w[-1] in DANGLING or text.rstrip().endswith((",", "-", "...", "…")):
            return config.HOLD_UNFINISHED
        if config.SMART_ENDPOINT and looks_complete(text):
            return config.HOLD_COMPLETE          # clearly finished: barely wait
        return config.HOLD_SECONDS

    def _hold_command(self, key, text, ended):
        """Don't answer instantly: give the user a beat to keep talking, and merge if they do."""
        with self._hold_lock:
            h = self._hold
            if h:
                if h.get("timer"):
                    h["timer"].cancel()
                h["text"] = f"{h['text']} {text}".strip()
                h["ended"] = ended
            else:
                h = self._hold = {"key": key, "text": text.strip(), "ended": ended, "timer": None}
            name_only = not [w for w in _words(h["text"]) if w not in FILLERS]
            self._arm_hold(self._hold_for(h["text"], name_only))
        self.set_state("listening")
        if h["text"]:
            self.emit({"type": "caption", "text": h["text"] + " …"})

    def _arm_hold(self, secs):
        h = self._hold
        if not h:
            return
        if h.get("timer"):
            h["timer"].cancel()
        h["timer"] = threading.Timer(secs, self._release_hold)
        h["timer"].daemon = True
        h["timer"].start()

    def _on_speech(self, active):
        """Mic says you started/stopped talking. While a command is on hold, starting to
        talk again pauses the countdown; stopping restarts it (plus time to transcribe)."""
        self._user_talking = active
        now = time.time()
        if not active:
            self._utt_pending_until = now + 3      # your sentence is being transcribed: don't talk over it yet
        if active:
            self._talk_engaged = now < self._engaged_until               # you started inside the window
        if active and self.brain:
            self.brain.warm()          # open the connection to Claude while you're still talking
        if active and self.listener is not None and self.listener.cloud is not None:
            self.listener.cloud.warm()
        with self._hold_lock:
            if not self._hold:
                return
            if active:
                self._arm_hold(config.MAX_RECORD_SECONDS + 3)   # safety net only
            else:
                self._arm_hold(config.HOLD_SECONDS + 1.5)

    def _release_hold(self):
        with self._hold_lock:
            h, self._hold = self._hold, None
        if not h:
            return
        key, text, ended = h["key"], h["text"], h["ended"]
        has_words = bool([w for w in _words(text) if w not in FILLERS])
        if key and key != self.persona_key:
            self.events.put(("switch", (key, text if has_words else "", "voice", ended)))
        elif has_words:
            self.events.put(("text", ("voice", text, ended)))
        else:
            self.events.put(("wake", None))

    def submit(self, text, source="typed"):
        """Typed commands from the app or console. No name needed."""
        text = (text or "").strip()
        if not text:
            return
        with self._plock:
            pending = self._pending
        if pending and (is_always(text) or is_yes(text) or is_no(text) or not pending.get("job")):
            self.emit({"type": "msg", "role": "user", "text": text})
            self.resolve_confirm(pending["id"], is_always(text) or is_yes(text), always=is_always(text))
            return
        low = " ".join(_words(text))
        if low in ("unmute", "unmute yourself", "mic on", "start listening", "listen"):
            self.set_muted(False)
            return
        key, rest = find_address(text)           # typing a name works like saying it
        if key and rest:
            if key != self.persona_key:
                self.events.put(("switch", (key, rest, source, time.time())))
                return
            text = rest
        self.events.put(("text", (source, text, time.time())))

    def push_to_talk(self):
        if self.listener:
            self.interrupt()
            self.events.put(("wake", None))
        else:
            self.emit({"type": "toast", "text": "Microphone is offline."})

    def switch_persona(self, key=None):
        self.interrupt()
        if key == "both":
            self.events.put(("duo", True))
            return
        if self.duo:
            self.events.put(("duo_off_quiet", None))
        self.events.put(("switch", (key or personas.other(self.persona_key), "", "typed", time.time())))

    def interrupt(self):
        """Stop talking and abandon the current answer."""
        turn = self._turn
        if turn:
            turn["interrupted"] = True
            turn["cancel"].set()
            turn["stream"].cancel()
        self.speaker.stop()

    def stop_speaking(self):
        self.interrupt()

    # ================================================================ approval gate
    def confirm(self, title, detail="", category=None):
        """Called from a tool (in the core thread). Blocks until approved, denied or timed out.
        Fast on purpose: the card shows and answers are accepted the instant this is called; the
        spoken cue is two words and plays in the background once he's finished his sentence."""
        if category and permissions.allowed(category):
            self.emit({"type": "msg", "role": "system", "text": f"Allowed (always): {title}"})
            return True
        job_id = getattr(tools._CTX, "job", None)
        job = self.jobs.jobs.get(job_id) if job_id and getattr(self, "jobs", None) else None
        if job is not None:
            title = f"Background job {job.id}: {title[0].lower() + title[1:]}"
        with self._confirm_lock:                  # one approval card at a time (a job and you might both need one)
            return self._confirm_one(title, detail, category, job)

    def _confirm_one(self, title, detail, category, job):
        can_always = permissions.can_always(category)
        p = {"id": uuid.uuid4().hex[:8], "event": threading.Event(), "approved": False, "always": False,
             "job": job is not None}
        with self._plock:
            self._pending = p
        label = permissions.CATEGORIES[category][0] if can_always else None
        self.emit({"type": "confirm", "id": p["id"], "title": title, "detail": detail,
                   "timeout": config.CONFIRM_TIMEOUT, "category": category if can_always else None,
                   "can_always": can_always, "always_label": label,
                   "keys": {"yes": config.APPROVE_HOTKEY, "no": config.DENY_HOTKEY}})
        self.set_state("awaiting")
        threading.Thread(target=self._confirm_cue, args=(p,), daemon=True, name="confirm-cue").start()
        cancel = job.cancel if job is not None else (self._turn["cancel"] if self._turn else threading.Event())
        end = time.time() + config.CONFIRM_TIMEOUT
        while not p["event"].wait(0.1):
            if time.time() > end or cancel.is_set():
                break
        with self._plock:
            self._pending = None
        approved = p["approved"]
        if approved and p["always"] and can_always:
            permissions.set_always(category)
            self._emit_permissions()
        self.emit({"type": "confirm_done", "id": p["id"], "approved": approved, "always": bool(approved and p["always"])})
        verdict = ("Allowed, and won't ask again" if p["always"] else "Allowed") if approved else (
            "Denied" if p["event"].is_set() else "No answer, so denied")
        self.emit({"type": "msg", "role": "system", "text": f"{verdict}: {title}"})
        self.set_state("thinking" if job is None and self._turn else self._rest_state())
        return approved

    def _confirm_cue(self, p):
        """Say "Approve?" once he's done with the sentence he's on (never more than a few seconds' wait),
        unless you've already answered by then."""
        turn = self._turn
        stream = turn.get("stream") if turn else None
        if stream is not None:
            t = threading.Thread(target=stream.drain, kwargs={"timeout": 6}, daemon=True)
            t.start()
            while t.is_alive() and not p["event"].is_set():
                t.join(0.1)
        if p["event"].is_set() or self._pending is not p:
            return
        cue = self.persona.get("confirm_cue") or "Approve?"
        self._spoken.append((time.time(), cue))
        self.emit({"type": "caption", "text": cue})
        try:
            self.speaker.say(cue)
        except Exception as e:
            print(f"[confirm] cue failed: {e}")

    def resolve_confirm(self, cid, approved, always=False):
        with self._plock:
            p = self._pending
        if p and (p["id"] == cid or cid in (None, "", "*")):
            p["approved"] = bool(approved)
            p["always"] = bool(always and approved)
            p["event"].set()
            return True
        return False

    def set_permission(self, key, on):
        """From the settings panel: switch a category's 'always allow' on or off."""
        if key == "*" and not on:
            permissions.reset()
        else:
            permissions.set_always(key, bool(on))
        self._emit_permissions()

    def _emit_permissions(self):
        self.emit({"type": "permissions", "items": permissions.state(),
                   "keys": {"yes": config.APPROVE_HOTKEY, "no": config.DENY_HOTKEY}})

    # ================================================================ main loop
    def _loop(self):
        tools._com_init()
        while not self._stop.is_set():
            try:
                kind, payload = self.events.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._handle(kind, payload)
            except Exception as e:
                traceback.print_exc()
                self.emit({"type": "msg", "role": "system", "text": f"Internal error: {e}"})
            finally:
                if self._stop.is_set():
                    return
                self.set_state(self._rest_state())

    def _handle(self, kind, payload):
        if kind == "say":
            self.emit({"type": "msg", "role": "jarvis", "text": payload})
            self.speak(payload)
            return
        if kind == "dictate":
            self._start_dictation(payload)
            return
        if kind == "brief":
            self._briefing(morning=True, source="auto", ended=time.time(), auto=True)
            return
        if kind == "discord":
            self._announce_discord(payload)
            return
        if kind == "job_done":
            self._announce_job(payload)
            return
        if kind == "dictate_stop":
            self._stop_dictation()
            return
        if kind == "alert":
            self.emit({"type": "alert", "text": payload})
            self.emit({"type": "msg", "role": "system", "text": payload})
            self.speak(payload)
            return
        if kind == "say_quiet":
            self.speak(payload)
            return
        if kind == "wake":
            self._wake()
            return
        if kind == "reminder":
            msg, late = payload
            line = f"Reminder: {msg}." if late < 2 else f"You missed a reminder from {round(late)} minutes ago: {msg}."
            self.emit({"type": "alert", "text": line})
            self.emit({"type": "msg", "role": "system", "text": line})
            self._emit_reminders()
            self.speak(line)
            return
        if kind == "duo":
            self._set_duo(bool(payload))
            return
        if kind == "duo_off_quiet":
            self._set_duo(False, speak=False)
            return
        if kind == "switch":
            key, rest, source, ended = payload
            self._switch(key, announce=not rest)
            if rest:
                self._command(rest, source, ended)
            return
        source, text, ended = payload
        self._command(text, source, ended)

    def _switch(self, key, announce=True):
        if key == self.persona_key:
            if announce:
                self.speak("Already here.")
            return
        if self.duo:                       # both are in the room: whoever's named just takes the floor
            self._become(key)
            self._wake_for(key)
            if announce:
                self._wake()
            return
        self.persona_key = key
        self.speaker.set_persona(self.persona)
        self._save_state()
        self._emit_persona()
        self._wake_for(key)
        if announce:
            self.emit({"type": "msg", "role": "jarvis", "text": self.persona["hello"]})
            self.speak(self.persona["hello"])

    def _split_duo(self, text):
        """Is this aimed at BOTH of them? ("Jarvis and Ultron, ...", "Jarvis, what do you two think",
        "Jarvis, what would Ultron say"). The named one has already taken the floor by now.
        Returns (text without the second name, True/False)."""
        other = personas.other(self.persona_key)
        toks = [(m.group(0).lower(), m.start(), m.end()) for m in re.finditer(r"[A-Za-z']+", text)]
        if not toks:
            return text, False
        is_other = lambda t: _alias(t) == other
        # "Jarvis and Ultron, ..." / "Jarvis, Ultron, ..." -> the second name is right at the front
        # (but "Jarvis, Ultron is being rude" is a sentence ABOUT him: keep it whole)
        after = text[toks[0][2]:].lstrip()
        if is_other(toks[0][0]) and (not after or after[0] in ",.!?;:-"):
            return text[toks[0][2]:].strip(" ,.!?;:-&"), True
        if len(toks) > 1 and toks[0][0] in ("and", "plus") and is_other(toks[1][0]):
            return text[toks[1][2]:].strip(" ,.!?;:-&"), True
        # "..., Jarvis and Ultron" / "..., you too Ultron" -> the other name closes the sentence
        if len(toks) > 1 and is_other(toks[-1][0]):
            before = text[:toks[-1][1]].rstrip()
            if toks[-2][0] in ("and", "plus"):
                return text[:toks[-2][1]].strip(" ,.!?;:-&"), True
            if before.endswith((",", "&")):
                return before.strip(" ,.!?;:-&"), True
        # find_address already took the LAST name off "..., Jarvis and Ultron", leaving "..., Jarvis and"
        if len(toks) > 1 and toks[-1][0] in ("and", "plus") and is_other(toks[-2][0]):
            return text[:toks[-2][1]].strip(" ,.!?;:-&"), True
        if GROUP_RE.search(text):
            return text, True
        # mentions the other one ("what does Ultron think", "is Ultron's idea any good")
        for t, _, _ in toks:
            base = t[:-2] if t.endswith("'s") else t
            if is_other(base):
                return text, True
        return text, False

    def _set_duo(self, on, speak=True):
        if on == self.duo:
            if speak:
                self.speak("They're both here already." if on else "Already just me.")
            return
        self.duo = on
        self._save_state()
        self.emit({"type": "duo", "on": on})
        if not speak:
            return
        if on:
            line = self.persona["duo_on"]
            self.emit({"type": "msg", "role": "jarvis", "text": line})
            self.speak(line)
            self._become(personas.other(self.persona_key))
            line = self.persona["duo_join"]
            self.emit({"type": "msg", "role": "jarvis", "text": line})
            self.speak(line)
            self._save_state()
        else:
            line = self.persona["duo_off"]
            self.emit({"type": "msg", "role": "jarvis", "text": line})
            self.speak(line)

    def _wake_duo(self, lead):
        """ "Jarvis and Ultron?" -> both answer to their name, then whatever comes next goes to both."""
        second = personas.other(lead)
        for key in (lead, second):
            self._become(key)
            self._wake_for(key)
            phrase, audio = random.choice(self._wake_for(key))
            self._spoken.append((time.time(), phrase))
            self.emit({"type": "caption", "text": phrase})
            if audio is not None:
                self.speaker.play(audio)
            else:
                self.speaker.say(phrase)
        self._become(lead)
        self._duo_once = lead
        self._engage()
        self.set_state("listening")

    def _command(self, text, source, ended):
        duo_hit = False
        if not SWITCH_RE.search(text):            # "switch to Ultron" names him but isn't for both
            text, duo_hit = self._split_duo(text)
        once, self._duo_once = self._duo_once, None
        if duo_hit and not [w for w in _words(text) if w not in FILLERS]:
            self._wake_duo(self.persona_key)
            return
        self.emit({"type": "msg", "role": "user", "text": text, "source": source})
        low = " ".join(_words(text))
        if low in HIDE_WORDS:
            self.hide_window()
            return
        if low in SHOW_WORDS:
            self.show_window()
            return
        if low in MUTE_WORDS:
            self.set_muted(True)
            return
        if low in DICTATE_START:
            self._start_dictation()
            return
        if low in BRIEF_WORDS:
            self._briefing(morning=low in ("good morning", "morning", "morning briefing"), source=source, ended=ended)
            return
        if low in QUIT_WORDS:
            bye = self.persona["bye"]
            self.emit({"type": "msg", "role": "jarvis", "text": bye})
            self.speak(bye)
            self._stop.set()
            self.emit({"type": "quit"})
            self.on_quit()
            return
        if low in RESET_WORDS:
            if self.brain:
                self.brain.reset()
            self.emit({"type": "msg", "role": "jarvis", "text": "Memory wiped."})
            self.speak("Memory wiped.")
            return
        if is_stop(text):
            return
        if low in USAGE_ASK:
            self.say_line(usage.spoken())
            return
        m = BUDGET_RE.match(low)
        if m:
            usage.set_budget(float(m.group(1)), today_only=bool(m.group(2)))
            self.say_line(f"Done. The limit's {float(m.group(1)):.2f} dollars" + (" for today." if m.group(2) else " a day."))
            return
        if low in JOB_STATUS or low in JOB_CANCEL:
            js = getattr(self, "jobs", None)
            if js is None:
                self.say_line("Background jobs aren't available.")
            elif low in JOB_CANCEL:
                hit = js.cancel()
                self.say_line(f"Cancelled {'the background job' if len(hit) == 1 else str(len(hit)) + ' background jobs'}." if hit
                              else "Nothing's running in the background.")
            else:
                self.say_line(js.spoken_status())
            return
        if low in CONNECTOR_RELOAD or low in CONNECTOR_LIST:
            con = getattr(self, "connectors", None)
            if con is None:
                self.say_line("Connectors aren't available. Run setup dot bat to install the part they need.")
                return
            if low in CONNECTOR_RELOAD:
                self.emit({"type": "toast", "text": "Reconnecting connectors..."})
                line = con.reload()
            else:
                line = con.summary()
            self._emit_connectors()
            self.say_line(line)
            return
        if low in HISTORY_CLEAR:
            if self.history is None:
                self.say_line("There's no saved conversation history.")
            elif self.confirm("Delete all saved conversation history",
                              f"{self.history.count()} saved lines. Your saved notes and memories stay."):
                self.history.clear()
                self.say_line("Done. I don't remember any of our past conversations now.")
            else:
                self.say_line("Kept it.")
            return
        if low in UPDATE_WORDS or (UPDATE_RE.search(low) and not re.search(r"\b(windows|driver|drivers|steam|discord|game|app store|nvidia|graphics)\b", low)):
            self._update()                       # HIS updates; "Windows update" etc. still go to Claude
            return
        if low in ROLLBACK_WORDS:
            self._rollback()
            return
        if low in EMAIL_ANNOUNCE_ON or low in EMAIL_ANNOUNCE_OFF:
            on = low in EMAIL_ANNOUNCE_ON
            mb = getattr(self, "mailbox", None)
            if on and (mb is None or mb.problem()):
                self.say_line(mb.problem() if mb else "Email isn't set up yet. The readme has the steps.")
                return
            self._state_flag("email_announce", on)
            self.say_line("I'll tell you when new email arrives. Just who it's from and the subject." if on
                          else "Okay, I'll keep new email to myself until you ask.")
            return
        if low in SPOTIFY_STATUS:
            import spotify
            self.say_line(spotify.status())
            return
        if low in DISCORD_BOT_STATUS:
            b = getattr(self, "discord_bot", None)
            if b is None:
                self.say_line("The Discord bot isn't set up. It needs DISCORD_BOT_TOKEN in the dot env file, then a restart.")
            elif b.status == "online":
                self.say_line(f"Online as {b.name.split('#')[0]}, in {len(b.client.guilds)} server"
                              f"{'' if len(b.client.guilds) == 1 else 's'}. Sending is {'on' if b.send_enabled else 'off'}.")
            else:
                self.say_line(b._not_ready() + (f" {b.error}" if b.error and b.error not in b._not_ready() else ""))
            return
        if low in DISCORD_SEND_ON or low in DISCORD_SEND_OFF:
            self.set_discord_send(low in DISCORD_SEND_ON, speak=True)
            return
        if low in DISCORD_OFF or low in DISCORD_ON:
            on = low in DISCORD_ON
            self._state_flag("discord_read", on)
            self.say_line("I'll read your Discord messages out as they come in." if on else
                          "Fine. I'll keep your Discord messages to myself. Ask if you want them.")
            return
        if low in DISCORD_CHECK:
            self._discord_roundup()
            return
        if low in AUTOSTART_ON or low in AUTOSTART_OFF:
            self.set_autostart(low in AUTOSTART_ON, speak=True)
            return
        if low in DUO_ON_WORDS or (SWITCH_RE.search(text) and re.search(r"\b(both|two|together|everyone)\b", low)):
            self._set_duo(True)
            return
        if self.duo and low in DUO_OFF_WORDS:
            self._set_duo(False)
            return
        if SWITCH_RE.search(text) or (self.duo and re.match(r"^(just|only)\b", low)):
            target = next((k for k in personas.ORDER if any(a in low.split() for a in personas.PERSONAS[k]["aliases"])),
                          personas.other(self.persona_key))
            if self.duo:
                self._set_duo(False, speak=False)
                if target == self.persona_key:
                    line = self.persona["duo_off"]
                    self.emit({"type": "msg", "role": "jarvis", "text": line})
                    self.speak(line)
                    return
            self._switch(target)
            return
        if not self.brain:
            self.emit({"type": "msg", "role": "system",
                       "text": self.brain_error or "No working API key. Click API keys in the System panel."})
            if not config.ANTHROPIC_API_KEY:
                self.emit_key_status()
            return
        if config.INSTANT_COMMANDS and not duo_hit and self._instant(text):
            return
        if duo_hit or once or self.duo:
            self._duo_turn(text, source, ended, lead=once if once in personas.PERSONAS else None)
            return
        self._run_turn(text, source, ended)

    def _instant(self, text):
        """Everyday commands done locally, no AI call (see intents.py). True if handled."""
        t0 = time.time()
        hit = intents.match(text)
        if not hit:
            return False
        line, log = hit
        print(f"[instant] {text!r} -> {log} ({(time.time() - t0) * 1000:.0f} ms)")
        self._log_timing("done")
        if self.brain:      # so "turn it back up" etc. still makes sense to him afterwards
            self.brain.note(f'(The user said "{text}" and it was done instantly without you: {str(log)[:120]})')
        self.emit({"type": "instant", "text": text, "log": str(log)})     # the HUD shows a panel for it
        if line:
            self.say_line(line)
        else:
            self.emit({"type": "toast", "text": str(log)})
        self._engage(2.5)        # if you were still going ("...and play something"), the rest still lands
        return True

    # ================================================================ updating himself
    def _update_check(self):
        """At startup: a newer jarvis.zip in Downloads? Mention it once per version. Also: just updated?
        The installed app checks its releases page instead (and keeps checking every few hours)."""
        import updater
        done = self._state_flag("just_updated")
        if done:
            self._state_flag("just_updated", "")
            self.events.put(("say", f"Update complete. I'm on version {updater.current_version()} now."))
            if not config.FROZEN:
                return
        self._whats_new_after_update()
        if config.FROZEN:
            threading.Thread(target=self._app_update_loop, daemon=True, name="app-update").start()
            return
        try:
            found = updater.find_update()
        except Exception:
            found = None
        if found and self._state_flag("update_announced") != found[1]:
            self._state_flag("update_announced", found[1])
            self.events.put(("say", f"There's a newer version of me in your Downloads, {found[1]}. "
                                    "Say update yourself when you're ready."))

    def _whats_new_after_update(self):
        """Once per new version: pop up everything added since the version you had before."""
        import changelog
        latest = changelog.latest_version()
        if not latest:
            return
        seen = self._state_flag("changelog_seen")
        existing = seen is not None or self._state_flag("last_seen") is not None or self._state_flag("briefed") is not None
        self._state_flag("changelog_seen", latest)
        if not existing or seen == latest:
            return                                    # brand-new install, or nothing new
        picked = changelog.since(seen) if seen else changelog.sections()[:1]
        if picked:
            self.emit({"type": "whats_new", "version": latest if len(picked) == 1 else "",
                       "notes": changelog.as_markdown(picked)})

    def whats_new(self):
        import changelog
        picked = changelog.sections()[:3]
        self.emit({"type": "whats_new", "version": "",
                   "notes": changelog.as_markdown(picked) if picked else "No release notes in this version."})

    def _app_update_loop(self):
        import app_update
        time.sleep(20)                                   # don't compete with startup
        while not self._stop.is_set():
            try:
                print(f"[update] checking {app_update.source()} (on {app_update.current_version()})")
                v = app_update.check_and_download()
                print(f"[update] {'downloaded ' + v if v else 'up to date'}")
            except Exception as e:
                v = None
                print(f"[update] check failed: {app_update.explain(e)}")
            if v and self._state_flag("update_announced") != v:
                self._state_flag("update_announced", v)
                self.emit({"type": "update_ready", "version": v, "notes": app_update.pending_notes()[:600]})
                self.events.put(("say", f"Version {v} of me is downloaded. Say update yourself to switch now, "
                                        "or it installs the next time I start."))
            if self._stop.wait(6 * 3600):
                return

    def _app_update(self):
        import app_update
        if not app_update.available():
            if not app_update.source():
                why = "this build doesn't know where its updates come from (it was built without an update address)"
            else:
                why = "Windows says this copy wasn't installed by the setup program"
            detail = app_update._STATE.get("error") or ""
            print(f"[update] can't update: {why}. {detail}")
            self.emit({"type": "msg", "role": "system", "text": f"Can't update: {why}. {detail}".strip()})
            self.say_line(f"I can't update myself: {why}. Download the newest Setup dot exe from the releases page "
                          "and run it; that updates me in place and keeps everything.")
            return
        v = app_update.pending_version()
        if not v:
            self.say_line("Checking.")
            try:
                v = app_update.check_and_download()
            except Exception as e:
                why = app_update.explain(e)
                print(f"[update] check failed: {why}")
                self.say_line(f"I couldn't check for updates: {why}")
                return
        if not v:
            self.say_line(f"You're on the newest version, {app_update.current_version()}.")
            return
        notes = app_update.pending_notes()
        if not self.confirm(f"Update to version {v}", (f"Currently {app_update.current_version()}. "
                            "Your keys, memory, voice and settings stay as they are. He restarts after.")
                            + (f"\n\nWhat's new:\n{notes[:700]}" if notes else "")):
            self.say_line("Okay. It'll install the next time I start.")
            return
        self.say_line("Updating. Back in a moment.")
        self._state_flag("just_updated", v)
        try:
            app_update.apply_and_restart()
        except Exception as e:
            self._state_flag("just_updated", "")
            self.say_line(f"The update didn't start: {e}")
            return
        time.sleep(0.5)
        if getattr(self, "on_quit", None):
            self.on_quit()
        else:
            self.shutdown()

    def _update(self):
        import updater
        if config.FROZEN:
            return self._app_update()
        found = updater.find_update()
        if not found:
            self.say_line(f"You've got the newest version I can find, {updater.current_version()}. "
                          "When a new jarvis zip lands in your Downloads, ask me again.")
            return
        path, version = found
        if not self.confirm(f"Update Jarvis to version {version}",
                            f"From {path.name} in your Downloads (currently {updater.current_version()}).\n"
                            "Your .env, memory, reminders, voice and settings stay as they are. "
                            "He backs himself up first and restarts after."):
            self.say_line("Update cancelled.")
            return
        self.say_line("Updating. I'll be right back.")
        try:
            new, needs_pip = updater.apply(path, log=print)
        except Exception as e:
            self.say_line(f"The update failed and nothing was changed: {e}")
            return
        if needs_pip:
            self.say_line("Installing a couple of new parts first. This can take a minute.")
            if not updater.pip_install(log=print):
                self.emit({"type": "msg", "role": "system", "text": "Installing new packages failed; run setup.bat if anything's missing."})
        self._state_flag("just_updated", new)
        self._restart()

    def _rollback(self):
        import updater
        if config.FROZEN:
            self.say_line("The installed version can't undo an update by itself. If this one's broken, "
                          "download an older Setup dot exe from the releases page and run it.")
            return
        src = updater.latest_backup()
        if not src:
            self.say_line("There's no earlier version to go back to.")
            return
        if not self.confirm("Undo the last update", f"Restores the backup in {src}. He restarts after."):
            self.say_line("Okay, staying on this version.")
            return
        v = updater.rollback(log=print)
        self.say_line(f"Rolled back to {v}. Restarting.")
        self._state_flag("just_updated", v or "")
        self._restart()

    def _restart(self):
        import updater
        updater.RESTARTING = True
        updater.spawn_restart()            # the new copy waits until this one has let go, then starts
        time.sleep(0.5)
        if getattr(self, "on_quit", None):
            self.on_quit()
        else:
            self.shutdown()

    # ================================================================ morning briefing
    @staticmethod
    def _brief_day():
        """Today, for briefings. The day rolls over at 4 AM, so a 1 AM session still counts as last night."""
        return (datetime.now() - timedelta(hours=4)).strftime("%Y-%m-%d")

    def _briefing_due(self):
        """The first time you start or wake the PC each day, whatever the time."""
        return config.MORNING_BRIEFING and self._state_flag("briefed") != self._brief_day()

    def _wake_watch(self):
        """Notices the PC waking from sleep (the clock jumps). First wake of the day = briefing.
        Also remembers when you were last here, so the briefing knows what's new."""
        last, saved = time.time(), 0.0
        while not self._stop.wait(15):
            now = time.time()
            if now - last > 120 and self._briefing_due():          # we were asleep
                self._brief_from = last
                for _ in range(40):                                 # wait for a quiet moment (up to ~2 min)
                    if self._turn is None and not self._user_talking and self.state in ("idle", "listening"):
                        break
                    if self._stop.wait(3):
                        return
                self.events.put(("brief", None))
            last = now
            if now - saved > 300:
                saved = now
                self._state_flag("last_seen", now)

    def _briefing(self, morning=True, source="voice", ended=None, auto=False):
        """Facts gathered locally in parallel (a few seconds at most), then the fast model says it."""
        if auto:
            self._state_flag("briefed", self._brief_day())
        self.set_state("thinking")
        watcher = getattr(self, "discord", None)
        since = getattr(self, "_brief_from", 0) or (watcher.read_upto if watcher else 0) or time.time() - 12 * 3600
        since = max(since, time.time() - 24 * 3600)
        items = [{"message": r["message"], "due": r["due"]} for r in tools.REMINDERS.items]
        t0 = time.time()
        facts = briefing.gather(items, watcher, since, self._state_flag, self._state_flag)
        print(f"[briefing] gathered {sorted(k for k in facts if not k.startswith('_'))} in {time.time() - t0:.1f}s")
        self.emit({"type": "briefing", "weather": facts.get("_weather"), "reminders": facts.get("_reminders", []),
                   "discord": facts.get("_discord", []), "headlines": facts.get("_headlines", [])})
        facts = {k: v for k, v in facts.items() if not k.startswith("_")}
        if watcher:
            watcher.read_upto = time.time()
        self._brief_from = 0
        if self.brain is None:
            self.say_line(briefing.fallback(facts))
            return
        self._run_turn("Daily briefing" if morning else "Briefing", source, ended or time.time(), max_words=140,
                       prompt=briefing.prompt(facts, morning), allow_tools=False, quick=True)

    # ================================================================ Discord (via Windows notifications)
    def emit(self, ev):
        """Everything shown in the app goes through here; what's said is also kept in conversation memory."""
        self._emit_out(ev)
        h = self.history
        if h is None:
            return
        try:
            t = ev.get("type")
            if t == "turn_start":
                self._turn_who[ev["id"]] = ev.get("who") or self.persona["name"]
            elif t == "msg" and ev.get("role") == "user":
                h.add("You", ev.get("text", ""))
            elif t == "msg" and ev.get("role") == "jarvis":
                h.add(self.persona["name"], ev.get("text", ""))
            elif t == "turn_end":
                who = self._turn_who.pop(ev.get("id"), self.persona["name"])
                if not ev.get("interrupted") and ev.get("text"):
                    h.add(who, ev["text"])
        except Exception as e:
            print(f"[history] couldn't save: {e}")

    # ================================================================ background jobs
    def _start_jobs(self):
        import jobs
        self.jobs = None
        if self.brain is None:
            return
        self.jobs = jobs.Jobs(make_brain=lambda p: Brain(p), on_change=self._emit_jobs, on_done=self._job_done, log=print)
        tools.set_jobs(self.jobs)

    def _emit_jobs(self):
        js = getattr(self, "jobs", None)
        self.emit({"type": "jobs", "items": js.views() if js else []})

    def _job_done(self, job):
        self.emit({"type": "job_done", "id": job.id, "goal": job.goal, "summary": job.summary,
                   "path": str(job.path) if job.path else None, "ok": job.status == "done"})
        self.events.put(("job_done", job))

    def _announce_job(self, job):
        for _ in range(40):                     # wait for a quiet moment (up to ~20 s) instead of talking over you
            if self._turn is None and not self._user_talking and self._pending is None and self.state in ("idle", "listening"):
                break
            time.sleep(0.5)
        if job.status == "done":
            line = f"Background job done. {job.summary}"
            if job.path:
                self.emit({"type": "msg", "role": "system", "text": f"Saved the full write-up: {job.path}"})
        else:
            line = f"The background job didn't work out. {job.summary}"
        self._spoken.append((time.time(), line))
        self.emit({"type": "caption", "text": line})
        self.say_line(line)

    def _start_connectors(self):
        """App connectors (MCP) start in the background: a slow server never delays him."""
        self.connectors = None
        try:
            import connectors
            connectors.ensure_file()
            con = connectors.Connectors(log=print)
            con.on_change = self._emit_connectors
            self.connectors = con
            tools.set_connectors(con)
            if con.read_config():
                con.start()
                if any(s["status"] == "connected" for s in con.servers.values()):
                    self._log(f"APP CONNECTORS  [{', '.join(n for n, s in con.servers.items() if s['status'] == 'connected')}]")
            else:
                con.start()
        except ImportError:
            print("[connectors] the MCP library isn't installed (run setup.bat); connectors are off")
        except Exception as e:
            print(f"[connectors] couldn't start: {e}")
        self._emit_connectors()

    def _open_job(self, jid):
        js = getattr(self, "jobs", None)
        job = js.jobs.get(int(jid)) if js and jid is not None else None
        if not job or not job.path:
            return "That job has no saved result yet."
        tools.open_path(str(job.path), front=True)
        return f"Opened {job.path.name}"

    def _reload_connectors(self):
        con = getattr(self, "connectors", None)
        if con is None:
            return "Connectors aren't available (run setup.bat)."
        line = con.reload()
        self._emit_connectors()
        return line

    def _open_connectors_file(self):
        import connectors
        path = connectors.ensure_file()
        if tools.IS_WINDOWS:
            import subprocess
            subprocess.Popen(["notepad.exe", str(path)])
        return f"Opened {path}"

    def _emit_connectors(self):
        con = getattr(self, "connectors", None)
        self.emit({"type": "connectors", "available": con is not None, "items": con.status() if con else []})

    def _start_discord(self):
        self.discord = None
        try:
            w = notifications.DiscordWatcher(on_message=self._on_discord, log=print)
            if w.start():
                self.discord = w
                tools.set_discord(w)
                self._log("DISCORD MESSAGES  [WINDOWS NOTIFICATIONS]")
        except Exception as e:
            print(f"[discord] not available: {e}")

    def _has_key(self):
        k = config.ANTHROPIC_API_KEY or ""
        return bool(k) and "paste-yours" not in k

    def _first_voice_download(self):
        """The installer doesn't include the 350 MB voice: fetch it during first-time setup, BEFORE he starts
        listening or talking, so the first thing anyone hears is his real voice. Progress shows on screen.
        If it can't download (offline), he starts anyway with a stand-in voice and tries again next start."""
        if config.TTS_ENGINE != "kokoro" or not self.speaker or not self.speaker.enabled:
            return
        import download_models
        if download_models.have_voice():
            return
        self._log("FIRST-TIME SETUP  [DOWNLOADING VOICE, ABOUT 350 MB]")
        last = {"pct": -10, "file": None}

        def progress(name, done, total):
            pct = int(done * 100 / total) if total else 0
            if name != last["file"]:
                last.update(file=name, pct=-10)
            if pct >= last["pct"] + 10:
                last["pct"] = pct
                part = "voice model" if name.endswith(".onnx") else "voices"
                self._log(f"DOWNLOADING {part.upper()}  {pct}%")
                self.emit({"type": "download", "what": "voice", "pct": pct})
        if download_models.ensure_voice(progress=progress, log=print) and self.speaker.add_kokoro():
            self.emit({"type": "download", "what": "voice", "pct": 100})
            self._log("VOICE DOWNLOADED")
        else:
            self._log("VOICE DOWNLOAD FAILED  [STAND-IN VOICE FOR NOW, RETRIES NEXT START]")

    # ================================================================ API keys (first run, or changing them)
    def emit_key_status(self, reason=""):
        import experts
        self.emit({"type": "setup", "reason": reason,
                   "has_anthropic": bool(config.ANTHROPIC_API_KEY) and "paste-yours" not in config.ANTHROPIC_API_KEY,
                   "has_groq": bool(config.GROQ_API_KEY),
                   "has_blender": experts.unlocked("blender"), "has_unreal": experts.unlocked("unreal")})

    def save_keys(self, anthropic="", groq="", blender="", unreal=""):
        """The first-run card: the Claude key, plus optional Groq, Blender and Unreal keys (blank = skip)."""
        changes = {"ANTHROPIC_API_KEY": anthropic, "GROQ_API_KEY": groq, "BLENDER_AI_KEY": blender,
                   "UNREAL_AI_KEY": unreal}
        if not any(str(v or "").strip() for v in changes.values()):
            if self._has_key():                      # nothing new, but he's already set up: just close the card
                return self.emit({"type": "keys_result", "ok": True, "restart": False})
            return self.emit({"type": "keys_result", "ok": False, "error": "Paste your Claude key first."})
        if not self._has_key() and not (anthropic or "").strip():
            return self.emit({"type": "keys_result", "ok": False,
                              "error": "The Claude key is the one he can't run without; the others are optional."})
        ok, errors = settings.save(changes)
        if not ok:
            k, err = next(iter(errors.items()))
            label = {"ANTHROPIC_API_KEY": "Claude key", "GROQ_API_KEY": "Groq key", "BLENDER_AI_KEY": "Blender key",
                     "UNREAL_AI_KEY": "Unreal key"}.get(k, k)
            return self.emit({"type": "keys_result", "ok": False, "error": f"{label}: {err}", "field": k})
        needs_restart = any(str(changes[k] or "").strip() for k in ("ANTHROPIC_API_KEY", "GROQ_API_KEY"))
        self.emit({"type": "keys_result", "ok": True, "restart": needs_restart})
        self.emit_studio()
        if needs_restart:
            print("[setup] keys saved; restarting")
            time.sleep(1.5)
            self._restart()

    # ================================================================ Studio: the Blender and Unreal modes
    def emit_studio(self, probe=False):
        import experts
        self.emit({"type": "studio", "modes": experts.view(probe=probe)})

    def studio_save(self, mode, key="", model=None):
        """Unlock (or change) a mode from the Studio panel. Live: no restart. The key never goes back to the screen."""
        import experts
        if mode not in experts.MODES:
            return
        m = experts.MODES[mode]
        changes = {}
        if str(key or "").strip():
            changes[m["key"]] = key
        clear = []
        if model is not None:
            if str(model).strip():
                changes[m["model"]] = model
            else:
                clear.append(m["model"])
        if not changes and not clear:
            return self.emit({"type": "studio_result", "mode": mode, "ok": False, "error": "Paste a key first."})
        if not experts.unlocked(mode) and m["key"] not in changes:
            return self.emit({"type": "studio_result", "mode": mode, "ok": False, "error": "Paste a key first."})
        ok, errors = settings.save(changes, clear)
        if not ok:
            return self.emit({"type": "studio_result", "mode": mode, "ok": False, "error": next(iter(errors.values()))})
        print(f"[studio] {m['name']} mode {'unlocked' if m['key'] in changes else 'updated'}")
        self.emit({"type": "studio_result", "mode": mode, "ok": True})
        self.emit_studio(probe=True)

    def studio_remove(self, mode):
        import experts
        if mode not in experts.MODES:
            return
        m = experts.MODES[mode]
        settings.save({}, [m["key"], m["model"]])
        print(f"[studio] {m['name']} mode locked (key removed)")
        self.emit({"type": "studio_result", "mode": mode, "ok": True, "removed": True})
        self.emit_studio()

    def studio_install_addon(self):
        out = tools.blender("install_addon")
        self.emit({"type": "toast", "text": out[:220]})
        self.emit_studio(probe=True)

    # ================================================================ his voice, changed live
    def _voice_view(self):
        kok = next((e for e in self.speaker.engines if e.name == "kokoro"), None) if self.speaker else None
        avail = voice_settings.english_voices(getattr(kok, "available", None)) or sorted(
            {"bm_george", "bm_lewis", "bm_daniel", "bm_fable", "am_michael", "am_adam", "am_onyx", "am_puck",
             "bf_emma", "af_heart", "af_bella", "af_nicole"})
        return {"personas": [{"key": k, "name": personas.PERSONAS[k]["name"], **voice_settings.current(k)}
                             for k in personas.ORDER],
                "voices": [{"id": v, "label": voice_settings.describe(v)} for v in avail],
                "engine": self.speaker.engine_name if self.speaker else "none",
                "speed": list(voice_settings.SPEED), "pitch": list(voice_settings.PITCH)}

    def set_voice(self, key, voice=None, speed=None, pitch=None, preview=True):
        """Settings panel / the voice tool. Takes effect immediately, no restart."""
        kok = next((e for e in self.speaker.engines if e.name == "kokoro"), None)
        ok, msg = voice_settings.set_voice(key, voice, speed, pitch, getattr(kok, "available", None))
        if ok:
            self._wake_audio.pop(key, None)
            if key == self.persona_key:
                self.speaker.set_persona(self.persona)
            if preview:
                self.preview_voice(key)
        self.emit({"type": "voices", **self._voice_view(), "msg": msg})
        return msg

    def reset_voice(self, key):
        msg = voice_settings.reset(key)
        self._wake_audio.pop(key, None)
        if key == self.persona_key:
            self.speaker.set_persona(self.persona)
        self.emit({"type": "voices", **self._voice_view(), "msg": msg})
        self.preview_voice(key)
        return msg

    def preview_voice(self, key):
        """Say a line in that persona's (new) voice, without switching who you're talking to."""
        if self._turn is not None or not self.speaker:
            return
        p = personas.PERSONAS[key]
        line = p.get("voice_preview") or ("How's this, then?" if key == "jarvis" else "Is this voice adequate, human?")
        before = dict(self.speaker.persona), self.speaker.who
        self.speaker.set_persona(p)
        try:
            self.speaker.say(line)
        finally:
            self.speaker.persona, self.speaker.who = before

    def emit_settings(self):
        self.emit({"type": "settings", "fields": settings.view(), "voices": self._voice_view()})

    def save_settings(self, changes=None, clear=None):
        """From the Settings panel. Secrets arrive here once and are never sent back to the screen."""
        ok, errors = settings.save(changes or {}, clear or [])
        if not ok:
            self.emit({"type": "settings_result", "ok": False, "errors": errors})
            return
        import experts
        changed = [k for k, v in (changes or {}).items() if str(v or "").strip()] + list(clear or [])
        restart = [k for k in changed if k not in experts.LIVE_KEYS]      # Blender/Unreal keys apply live
        self.emit({"type": "settings_result", "ok": True, "restart": bool(restart)})
        if any(k in experts.LIVE_KEYS for k in changed):
            self.emit_studio()
        if restart:
            print(f"[settings] saved {', '.join(sorted(changed))}; restarting")
            time.sleep(1.5)
            self._restart()

    # ================================================================ Netflix log
    def _start_netflix(self):
        if not config.NETFLIX_TRACK or not tools.IS_WINDOWS:
            return
        import netflix

        def finished(s):
            if self.history is not None:
                what = "; ".join(s["titles"]) or "something (title unknown)"
                self.history.add("Netflix", f"Watched {what} for {s['minutes']} minutes on the {s['via']}")
        self.netflix = netflix.WatchTracker(on_finished=finished, log=print)
        self.netflix.start()

    # ================================================================ email
    def _start_email(self):
        import email_reader
        self.mailbox = email_reader.Mailbox(log=print)
        tools.set_mailbox(self.mailbox)
        if self.mailbox.problem() and self.mailbox.configured:
            self._log(f"EMAIL  [{self.mailbox.problem()[:60]}]")
        if not self.mailbox.problem():
            briefing.EMAIL_LINE = self.mailbox.briefing_line
            self._log(f"EMAIL  [{self.mailbox.address}, READ-ONLY]")
            threading.Thread(target=self._email_watch, daemon=True, name="email-watch").start()

    def _email_announcing(self):
        flag = self._state_flag("email_announce")
        return config.EMAIL_ANNOUNCE if flag is None else bool(flag)

    def _email_watch(self):
        """Every few minutes: anything new? Said out loud only if you've turned announcements on. Costs nothing
        (no Claude): just who it's from and the subject."""
        while not self._stop.wait(180):
            if not self._email_announcing() or self._dictation:
                continue
            try:
                fresh = self.mailbox.new_since_last()
            except Exception as e:
                print(f"[email] check failed: {type(e).__name__}: {e}")
                continue
            if not fresh:
                continue
            for _ in range(40):                       # wait for a quiet moment (up to ~20 s)
                if self._turn is None and not self._user_talking and self._pending is None:
                    break
                time.sleep(0.5)
            if len(fresh) == 1:
                line = f"New email from {fresh[0]['from']}: {fresh[0]['subject'][:90]}."
            else:
                line = f"{len(fresh)} new emails, from " + ", ".join(dict.fromkeys(f["from"] for f in fresh)) + "."
            self.emit({"type": "toast", "text": line})
            self.events.put(("say", line))

    # ================================================================ Discord bot
    def _start_discord_bot(self):
        import discord_bot
        self.discord_bot = None
        if self.brain is None or not config.DISCORD_BOT_TOKEN:
            self._emit_discord_bot()
            return
        b = discord_bot.DiscordBot(make_brain=lambda p: Brain(p), persona_key=lambda: self.persona_key,
                                   on_change=self._emit_discord_bot, on_chat=self._on_discord_chat, log=print)
        self.discord_bot = b                 # even if it can't connect: its status says why
        tools.set_discord_bot(b)
        b.start()
        self._log("DISCORD BOT  [CONNECTING]")
        self._emit_discord_bot()

    def _emit_discord_bot(self):
        b = getattr(self, "discord_bot", None)
        if b is None:
            import discord_bot
            self.emit({"type": "discord_bot", "configured": bool(config.DISCORD_BOT_TOKEN), "status": "off",
                       "send": bool(discord_bot._load().get("send", False))})
            return
        self.emit({"type": "discord_bot", **b.view()})

    def _on_discord_chat(self, info):
        self.emit({"type": "msg", "role": "system",
                   "text": f"Discord ({info['where']}) {info['who']}: {info['text'][:160]}\n→ {info['reply'][:240]}"})
        if self.history is not None:
            self.history.add(f"Discord bot, {info['who']} in {info['where']}", info["text"])
            self.history.add(f"{self.persona['name']} on Discord", info["reply"])

    def set_discord_send(self, on, speak=False):
        """The System panel switch, or "turn on Discord sending"."""
        import discord_bot
        b = getattr(self, "discord_bot", None)
        if b is not None:
            b.set_send(on)
        else:
            d = discord_bot._load()
            d["send"] = bool(on)
            discord_bot._save(d)
        self._emit_discord_bot()
        if on and not config.DISCORD_BOT_TOKEN:
            line = "Sending is on, but the Discord bot isn't set up yet. The README has the five-minute setup."
        elif on:
            line = "Discord sending on. I'll still show you each message before it goes."
        else:
            line = "Discord sending off. I won't post anything."
        if speak:
            self.say_line(line)
        else:
            self.emit({"type": "toast", "text": line})

    def _discord_reading(self):
        flag = self._state_flag("discord_read")
        return config.DISCORD_READ if flag is None else bool(flag)

    def _on_discord(self, m):
        self.emit({"type": "discord", "from": m["sender"], "channel": m["channel"], "text": m["text"]})
        if self.history is not None:
            self.history.add(f"Discord, {m['sender']}" + (f" in #{m['channel']}" if m["channel"] else ""), m["text"], ts=m["time"])
        if not self._discord_reading() or self._dictation:
            return
        with self._plock:
            q = self._discord_q = getattr(self, "_discord_q", []) + [m]
            first = len(q) == 1
        if first:                     # collect a burst for a moment, then say it once
            threading.Timer(1.5, lambda: self.events.put(("discord", None))).start()

    def _announce_discord(self, _):
        # wait (briefly, without blocking the engine for long) until he isn't talking to you or hearing you
        for _ in range(20):
            if not self._user_talking and self._pending is None and self.state in ("idle", "listening"):
                break
            time.sleep(0.5)
        with self._plock:
            q, self._discord_q = getattr(self, "_discord_q", []), []
        if not q or self._dictation or not self._discord_reading():
            return
        if len(q) == 1:
            m = q[0]
            who = m["sender"] + (f" in {m['channel']}" if m["channel"] else "")
            line = self.persona.get("discord_line", "Message from {who}: {text}").format(
                who=who, text=notifications.speakable(m["text"]))
        else:
            line = notifications.summary(q)
        if self.discord:
            self.discord.read_upto = time.time()
        self._spoken.append((time.time(), line))
        self.emit({"type": "caption", "text": line})
        self.emit({"type": "msg", "role": "system", "text": "Discord: " + line})
        self.speak(line)

    def _discord_roundup(self):
        if not self.discord:
            self.say_line("I can't see your Discord messages on this PC. Discord's Windows notifications need to be "
                          "turned on, in Discord's settings under Notifications.")
            return
        msgs = self.discord.unread()
        if not msgs:
            msgs = self.discord.search(hours=12, limit=5)
            line = ("Nothing new on Discord. " + ("The last thing was from " + msgs[-1]["sender"] + ": "
                    + notifications.speakable(msgs[-1]["text"], 16) if msgs else "Quiet day.")).strip()
        else:
            line = notifications.summary(msgs)
        self.say_line(line)

    # ================================================================ whose computer is this
    def _emit_autostart(self):
        import autostart
        try:
            on = autostart.is_on()
        except Exception:
            on = False
        self.emit({"type": "autostart", "available": autostart.available(), "on": on})

    def set_autostart(self, on, speak=False):
        """Start with Windows on/off (the System panel switch, or "Jarvis, start with Windows")."""
        import autostart
        try:
            line = autostart.set_on(on)
        except Exception as e:
            line = f"I couldn't change the startup setting: {e}"
        self._emit_autostart()
        if speak:
            self.say_line(line)
        else:
            self.emit({"type": "toast", "text": line})

    def _state_flag(self, key, value=None):
        """Small per-PC flags kept in Documents/Jarvis/flags.json."""
        path = config.JARVIS_DIR / "flags.json"
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        if value is None:
            return d.get(key)
        d[key] = value
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(d), encoding="utf-8")
        except OSError:
            pass
        return value

    def say_line(self, line):
        self.emit({"type": "msg", "role": "jarvis", "text": line})
        self.speak(line)

    # ================================================================ both at once
    def _duo_turn(self, text, source, ended, lead=None):
        """They take turns. The lead answers and does any actions; the other one
        reads that and adds their own short take. The second one starts thinking
        while the first is still talking, so there's no dead air at the hand-off."""
        lead = lead or self.persona_key
        second = personas.other(lead)
        lp, sp = personas.PERSONAS[lead], personas.PERSONAS[second]
        lb, sb = self._brain_for(lead), self._brain_for(second)
        if not lb or not sb:
            return
        self._become(lead)

        cap = self._duo_capture = []
        lead_prompt = (f"{text}\n\n[The user said this to both you and {sp['name']}. You answer first and handle "
                       f"anything that needs doing. {sp['name']} will add his own take right after you, so keep "
                       f"yours short and leave him room.]")
        try:
            r1 = self._run_turn(text, source, ended, brain=lb, prompt=lead_prompt, wait=False)
        finally:
            self._duo_capture = None
        if r1["interrupted"] or not r1["reply"]:
            return
        lead_reply = r1["reply"]

        did = f" and did this: {'; '.join(cap[:6])}" if cap else ""
        second_prompt = (f'[The user said to both of you: "{text}". {lp["name"]} answered first: "{lead_reply}"{did}.]\n'
                         f"Your turn, {sp['name']}. Add your own short take in your own voice: react to "
                         f"{lp['name']}, add what he missed, or disagree. Don't repeat him and don't redo anything "
                         f"he already did; you can't use tools this turn. One or two sentences.")

        lead_stream = r1["stream"]
        self.speaker.set_persona(sp)             # the second stream picks up his voice; the lead's keeps theirs
        handed = threading.Event()
        cancelled = threading.Event()

        def hand_off():
            # flip the HUD to whoever's talking at the moment the lead stops
            lead_stream.wait(timeout=240)
            if cancelled.is_set() or lead_stream.cancelled.is_set():
                return                            # cut off: the floor stays where it was
            self._become(second, voice=False)
            handed.set()
            if self._turn and not self._turn.get("spoke"):
                self.set_state("thinking")
        threading.Thread(target=hand_off, daemon=True, name="duo-handoff").start()

        r2 = self._run_turn(text, "duo", ended, brain=sb, prompt=second_prompt, allow_tools=False,
                            after=lead_stream, who=sp["name"], max_words=config.DUO_SECOND_WORDS,
                            quick=not DETAIL_HINTS.search(text))      # a quick reaction: the fast model is plenty
        if r2["interrupted"]:
            cancelled.set()
            self.speaker.set_persona(self.persona)
            return
        handed.wait(2)
        self._become(second)                      # the last one to speak holds the floor; next time he leads
        self._save_state()
        if r2["reply"]:
            lb.note(f'{sp["name"]} added after your answer: "{r2["reply"]}"')
        if source == "voice" and (lead_reply.rstrip().endswith("?") or (r2["reply"] or "").rstrip().endswith("?")):
            self._engage()

    # ================================================================ mic mute
    def set_muted(self, muted, minutes=None, speak=True):
        """Really closes the mic. He can't hear "unmute", so unmuting is the button,
        the hotkey, typing "unmute", or a timer."""
        if not self.listener:
            self.emit({"type": "toast", "text": "Microphone is offline anyway."})
            return "Microphone is offline."
        if self._mute_timer:
            self._mute_timer.cancel()
            self._mute_timer = None
        until = None
        if muted and minutes:
            until = time.time() + float(minutes) * 60
            self._mute_timer = threading.Timer(float(minutes) * 60, lambda: self.set_muted(False))
            self._mute_timer.daemon = True
            self._mute_timer.start()
        if muted and speak:
            # say it BEFORE closing the mic... and after, the mic can't catch the echo anyway
            line = self.persona["muted"]
            if minutes:
                line = f"Mic off for {round(float(minutes))} minute{'s' if round(float(minutes)) != 1 else ''}."
            self.speak(line)
        self.muted = muted
        with self._hold_lock:
            if self._hold and self._hold.get("timer"):
                self._hold["timer"].cancel()
            self._hold = None
        self._engaged_until, self._talk_engaged = 0, False
        self.listener.set_muted(muted)
        self.emit({"type": "mic", "muted": muted, "until": until, "hotkey": config.MUTE_HOTKEY})
        print(f"[voice] mic {'MUTED' if muted else 'live'}")
        if not muted and speak:
            self.events.put(("say_quiet", "I'm listening."))
        return "Mic muted." if muted else "Mic live."

    def toggle_mute(self):
        self.set_muted(not self.muted)

    @staticmethod
    def _parse_hotkey(text):
        mods = {"ctrl": 0x2, "control": 0x2, "alt": 0x1, "shift": 0x4, "win": 0x8}
        parts = [p.strip().lower() for p in (text or "").split("+") if p.strip()]
        mod = 0
        for p in parts[:-1]:
            mod |= mods.get(p, 0)
        key = parts[-1] if parts else ""
        vk = ord(key.upper()) if len(key) == 1 else {"f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
                                                       "pause": 0x13, "scrolllock": 0x91}.get(key, 0)
        return mod, vk

    def _hotkey_answer(self, yes):
        with self._plock:
            p = self._pending
        if p:
            self.resolve_confirm(p["id"], yes)

    def _start_hotkey(self):
        """Global hotkeys via RegisterHotKey: work while you're in a game or another app.
        Mute toggle, plus approve / deny for whatever he's asking permission for."""
        if not tools.IS_WINDOWS:
            return
        keys = [(1, config.MUTE_HOTKEY, "MUTE", lambda: self.toggle_mute()),
                (2, config.APPROVE_HOTKEY, "APPROVE", lambda: self._hotkey_answer(True)),
                (3, config.DENY_HOTKEY, "DENY", lambda: self._hotkey_answer(False))]

        def loop():
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            actions = {}
            for hid, text, name, fn in keys:
                if not text:
                    continue
                mod, vk = self._parse_hotkey(text)
                if not vk:
                    self._log(f"{name} HOTKEY '{text}' NOT UNDERSTOOD")
                    continue
                if not user32.RegisterHotKey(None, hid, mod | 0x4000, vk):   # 0x4000 = no auto-repeat
                    self._log(f"{name} HOTKEY {text.upper()} IS TAKEN BY ANOTHER APP")
                    continue
                actions[hid] = fn
                self._log(f"{name} HOTKEY  [{text.upper()}]")
            if not actions:
                return
            msg = wintypes.MSG()
            while not self._stop.is_set() and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == 0x0312 and msg.wParam in actions:          # WM_HOTKEY
                    threading.Thread(target=actions[msg.wParam], daemon=True).start()
            for hid in actions:
                user32.UnregisterHotKey(None, hid)

        threading.Thread(target=loop, daemon=True, name="hotkeys").start()

    # ================================================================ dictation
    def _start_dictation(self, window=None):
        target = None
        if tools.IS_WINDOWS:
            try:
                if window:
                    w = tools._find_window(window)
                else:   # windows come back in front-to-back order: the first that isn't us is where you were
                    w = next(iter(tools._windows()), None)
                target = w.title if w else None
            except Exception as e:
                print(f"[dictation] couldn't pick a window: {e}")
        if tools.IS_WINDOWS and not target:
            self.speak("Click into the app you want me to type into, then ask again.")
            return
        self._dictation = {"window": target, "last": "", "newline": True, "prev_newline": True}
        short = (target or "the active window").split(" - ")[0][:40]
        self.emit({"type": "dictation", "on": True, "window": target})
        self.emit({"type": "msg", "role": "system", "text": f"Dictating into {target or 'the active window'}. Say \"{self.persona['name']}, stop dictating\" to finish."})
        # Don't say the stop phrase out loud: the echo filter would then ignore YOU saying it.
        self.speak(f"Dictating into {short}. Go ahead.")
        self.set_state("dictating")

    def _stop_dictation(self):
        if not self._dictation:
            return
        self._dictation = None
        self.emit({"type": "dictation", "on": False})
        self.speak("Done dictating.")

    def _dictate(self, text):
        d = self._dictation
        low = " ".join(_words(text))
        win = d["window"]
        if low in ("new line", "next line"):
            tools.keyboard_input("press", keys=["enter"], window=win)
            d["newline"] = True
        elif low in ("new paragraph", "next paragraph"):
            tools.keyboard_input("press", keys=["enter"], times=2, window=win)
            d["newline"] = True
        elif low in ("scratch that", "delete that", "undo that") and d["last"]:
            tools.keyboard_input("press", keys=["backspace"], times=min(len(d["last"]), 50), window=win)
            d["last"], d["newline"] = "", d["prev_newline"]
        else:
            chunk = text.strip()
            if not d["newline"]:
                chunk = " " + chunk
            r = tools.keyboard_input("type", text=chunk, window=win)
            if "couldn't find" in r.lower():
                self.emit({"type": "toast", "text": r})
            d["prev_newline"] = d["newline"]
            d["last"], d["newline"] = chunk, False
        self.emit({"type": "heard", "text": text, "addressed": True})

    def hide_window(self, speak=True):
        hidden = self.on_minimize()
        line = (self.persona["hidden"] if hidden else "There's no window to hide in console mode.")
        self.emit({"type": "msg", "role": "jarvis", "text": line})
        if speak:
            self.speak(line)
        return line

    def show_window(self, speak=True):
        shown = self.on_restore()
        line = self.persona["shown"] if shown else "No window in console mode."
        self.emit({"type": "msg", "role": "jarvis", "text": line})
        if speak:
            self.speak(line)
        return line

    def _quick_ack(self, text, source):
        """For requests that will take a moment: say a pre-recorded "On it." right away (no dead air)."""
        if not config.INSTANT_ACK or source not in ("voice", "typed", "phone") or not SLOW_HINTS.search(text):
            return None
        acks = self.persona.get("acks") or []
        if not acks:
            return None
        line = random.choice(acks)
        self._spoken.append((time.time(), line))
        self.emit({"type": "caption", "text": line})
        audio = self.speaker.synth(line)          # pre-recorded at startup, so this is instant
        if audio is not None:
            threading.Thread(target=self.speaker.play, args=(audio,), daemon=True, name="ack").start()
        return line

    def _warm_phrases(self):
        """In the background after startup: pre-record the lines he says most, for both of them,
        so they play instantly. Takes a minute the first time, then loads from disk."""
        common = ["Done.", "Opening Spotify.", "Opening Discord.", "Opening Steam.", "Opening Chrome.",
                  "Opening Downloads.", "Screenshot saved.", "Dark mode.", "Light mode.", "Already here."]
        common += [f"Volume {v}." for v in range(10, 101, 10)]
        common += [f"Timer set for {n} minutes." for n in (1, 2, 3, 5, 10, 15, 20, 30)]
        items = []
        for key in personas.ORDER:
            p = personas.PERSONAS[key]
            lines = [p["confirm_cue"]] + list(p.get("acks", [])) + [p["hidden"], p["shown"], p["muted"]] + common
            items += [(line, p) for line in lines]
        try:
            self.speaker.warm_phrases(items, stop=self._stop,
                                      busy=lambda: (self._user_talking or self._turn is not None or self._hold is not None
                                                    or self.state not in ("idle", "listening")))
        except Exception as e:
            print(f"[tts] pre-recording phrases failed: {e}")

    def _log_timing(self, what):
        """One line per request in the console: where the time went between you stopping and him starting."""
        t = getattr(self, "_timing", None)
        if not t or time.time() - t.get("speech_end", 0) > 30:
            return
        self._timing = None
        total = time.time() - t["speech_end"]
        parts = [("noticing you'd stopped (" + t.get("how", "") + ")", t.get("endpoint", 0)),
                 ("cloud transcription", t.get("cloud", 0)),
                 ("waiting for the transcriber", t.get("queue", 0)),
                 ("quick transcription", t.get("fast", 0)), ("finishing live transcription", t.get("live_wait", 0)),
                 ("careful transcription", t.get("careful", 0))]
        known = sum(v for _, v in parts)
        parts.append(("waiting a beat for more (hold)", max(0.0, total - known)))
        detail = ", ".join(f"{name} {v:.1f}s" for name, v in parts if v >= 0.05)
        print(f"[timing] you stopped talking -> {what}: {total:.1f}s  ({detail})")
        if total > 3:
            biggest = max(parts, key=lambda p: p[1])
            print(f"[timing] slowest part: {biggest[0]}")

    def _quick(self, text):
        """Short, everyday request? Then the fast model answers it."""
        return (bool(config.FAST_MODEL) and len(text.split()) <= 14 and not HEAVY_HINTS.search(text)
                and not DETAIL_HINTS.search(text))

    def _run_turn(self, text, source, ended, max_words="auto", brain=None, prompt=None, allow_tools=True,
                  after=None, wait=True, who=None, quick="auto"):
        """Stream the answer: text goes to the voice and the app as it's written,
        every step is reported live, and the user can cut in at any time.
        For duo turns: brain/prompt pick who answers and what they're told, after=
        holds this voice until the other one finishes, wait=False returns while
        still talking. Returns {"reply", "interrupted", "stream"}."""
        brain = brain or self.brain
        tid = uuid.uuid4().hex[:8]
        t0 = time.time()
        detail = bool(DETAIL_HINTS.search(text))
        if max_words == "auto":
            max_words = None if detail else config.MAX_SPOKEN_WORDS
        elif detail and source == "duo":
            max_words = None
        acked = self._quick_ack(text, source)
        if acked:
            prompt = (prompt or text) + f"\n[You already said \"{acked}\" out loud. Don't open with another acknowledgement.]"
        gaming = config.GAME_MODE and not detail and tools.fullscreen_app()
        if gaming:                                   # in a game / fullscreen video: get in, get out
            max_words = min(max_words or 999, 25)
            prompt = (prompt or text) + f"\n[The user is in a fullscreen game or video ({gaming}). One short sentence.]"
        stream = self.speaker.stream(max_words=max_words, after=after)
        turn = {"id": tid, "stream": stream, "text": "", "cancel": threading.Event(), "spoke": False,
                "interrupted": False, "source": source, "text_in": text, "utt_end": ended or t0}
        self._turn = turn
        if source != "duo":
            self._log_timing("thinking")
        self.set_state("thinking")
        self.emit({"type": "turn_start", "id": tid, "who": who or self.persona["name"]})

        turn.update(tools_used=False, pre="", post_buf="")

        def speak(delta):
            """Before any action: straight to the voice. After one: sentence by sentence, dropping the
            "Done, I've opened Spotify" recap when he already said "Opening Spotify" as he did it."""
            if not turn["tools_used"]:
                stream.feed(delta)
                return
            turn["post_buf"] += delta
            while True:
                m = re.search(r"[.!?…][\"')\]]*\s+", turn["post_buf"])
                if not m:
                    return
                sent, turn["post_buf"] = turn["post_buf"][:m.end()], turn["post_buf"][m.end():]
                if not is_recap(sent, turn["pre"]):
                    stream.feed(sent)
                else:
                    print(f"[voice] not repeating: {sent.strip()!r}")

        def on_text(delta):
            if turn["cancel"].is_set():
                return
            turn["text"] += delta
            if delta.strip():
                self.emit({"type": "reply_delta", "id": tid, "text": delta})
            speak(delta)

        def on_event(kind, data):
            if kind == "tool_start" and not turn["tools_used"]:
                turn["tools_used"], turn["pre"] = True, turn["text"]
                if turn["pre"].strip() and not turn["cancel"].is_set():
                    stream.flush()
                    stream.drain(timeout=2.5)       # "Opening Spotify." is heard as it happens, not after
            if not turn["cancel"].is_set():
                self.emit({"type": "activity", "id": tid, "kind": kind, "data": data,
                           "t": round(time.time() - t0, 1)})

        reply = None
        try:
            if quick == "auto":
                quick = self._quick(text)
            if quick:
                print(f"[brain] quick model for {text[:50]!r}")
            tools._CTX.persona = getattr(brain, "persona_key", self.persona_key)
            reply = brain.ask(prompt or text, on_text=on_text, on_event=on_event, cancel=turn["cancel"],
                              allow_tools=allow_tools, quick=quick)
            if reply is not None and not turn["interrupted"]:
                if not turn["text"].strip():
                    self.emit({"type": "reply_delta", "id": tid, "text": reply})
                    stream.feed(reply)
                rest, turn["post_buf"] = turn["post_buf"], ""
                if rest.strip() and not is_recap(rest, turn["pre"]):
                    stream.feed(rest)
                stream.finish()
                self.emit({"type": "turn_end", "id": tid, "text": turn["text"].strip() or reply,
                           "secs": round(time.time() - t0, 1), "interrupted": False})
                if wait:
                    stream.wait(timeout=240)          # safety net: a stuck voice can't freeze him forever
                    if not stream.done.is_set():
                        print("[voice] speech got stuck; cancelling it so he keeps working")
                        stream.cancel()
            if turn["interrupted"] or reply is None:
                stream.cancel()
                self.emit({"type": "turn_end", "id": tid, "text": turn["text"].strip(),
                           "secs": round(time.time() - t0, 1), "interrupted": True})
        finally:
            self._turn = None
        final = (turn["text"].strip() or reply or "")
        if not turn["interrupted"] and source == "voice" and wait and final.rstrip().endswith("?"):
            self._engage()
        return {"reply": final if reply is not None else None, "interrupted": turn["interrupted"] or reply is None,
                "stream": stream}

    # ================================================================ quick controls
    def quick_action(self, name, value=None):
        tools._com_init()
        actions = {
            "play_pause": lambda: tools.media_control("play_pause"),
            "connectors_file": self._open_connectors_file,
            "connectors_reload": self._reload_connectors,
            "open_job": lambda: self._open_job(value),
            "cancel_job": lambda: (self.jobs.cancel(int(value)) and "Cancelling the job.") if getattr(self, "jobs", None) else "",
            "next": lambda: tools.media_control("next"),
            "previous": lambda: tools.media_control("previous"),
            "mute": lambda: tools.set_volume(mute=not (tools.volume_state() or (0, False))[1]),
            "volume": lambda: tools.set_volume(level=float(value)),
            "brightness": lambda: tools.brightness(level=int(value)),
            "lock": lambda: tools.system_power("lock"),
            "screenshot": tools.screenshot,
            "desktop": lambda: tools.window_control("show_desktop"),
            "dark_mode": lambda: tools.dark_mode(),
            "status": tools.system_status,
            "reset": lambda: (self.brain.reset() if self.brain else None) or "Memory wiped.",
        }
        fn = actions.get(name)
        if not fn:
            return
        try:
            res = fn()
        except Exception as e:
            res = f"{name} failed: {e}"
        if name not in ("volume", "brightness"):
            self.emit({"type": "toast", "text": str(res)})

    # ================================================================ telemetry
    def _check_alerts(self, bat, mem, disk):
        """Speak up about things you'd want to know without asking."""
        if bat is not None:
            if bat.power_plugged:
                self._alerted -= {"bat15", "bat5"}
            else:
                for lvl in (15, 5):
                    if bat.percent <= lvl and f"bat{lvl}" not in self._alerted:
                        self._alerted.add(f"bat{lvl}")
                        msg = (f"Battery's at {round(bat.percent)} percent. Plug in soon." if lvl == 15
                               else f"Battery's at {round(bat.percent)} percent. Plug in now or lose your work.")
                        self._alert(msg, urgent=lvl == 5)
                        break
        self._ram_hot = self._ram_hot + 1 if mem.percent >= 93 else 0
        if self._ram_hot == 3 and time.time() - self._last_ram_alert > 900:
            self._last_ram_alert = time.time()
            self._alert(f"Memory's at {round(mem.percent)} percent. Things might start to crawl.")
        if disk.free < 5 * 2**30 and "disk" not in self._alerted:
            self._alerted.add("disk")
            self._alert(f"Your main drive is almost full, about {disk.free / 2**30:.1f} gigabytes left.")

    def _alert(self, msg, urgent=False):
        """Heads-ups are spoken, except mid-game, where they show quietly (unless it's urgent)."""
        if config.GAME_MODE and not urgent and tools.fullscreen_app():
            self.emit({"type": "alert", "text": msg})
            self.emit({"type": "msg", "role": "system", "text": msg})
            return
        self.events.put(("alert", msg))

    def _emit_knowledge(self):
        self._emit_permissions()
        self.emit({"type": "memory", "items": tools.memories()[-50:]})
        self.emit({"type": "routines", "items": [{"name": k, "steps": v["steps"]} for k, v in tools.routines().items()]})

    def _emit_reminders(self):
        items = [{"id": r["id"], "message": r["message"], "due": r["due"]} for r in tools.REMINDERS.items]
        self.emit({"type": "reminders", "items": items})

    def _telemetry(self):
        import psutil
        tools._com_init()
        psutil.cpu_percent(None)
        last_net, last_t = psutil.net_io_counters(), time.time()
        tick = 0
        while not self._stop.wait(2):
            try:
                now = time.time()
                net = psutil.net_io_counters()
                dt = max(now - last_t, 0.1)
                up = (net.bytes_sent - last_net.bytes_sent) / dt / 1024
                down = (net.bytes_recv - last_net.bytes_recv) / dt / 1024
                last_net, last_t = net, now
                mem = psutil.virtual_memory()
                disk = psutil.disk_usage(config.HOME.anchor or "/")
                bat = psutil.sensors_battery()
                data = {
                    "type": "telemetry",
                    "cpu": psutil.cpu_percent(None),
                    "ram": mem.percent,
                    "ram_used": round(mem.used / 2**30, 1),
                    "ram_total": round(mem.total / 2**30, 1),
                    "disk": disk.percent,
                    "disk_free": round(disk.free / 2**30),
                    "battery": bat.percent if bat else None,
                    "plugged": bat.power_plugged if bat else None,
                    "up_kbps": round(up, 1),
                    "down_kbps": round(down, 1),
                    "uptime": int(now - psutil.boot_time()),
                    "procs": len(psutil.pids()),
                    "spend": usage.snapshot(),
                }
                if usage.warn_due():
                    self._alert(f"Heads up: we've used about {usage.today():.2f} of today's {usage.budget():.2f} dollar spending limit.")
                if config.ALERTS:
                    self._check_alerts(bat, mem, disk)
                if tick % 3 == 0:
                    vol = tools.volume_state()
                    if vol:
                        data["volume"], data["muted"] = vol
                self.emit(data)
                if tick % 5 == 0:
                    self._emit_reminders()
                    self._emit_knowledge()
                tick += 1
            except Exception as e:
                print(f"[telemetry] {e}")
