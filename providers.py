"""
The AI services a Blender or Unreal key can be for. Paste any of these and he works out which it is:

  * Claude (Anthropic)  sk-ant-...   console.anthropic.com
  * OpenRouter          sk-or-...    openrouter.ai (one key, many models: Claude, GPT, Gemini...)
  * OpenAI              sk-...       platform.openai.com

Each mode (Blender, Unreal) has its own key, so its spending lands on that key's bill, separate from
Jarvis's main Claude key. Model: an optional "model" setting per mode; otherwise he picks the strongest
general model that key can use.

agent(...).run() is a small tool-using loop that works the same on all three, so the expert modes don't care
which service is behind them.
"""
import base64
import json
import re
import time

import config

LABEL = {"anthropic": "Claude", "openrouter": "OpenRouter", "openai": "OpenAI"}
OPENAI_URL = "https://api.openai.com/v1"
OPENROUTER_URL = "https://openrouter.ai/api/v1"

# strongest first; the first pattern a key can use wins
PREFS = {
    "openai": [r"^gpt-5(\.\d+)?$", r"^gpt-5(\.\d+)?-\d{4}", r"^gpt-4\.1$", r"^gpt-4o$"],
    "openrouter": [r"^anthropic/claude-sonnet", r"^anthropic/claude-opus", r"^openai/gpt-5(\.\d+)?$",
                   r"^google/gemini-[\d.]+-pro", r"^anthropic/claude"],
}
SKIP = re.compile(r"(mini|nano|audio|realtime|search|transcribe|tts|image|embedding|instruct|preview|:free)", re.I)
_MODEL_CACHE = {}


def detect(key):
    k = (key or "").strip()
    if k.startswith("sk-ant-"):
        return "anthropic"
    if k.startswith("sk-or-"):
        return "openrouter"
    if k.startswith("sk-"):
        return "openai"
    return None


def looks_valid(key):
    """None if the key is shaped like one of the three, else a sentence why not."""
    k = (key or "").strip()
    if " " in k or len(k) < 30:
        return "That doesn't look like a full key (they're long, with no spaces)."
    if not detect(k):
        return "That isn't a Claude (sk-ant-), OpenRouter (sk-or-) or OpenAI (sk-) key."
    return None


def _http(method, url, key, body=None, timeout=60):
    import requests
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if "openrouter.ai" in url:
        headers.update({"HTTP-Referer": "https://github.com/KIzzyonroller/jarvis-2", "X-Title": "Jarvis"})
    r = requests.request(method, url, headers=headers, json=body, timeout=timeout)
    return r


def check(key):
    """Ask the service whether it accepts the key. (ok, sentence). Network trouble counts as ok: we can't tell."""
    p = detect(key)
    if not p:
        return False, looks_valid(key) or "Unknown kind of key."
    try:
        if p == "anthropic":
            import anthropic
            anthropic.Anthropic(api_key=key, timeout=15, max_retries=0).models.list(limit=1)
            return True, "Claude accepted the key."
        url = OPENROUTER_URL + "/auth/key" if p == "openrouter" else OPENAI_URL + "/models"
        r = _http("GET", url, key, timeout=15)
        if r.status_code in (401, 403):
            return False, f"{LABEL[p]} says that key isn't valid. Copy it again from their site."
        return True, f"{LABEL[p]} accepted the key."
    except Exception as e:
        if type(e).__name__ in ("AuthenticationError", "PermissionDeniedError"):
            return False, "Anthropic says that key isn't valid. Copy it again from console.anthropic.com."
        return True, f"Couldn't reach {LABEL[p]} to check it right now ({type(e).__name__}); saved anyway."


def _best(ids, prefs):
    ids = [i for i in ids if not SKIP.search(i)]
    for pat in prefs:
        hits = sorted((i for i in ids if re.search(pat, i)), reverse=True)    # newest version sorts last alphabetically
        if hits:
            return hits[0]
    return None


def pick_model(provider, key, override=""):
    """The model to use: the per-mode setting if there is one, else the strongest one this key can use."""
    if (override or "").strip():
        return override.strip()
    if provider == "anthropic":
        return config.MODEL
    cached = _MODEL_CACHE.get((provider, key[-8:]))
    if cached:
        return cached
    fallback = {"openai": "gpt-4o", "openrouter": "anthropic/claude-sonnet-4.5"}[provider]
    try:
        url = (OPENROUTER_URL if provider == "openrouter" else OPENAI_URL) + "/models"
        data = _http("GET", url, key, timeout=15).json().get("data") or []
        model = _best([d.get("id", "") for d in data], PREFS[provider]) or fallback
    except Exception:
        model = fallback
    _MODEL_CACHE[(provider, key[-8:])] = model
    return model


class Stopped(Exception):
    pass


# ============================================================ the loop
class _Base:
    def __init__(self, key, model, provider):
        self.key, self.model, self.provider = key, model, provider
        self.usage = {"input": 0, "output": 0, "usd": 0.0, "usd_known": True, "calls": 0}

    def run(self, system, task, specs, run_tool, on_event=None, cancel=None, max_rounds=14):
        """Work on task with the given tools until done. Returns the final text for the user."""
        raise NotImplementedError


class AnthropicAgent(_Base):
    def run(self, system, task, specs, run_tool, on_event=None, cancel=None, max_rounds=14):
        import anthropic
        import usage
        on_event = on_event or (lambda k, d: None)
        client = anthropic.Anthropic(api_key=self.key, max_retries=2)
        msgs = [{"role": "user", "content": task}]
        sys_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        text = ""
        for rnd in range(max_rounds):
            if cancel is not None and cancel.is_set():
                raise Stopped()
            last_round = rnd == max_rounds - 1
            kw = dict(model=self.model, max_tokens=8000, system=sys_blocks, messages=msgs, tools=specs)
            if last_round:
                kw["tool_choice"] = {"type": "none"}
            msg = client.messages.create(**kw)
            self.usage["calls"] += 1
            u = msg.usage
            self.usage["input"] += (u.input_tokens or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0) \
                + (getattr(u, "cache_creation_input_tokens", 0) or 0)
            self.usage["output"] += u.output_tokens or 0
            try:
                self.usage["usd"] += usage.cost_of(self.model, u)[0]
            except Exception:
                pass
            msgs.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in msg.content]})
            text = "".join(b.text for b in msg.content if b.type == "text").strip() or text
            calls = [b for b in msg.content if b.type == "tool_use"]
            if not calls or msg.stop_reason != "tool_use":
                return text
            results = []
            for b in calls:
                out = _call(run_tool, b.name, b.input, on_event)
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": out if isinstance(out, list) else str(out)})
            msgs.append({"role": "user", "content": results})
            _drop_old_images(msgs)
        return text or "I ran out of steps before finishing; the work so far is in the editor."


class OpenAIAgent(_Base):
    """OpenAI and OpenRouter (same chat-completions API with function calling)."""
    def run(self, system, task, specs, run_tool, on_event=None, cancel=None, max_rounds=14):
        on_event = on_event or (lambda k, d: None)
        url = (OPENROUTER_URL if self.provider == "openrouter" else OPENAI_URL) + "/chat/completions"
        fns = [{"type": "function", "function": {"name": s["name"], "description": s["description"][:1024],
                                                 "parameters": s["input_schema"]}} for s in specs]
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": task}]
        text = ""
        for rnd in range(max_rounds):
            if cancel is not None and cancel.is_set():
                raise Stopped()
            body = {"model": self.model, "messages": msgs, "tools": fns,
                    "tool_choice": "none" if rnd == max_rounds - 1 else "auto"}
            if self.provider == "openrouter":
                body["usage"] = {"include": True}            # OpenRouter reports the real cost
            data = self._post(url, body)
            self.usage["calls"] += 1
            u = data.get("usage") or {}
            self.usage["input"] += u.get("prompt_tokens") or 0
            self.usage["output"] += u.get("completion_tokens") or 0
            if isinstance(u.get("cost"), (int, float)):
                self.usage["usd"] += float(u["cost"])
            else:
                self.usage["usd_known"] = False
            m = ((data.get("choices") or [{}])[0].get("message")) or {}
            calls = m.get("tool_calls") or []
            text = (m.get("content") or "").strip() or text
            msgs.append({k: v for k, v in {"role": "assistant", "content": m.get("content") or "",
                                           "tool_calls": calls or None}.items() if v is not None})
            if not calls:
                return text
            images = []
            for c in calls:
                fn = c.get("function") or {}
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except ValueError:
                    args = {}
                out = _call(run_tool, fn.get("name", ""), args, on_event)
                if isinstance(out, list):                    # tool messages are text-only: images follow separately
                    txt = "\n".join(b.get("text", "") for b in out if b.get("type") == "text")
                    images += [b for b in out if b.get("type") == "image"]
                    out = txt or "(picture attached below)"
                msgs.append({"role": "tool", "tool_call_id": c.get("id"), "content": str(out)[:20000]})
            if images:
                msgs.append({"role": "user", "content": [{"type": "text", "text": "Pictures from those tools:"}] + [
                    {"type": "image_url", "image_url": {"url": f"data:{b['source']['media_type']};base64,{b['source']['data']}"}}
                    for b in images[-2:]]})
            _drop_old_images(msgs, openai=True)
        return text or "I ran out of steps before finishing; the work so far is in the editor."

    def _post(self, url, body, tries=3):
        for i in range(tries):
            r = _http("POST", url, self.key, body, timeout=180)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 * (i + 1))
                continue
            if r.status_code >= 400:
                try:
                    err = (r.json().get("error") or {}).get("message") or r.text
                except ValueError:
                    err = r.text
                raise RuntimeError(f"{LABEL[self.provider]} refused ({r.status_code}): {str(err)[:300]}")
            return r.json()
        raise RuntimeError(f"{LABEL[self.provider]} is busy (rate limited or down); try again in a minute.")


def _call(run_tool, name, args, on_event):
    on_event("tool_start", {"name": name, "args": args})
    t0 = time.time()
    try:
        out = run_tool(name, args or {})
    except Exception as e:
        out = f"Tool {name} failed: {type(e).__name__}: {e}"
    summary = out if isinstance(out, str) else " ".join(b.get("text", "") for b in out if b.get("type") == "text")
    on_event("tool_done", {"name": name, "args": args, "result": summary[:300], "ok": not str(summary).startswith(
        ("Tool ", "Didn't run", "Couldn't", "Unreal isn't", "Blender error")), "secs": round(time.time() - t0, 1)})
    return out


def _drop_old_images(msgs, openai=False, keep=2):
    """Screenshots are big: keep only the newest couple in the conversation."""
    seen = 0
    for m in reversed(msgs):
        content = m.get("content")
        if not isinstance(content, list):
            continue
        for i, b in enumerate(content):
            inner = b.get("content") if isinstance(b, dict) and b.get("type") == "tool_result" else None
            if isinstance(inner, list):
                for j, c in enumerate(inner):
                    if c.get("type") == "image":
                        seen += 1
                        if seen > keep:
                            inner[j] = {"type": "text", "text": "[older picture removed]"}
            elif isinstance(b, dict) and b.get("type") in ("image", "image_url"):
                seen += 1
                if seen > keep:
                    content[i] = {"type": "text", "text": "[older picture removed]"}


def agent(key, model_override=""):
    p = detect(key)
    if not p:
        raise ValueError("unknown key type")
    model = pick_model(p, key, model_override)
    return (AnthropicAgent if p == "anthropic" else OpenAIAgent)(key, model, p)


def b64(data):
    return base64.b64encode(data).decode()
