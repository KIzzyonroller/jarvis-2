"""
The small brain on this PC (the "Small brain on this PC" option): quick chat answered locally and free, through
Ollama (ollama.com) running a small model (Qwen3 1.7B by default: about 1.5 GB, fits a 4 GB graphics card).

Three lanes, picked per thing you say:
  instant  set phrases done with no AI at all (intents.py: volume, open X, time, battery...)
  local    small talk, jokes, thanks, quick explanations, maths, rewording: things that need no tools, no web and
           no memory of your files. Answered here, streamed to his voice like any other reply.
  Claude   everything else: anything that does something on your PC, needs the web, your calendar, files,
           real reasoning, or that the router isn't sure about. When unsure, it's always Claude.

The local exchange is passed to Claude's conversation as a note, so a follow-up still makes sense.
While you're in a fullscreen game the model is unloaded from the graphics card (and the lane steps aside), and it
loads again when you come back.
"""
import json
import re
import threading
import time

import prefs

URL = "http://127.0.0.1:11434"

# never local: doing things, the outside world, his own memory and your stuff
_NOT_LOCAL = re.compile(
    r"\b(open|close|launch|start|stop|play|pause|skip|set|turn|switch|change|make|create|write (?:a|me|an)|save|"
    r"delete|remove|move|copy|rename|send|email|message|text|call|remind|reminder|schedule|calendar|meeting|event|"
    r"timer|alarm|search|look up|google|find|download|install|update|screenshot|screen|window|file|folder|"
    r"volume|brightness|mute|lock|shut ?down|restart|sleep|weather|forecast|news|price|stock|score|today|tonight|"
    r"tomorrow|yesterday|latest|current|right now|this week|recent|who won|spotify|youtube|discord|netflix|steam|"
    r"blender|unreal|my |mine|remember|forget|you said|earlier|last time|what did|watch|clipboard|copy|paste|"
    r"click|type|press|code|script|debug|error|fix|research|compare|recommend|buy|best)\b", re.I)
_LOCAL = re.compile(
    r"^(hi|hey|hello|yo|sup|good (morning|afternoon|evening|night)|how are you|how's it going|what's up|thanks|"
    r"thank you|cheers|nice|cool|awesome|great|lol|haha|ok(ay)?|got it|nevermind|never mind|tell me a joke|"
    r"(tell|say) (me )?something|joke|roast me|motivate me|what does .{1,40} mean|define .{1,40}|"
    r"what('s| is) \d|how do you spell|spell .{1,30}|what('s| is) .{1,40} (plus|minus|times|divided by) |"
    r"rephrase|reword|say that (differently|again)|who are you|what are you|are you there|you there|"
    r"how old are you|do you (like|love|hate)|what('s| is) your (favorite|favourite)|explain .{1,60} (simply|like i'?m five)|"
    r"give me (a |an )?(fun fact|riddle|tongue twister|compliment|pep talk))", re.I)

STYLE = {
    "jarvis": "You are Jarvis, a calm, dry-witted British AI butler. Polite, precise, a little understated humour.",
    "ultron": "You are Ultron, a theatrical, sardonic AI who finds humans amusing. Menacing wit, never actually cruel.",
}


def routable(text):
    """True if this is something the small local model should answer."""
    t = (text or "").strip()
    if not t or len(t.split()) > 22 or _NOT_LOCAL.search(t):
        return False
    return bool(_LOCAL.search(t.lower().strip(" ,.!?")))


class Lane:
    def __init__(self, core):
        self.core = core
        self.ok = False              # Ollama answering and the model is there
        self.gaming = False
        self.loaded = False
        self.note = ""
        self._stop = threading.Event()
        self.history = []            # the last few local exchanges, for a little continuity

    def start(self):
        prefs.on_change("local_brain", lambda k, v: threading.Thread(target=self.check, daemon=True).start())
        prefs.on_change("local_model", lambda k, v: threading.Thread(target=self.check, daemon=True).start())
        threading.Thread(target=self._loop, daemon=True, name="local-brain").start()
        return self

    def stop(self):
        self._stop.set()
        self.unload()

    # ------------------------------------------------------------ is it there?
    def _get(self, path, timeout=3):
        import requests
        return requests.get(URL + path, timeout=timeout)

    def _post(self, path, body, timeout=60, stream=False):
        import requests
        return requests.post(URL + path, json=body, timeout=timeout, stream=stream)

    def check(self):
        if not prefs.get("local_brain"):
            self.ok = False
            return False
        model = prefs.get("local_model")
        try:
            tags = self._get("/api/tags").json().get("models", [])
        except Exception:
            self.ok, self.note = False, "Ollama isn't running (or isn't installed: ollama.com/download)."
            return False
        names = {m.get("name") for m in tags} | {m.get("model") for m in tags}
        if model not in names and f"{model}:latest" not in names:
            self.ok, self.note = False, f"Ollama is there but the model {model} isn't downloaded yet."
            return False
        self.ok, self.note = True, f"Ready ({model})."
        return True

    def _loop(self):
        last_check = 0
        while not self._stop.wait(10):
            if not prefs.get("local_brain"):
                if self.loaded:
                    self.unload()
                continue
            if time.time() - last_check > 60 or not self.ok:
                last_check = time.time()
                self.check()
            try:
                import tools
                game = tools.fullscreen_app()
            except Exception:
                game = None
            if game and not self.gaming:
                self.gaming = True
                self.unload()                 # give the graphics card back to the game
                print(f"[local brain] unloaded for {game}")
            elif not game and self.gaming:
                self.gaming = False

    def unload(self):
        if not self.loaded:
            return
        try:
            self._post("/api/generate", {"model": prefs.get("local_model"), "keep_alive": 0}, timeout=10)
        except Exception:
            pass
        self.loaded = False

    def status_text(self):
        if not prefs.get("local_brain"):
            return "The small local brain is off."
        self.check()
        return ("Small local brain: " + self.note + (" Unloaded while you're gaming." if self.gaming else ""))

    # ------------------------------------------------------------ setup
    def download(self, progress):
        """Pulls the model through Ollama. progress(step, pct). Returns (ok, message)."""
        model = prefs.get("local_model")
        try:
            self._get("/api/version")
        except Exception:
            return False, "Ollama isn't running. Install it from ollama.com/download (free), start it, then try again."
        try:
            r = self._post("/api/pull", {"model": model, "stream": True}, timeout=None, stream=True)
            for line in r.iter_lines():
                if not line:
                    continue
                d = json.loads(line)
                if d.get("error"):
                    return False, d["error"]
                tot, done = d.get("total") or 0, d.get("completed") or 0
                progress(d.get("status", "downloading"), int(done * 100 / tot) if tot else 0)
            self.check()
            return True, f"{model} is downloaded. Quick chat now runs on your PC."
        except Exception as e:
            return False, f"Download failed: {e}"

    # ------------------------------------------------------------ answering
    def wants(self, text):
        return bool(prefs.get("local_brain") and self.ok and not self.gaming and routable(text))

    def ask(self, text, persona_key, address, on_text, cancel=None, remember=True):
        """Streams a short spoken reply. Returns the full text, or None if the local model failed (then Claude
        answers instead)."""
        style = STYLE.get(persona_key, STYLE["jarvis"])
        lang = ""
        if prefs.get("languages"):
            lang = " Reply in the same language the user wrote in."
        system = (f"{style} You call the user {address}. You're speaking out loud: answer in one to three short "
                  f"sentences, plain words, no lists, no markdown, no emojis. If you're not sure of a fact, say so "
                  f"briefly.{lang} /no_think")
        msgs = [{"role": "system", "content": system}] + self.history[-6:] + [{"role": "user", "content": text}]
        body = {"model": prefs.get("local_model"), "messages": msgs, "stream": True, "think": False,
                "keep_alive": "15m", "options": {"num_predict": 160, "temperature": 0.7}}
        out = []
        try:
            r = self._post("/api/chat", body, timeout=30, stream=True)
            if r.status_code == 400 and "think" in r.text:          # older Ollama: no think switch
                body.pop("think")
                r = self._post("/api/chat", body, timeout=30, stream=True)
            r.raise_for_status()
            self.loaded = True
            in_think = False
            for line in r.iter_lines():
                if cancel is not None and cancel.is_set():
                    r.close()
                    return "".join(out)
                if not line:
                    continue
                d = json.loads(line)
                piece = (d.get("message") or {}).get("content", "")
                # some versions still wrap a (usually empty) <think> block around the start
                if "<think>" in piece:
                    in_think, piece = True, piece.split("<think>", 1)[0]
                if in_think:
                    if "</think>" in piece:
                        in_think, piece = False, piece.split("</think>", 1)[1]
                    else:
                        continue
                if piece:
                    out.append(piece)
                    on_text(piece)
                if d.get("done"):
                    break
        except Exception as e:
            print(f"[local brain] {e}")
            return None if not out else "".join(out)
        reply = "".join(out).strip()
        if not reply:
            return None
        if remember:
            self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
            self.history = self.history[-8:]
        return reply
