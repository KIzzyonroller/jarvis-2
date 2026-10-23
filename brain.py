"""
The thinking part: sends what you said to Claude, runs whatever tools
Claude asks for, loops until Claude has a final answer.
"""
import json
import re
import threading
import time
from datetime import datetime

import anthropic

import config
import personas
import tools
import usage



class Interrupted(Exception):
    """The user cut in; abandon this answer."""


def _ok(out):
    if isinstance(out, list):
        return True
    low = out.lower()
    return not (low.startswith(("tool ", "couldn't", "unknown", "not allowed", "no running", "too many"))
                or "did not authorize" in low or "failed" in low[:60] or "outside the folders" in low)


def _summary(out):
    if isinstance(out, list):
        return "[took a picture]"
    return out.replace("\n", " ")[:160]


class Brain:
    fast_broken = False          # shared: if the fast model isn't available on this account, stop trying it

    _guard_lock = threading.Lock()
    _done_calls = {}
    _started = {}

    def __init__(self, persona="jarvis", on_tool=None):
        if not config.ANTHROPIC_API_KEY or "paste-yours" in config.ANTHROPIC_API_KEY:
            raise SystemExit("No API key set. Open the .env file in the Jarvis folder and paste your Anthropic API key.")
        try:      # keep the connection to Claude open between requests (saves a TLS handshake each time)
            import httpx
            hc = anthropic.DefaultHttpxClient(limits=httpx.Limits(max_connections=20, max_keepalive_connections=10,
                                                                  keepalive_expiry=120))
            self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, http_client=hc)
        except Exception:
            self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self._last_net = 0.0
        self._ctx = ""
        self.on_tool = on_tool or (lambda name, args, result: None)
        self.history = []
        search = {"type": "web_search_20250305", "name": "web_search", "max_uses": config.WEB_SEARCH_MAX_USES}
        loc = {k: v for k, v in {"city": config.CITY, "region": config.REGION,
                                  "country": config.COUNTRY, "timezone": config.TIMEZONE}.items() if v}
        if loc:
            search["user_location"] = {"type": "approximate", **loc}
        self._search = search
        self.allowed = None       # a set of tool names to limit this brain to (background jobs), or None for all
        self.tools = tools.TOOL_SPECS + [search]
        self.persona_key = persona
        self.persona = personas.system_prompt(persona, config.ADDRESS_AS)
        self._reasoning = config.SHOW_REASONING
        self._cancel = None
        self._tools_on = True
        self._model = config.MODEL
        self._notes = []          # things the other AI said that this one should know about
        self.max_rounds = 15      # model calls per request (background jobs get more)
        self.private = True       # False for public chats (the Discord bot): no memory, routines or PC paths

    def note(self, text):
        """Pass along something that happened outside this conversation (e.g. the other AI's reply)."""
        self._notes.append(text)
        self._notes = self._notes[-4:]

    def reset(self):
        self.history = []

    def warm(self):
        """Called the moment you start talking: if the connection to Claude has gone idle, reopen it
        in the background, so the real request doesn't pay for the handshake. Free (no tokens)."""
        if time.time() - self._last_net < 25:
            return
        self._last_net = time.time()

        def go():
            try:
                self.client.models.list(limit=1)
            except Exception:
                pass
        import threading
        threading.Thread(target=go, daemon=True, name="api-warm").start()

    def _system(self):
        # This MUST stay identical between requests. Claude's reasoning blocks
        # are tied to the exact system prompt, so anything that changes here
        # (like the clock) invalidates every earlier block and the API 400s.
        # The current time goes into each user message instead.
        # Memory and routines go in a third block: they only change when you add one, so the
        # conversation history after them stays cacheable (faster, cheaper) between requests.
        blocks = [
            {"type": "text", "text": self.persona, "cache_control": {"type": "ephemeral"}},
        ]
        if self.private:
            blocks.append({"type": "text", "text": f"Jarvis folder: {config.JARVIS_DIR}. User home: {config.HOME}."})
        if self._ctx:
            blocks.append({"type": "text", "text": self._ctx})
        return blocks

    def _mark_cache(self):
        """One moving cache marker on the newest message: each request reuses everything before it."""
        for m in self.history:
            if isinstance(m.get("content"), list):
                for b in m["content"]:
                    if isinstance(b, dict):
                        b.pop("cache_control", None)
        last = self.history[-1] if self.history else None
        if not last or last["role"] != "user":
            return
        if isinstance(last["content"], str):
            last["content"] = [{"type": "text", "text": last["content"]}]
        if last["content"] and isinstance(last["content"][-1], dict):
            last["content"][-1]["cache_control"] = {"type": "ephemeral"}

    @staticmethod
    def _stamp(text):
        now = datetime.now().astimezone()
        return f"{text}\n\n[local time {now:%A %B %d %Y, %I:%M %p}, ISO {now.isoformat(timespec='minutes')}]"

    def _trim(self):
        # Trim in one big bite rather than a message every turn: every trim changes the start of the
        # conversation, which throws away the prompt cache, so do it rarely.
        if len(self.history) <= config.HISTORY_MESSAGES:
            return
        keep = max(4, int(config.HISTORY_MESSAGES * 0.6))
        while len(self.history) > keep:
            self.history.pop(0)
            while self.history and not self._starts_turn(self.history[0]):
                self.history.pop(0)

    @staticmethod
    def _starts_turn(m):
        """A message the user typed or said (not a tool result), where a conversation can safely begin."""
        if m["role"] != "user":
            return False
        c = m["content"]
        return isinstance(c, str) or (isinstance(c, list) and bool(c)
                                      and all(isinstance(b, dict) and b.get("type") == "text" for b in c))

    @staticmethod
    def _btype(b):
        return b.get("type") if isinstance(b, dict) else getattr(b, "type", None)

    def _strip_thinking(self, upto=None):
        """Remove reasoning blocks from finished turns. The API doesn't need
        them for past turns, and stale ones are the main source of 400s."""
        msgs = self.history if upto is None else self.history[:upto]
        for msg in msgs:
            if msg["role"] != "assistant" or isinstance(msg["content"], str):
                continue
            kept = [b for b in msg["content"] if self._btype(b) not in ("thinking", "redacted_thinking")]
            msg["content"] = kept or [{"type": "text", "text": "(done)"}]

    def _compact(self):
        self._strip_thinking()
        # Screenshots are big: swap old ones for a placeholder.
        for msg in self.history:
            if msg["role"] != "user" or not isinstance(msg["content"], list):
                continue
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result" and isinstance(block.get("content"), list):
                    block["content"] = [c if c.get("type") != "image" else {"type": "text", "text": "[old screenshot removed]"}
                                        for c in block["content"]]

    def _tool_list(self):
        specs = tools.all_specs()
        if self.allowed is not None:
            specs = [s for s in specs if s["name"] in self.allowed or (s["name"].count("__") and "connectors" in self.allowed)]
        out = specs + ([self._search] if self.allowed is None or "web_search" in self.allowed else [])
        self.tools = out
        return out

    def _kwargs(self):
        self._mark_cache()
        kw = dict(model=self._model, max_tokens=config.MAX_TOKENS, system=self._system(),
                  tools=self._tool_list(), messages=self.history)
        if self._reasoning and self._model == config.MODEL:     # the quick model answers straight away
            kw["thinking"] = {"type": "adaptive", "display": "summarized"}
        if not self._tools_on:
            kw["tool_choice"] = {"type": "none"}     # talk only (the other AI already did the doing)
        return kw

    def _stream_once(self, on_text, on_event):
        """One streamed request. Text is handed to on_text as it's generated."""
        self._last_net = time.time()
        with self.client.messages.stream(**self._kwargs()) as stream:
            for ev in stream:
                if self._cancel is not None and self._cancel.is_set():
                    raise Interrupted()
                t = getattr(ev, "type", "")
                if t == "content_block_start":
                    bt = ev.content_block.type
                    if bt == "thinking":
                        on_event("thinking_start", None)
                    elif bt in ("tool_use", "server_tool_use"):
                        on_event("tool_pending", {"name": ev.content_block.name})
                elif t == "content_block_delta":
                    dt = ev.delta.type
                    if dt == "text_delta":
                        on_text(ev.delta.text)
                    elif dt == "thinking_delta" and ev.delta.thinking:
                        on_event("thinking", ev.delta.thinking)
            msg = stream.get_final_message()
        try:
            usage.record_claude(self._model, msg.usage)
        except Exception as e:
            print(f"   [usage] couldn't record: {e}")
        return msg

    def _create(self, turn_start, on_text, on_event):
        try:
            return self._stream_once(on_text, on_event)
        except (anthropic.NotFoundError, anthropic.PermissionDeniedError, anthropic.BadRequestError) as e:
            if self._model != config.MODEL and ("model" in str(e).lower() or not isinstance(e, anthropic.BadRequestError)):
                print(f"   [brain] fast model {self._model} unavailable ({type(e).__name__}); using {config.MODEL}")
                Brain.fast_broken = True
                self._model = config.MODEL
                return self._create(turn_start, on_text, on_event)
            if not isinstance(e, anthropic.BadRequestError):
                raise
            return self._create_bad_request(e, turn_start, on_text, on_event)

    def _create_bad_request(self, e, turn_start, on_text, on_event):
        msg = str(e).lower()
        if "signature" in msg or "bound to a different" in msg:
            # Self-heal: drop reasoning from earlier turns and retry once.
            print("   [brain] stale reasoning block rejected, cleaning history and retrying")
            self._strip_thinking(upto=turn_start)
            try:
                return self._stream_once(on_text, on_event)
            except anthropic.BadRequestError:
                print("   [brain] still rejected, starting a fresh conversation")
                del self.history[:turn_start]
                self._strip_thinking()
                return self._stream_once(on_text, on_event)
        if self._reasoning and "thinking" in msg:
            # This model doesn't accept the reasoning-display option. Turn it off and carry on.
            print("   [brain] model rejected visible reasoning; continuing without it")
            self._reasoning = False
            return self._stream_once(on_text, on_event)
        raise e


    # Tools that don't depend on what's on screen or on each other: when Claude asks for several in
    # one go ("open Steam and Discord, volume 30"), they run at the same time instead of one by one.
    PARALLEL_SAFE = {"open", "close_app", "set_volume", "display", "system_info", "look_at_camera"}

    # Things that open or start something: repeating them in one request means duplicate tabs/windows.
    ONCE_PER_REQUEST = {"open", "youtube", "spotify", "close_app"}

    def _guard(self, b):
        """None to go ahead, or the result to return instead of running the call again."""
        if b.name not in self.ONCE_PER_REQUEST:
            return None
        args = b.input if isinstance(b.input, dict) else {}
        key = b.name + json.dumps(args, sort_keys=True)
        with self._guard_lock:
            if key in self._done_calls:
                return f"(Already done a moment ago in this request: {self._done_calls[key]}) Don't repeat it."
            service = b.name
            if b.name == "open":                     # a raw link is the same thing by another route
                tgt = str(args.get("target", "")).lower()
                service = "spotify" if tgt.startswith("spotify:") else "youtube" if ("youtube.com" in tgt or "youtu.be" in tgt) else None
            starts = service in ("youtube", "spotify") and (b.name == "open" or (
                (args.get("action") or "play") == "play" and (args.get("query") or args.get("video") or args.get("index") is not None)))
            if starts and service in self._started:
                return (f"(Not opening anything else on {service}: this request already did: "
                        f"{self._started[service]}) Tell the user what happened; don't try again.")
            # the same thing on the other service = a retry in disguise (the "4 YouTube tabs" bug)
            words = set(re.findall(r"[a-z0-9]+", str(args.get("query") or args.get("target") or "").lower())) - {"spotify", "search", "youtube", "my", "the", "a"}
            for other, w in getattr(self, "_started_words", {}).items():
                if starts and other != service and words and w and len(words & w) / max(1, min(len(words), len(w))) >= .5:
                    return (f"(Not also opening it on {service}: it was just handled on {other}: {self._started.get(other)}) "
                            f"Tell the user what happened; don't try another service.")
            self._done_calls[key] = "running"
            if starts:
                self._started[service] = "something"
                self._started_words[service] = words
                b._service = service
        return None

    def _run_one(self, b, on_event):
        skip = self._guard(b)
        if skip is not None:
            print(f"   [tool] {b.name} skipped (duplicate)")
            return {"type": "tool_result", "tool_use_id": b.id, "content": skip}
        print(f"   [tool] {b.name} {json.dumps(b.input)[:150]}")
        on_event("tool_start", {"name": b.name, "args": b.input})
        t0 = time.time()
        out = tools.run_tool(b.name, b.input)
        print(f"          -> {_summary(out)}")
        if isinstance(out, list):   # show the user exactly what he looked at
            for blk in out:
                if blk.get("type") == "image":
                    on_event("image", {"name": b.name, "src": "data:image/jpeg;base64," + blk["source"]["data"]})
        on_event("tool_done", {"name": b.name, "args": b.input, "result": _summary(out),
                               "ok": _ok(out), "secs": round(time.time() - t0, 1)})
        self.on_tool(b.name, b.input, _summary(out))
        if b.name in self.ONCE_PER_REQUEST:
            with self._guard_lock:
                self._done_calls[b.name + json.dumps(b.input if isinstance(b.input, dict) else {}, sort_keys=True)] = _summary(out)[:120]
                svc = getattr(b, "_service", None)
                if svc:
                    self._started[svc] = _summary(out)[:120]
        return {"type": "tool_result", "tool_use_id": b.id, "content": out}

    def _run_tools(self, calls, on_event, cancel):
        """Run in order, but back-to-back parallel-safe calls run together."""
        from concurrent.futures import ThreadPoolExecutor

        def worker(b):
            tools._com_init()           # volume control needs COM set up on each thread
            return self._run_one(b, on_event)
        results, i = [], 0
        while i < len(calls):
            if cancel is not None and cancel.is_set():
                raise Interrupted()
            j = i
            while j < len(calls) and calls[j].name in self.PARALLEL_SAFE:
                j += 1
            if j - i >= 2:
                with ThreadPoolExecutor(max_workers=j - i) as ex:
                    results += list(ex.map(worker, calls[i:j]))      # map keeps the original order
                i = j
            else:
                results.append(self._run_one(calls[i], on_event))
                i += 1
        return results

    def ask(self, text, on_text=None, on_event=None, cancel=None, allow_tools=True, quick=False):
        """on_text(delta): reply text as it streams. on_event(kind, data): progress
        (thinking_start, thinking, tool_pending, tool_start, tool_done).
        quick=True: use the fast model (simple requests); falls back to the main one if unavailable."""
        on_text = on_text or (lambda d: None)
        on_event = on_event or (lambda k, d: None)
        if usage.over_budget():
            return (f"We've hit today's spending limit of {usage.budget():.2f} dollars, so I'm holding off on anything "
                    "that needs thinking until tomorrow. Quick commands still work. Say raise my budget to, and an "
                    "amount, if you want to keep going.")
        self._cancel = cancel
        self._tools_on = allow_tools
        self._done_calls, self._started, self._started_words = {}, {}, {}     # per request: see _guard
        self._model = (config.FAST_MODEL if quick and config.FAST_MODEL and not Brain.fast_broken else config.MODEL)
        if self._notes:
            text = "[Meanwhile: " + " ".join(self._notes) + "]\n" + text
            self._notes = []
        note = tools.context_note() if self.private else ""
        self._ctx = f"[{note}]" if note else ""
        user_msg = {"role": "user", "content": self._stamp(text)}
        self.history.append(user_msg)
        self._trim()

        def rollback():   # undo this whole turn so a failure can't poison later requests
            for i, m in enumerate(self.history):
                if m is user_msg:
                    del self.history[i:]
                    return

        spoken_along_the_way = []
        try:
            for rnd in range(self.max_rounds):
                if rnd and usage.over_budget():
                    rollback()
                    return (" ".join(spoken_along_the_way) + " I've hit today's spending limit, so I stopped there.").strip()
                turn_start = next(i for i, m in enumerate(self.history) if m is user_msg)
                resp = self._create(turn_start, on_text, on_event)
                on_text("\n")   # sentence boundary between this message and the next
                self.history.append({"role": "assistant",
                                     "content": resp.content or [{"type": "text", "text": "(no response)"}]})
                text_now = "".join(b.text for b in resp.content if b.type == "text").strip()

                for b in resp.content:
                    if b.type == "server_tool_use":
                        q = (b.input or {}).get("query", "") if isinstance(b.input, dict) else ""
                        on_event("tool_done", {"name": b.name, "args": b.input, "result": f"searched: {q}", "ok": True})
                        self.on_tool(b.name, b.input, "searching the web")

                if resp.stop_reason == "tool_use":
                    if text_now:
                        spoken_along_the_way.append(text_now)
                    calls = [b for b in resp.content if b.type == "tool_use"]
                    results = self._run_tools(calls, on_event, cancel)
                    self.history.append({"role": "user", "content": results})
                    continue

                if resp.stop_reason == "pause_turn":
                    continue

                if resp.stop_reason == "refusal":
                    return text_now or "I'm not going to do that one."
                return text_now or " ".join(spoken_along_the_way) or "Done."
            return "I went round in circles on that one and gave up. Try asking differently."
        except Interrupted:
            rollback()
            return None
        except anthropic.AuthenticationError:
            rollback()
            return "My API key was rejected. Check the key in the .env file."
        except anthropic.APIConnectionError:
            rollback()
            return "I can't reach my brain. Check your internet connection."
        except anthropic.RateLimitError:
            rollback()
            return "I'm being rate limited. Give it a few seconds and try again."
        except anthropic.APIStatusError as e:
            rollback()
            print(f"   [api error] {e}")
            low = str(e).lower()
            if "credit" in low or "billing" in low:
                return "The API says you're out of credit. Top up at console.anthropic.com."
            if e.status_code == 404 or "model" in low and "not found" in low:
                return f"The model {config.MODEL} wasn't found. Check JARVIS_MODEL in your .env file."
            if e.status_code in (500, 502, 503, 529):
                return "The API is overloaded right now. Try again in a moment."
            return f"The API threw an error, status {e.status_code}. Details are in the console."
        except Exception as e:
            rollback()
            print(f"   [brain error] {type(e).__name__}: {e}")
            return f"Something broke on my end: {type(e).__name__}. Details are in the console."
        finally:
            self._compact()
