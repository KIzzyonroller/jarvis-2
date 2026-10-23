"""
App connectors via MCP (Model Context Protocol), the standard way of plugging AI assistants into apps.
Instead of hand-writing every integration, he can use any existing MCP server: calendars, email, notes,
GitHub, smart homes, databases, your files...

Setup: list servers in Documents\\Jarvis\\mcp.json, in the same format Claude Desktop uses:

    {"mcpServers": {
        "files":  {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:\\\\Users\\\\you\\\\Notes"]},
        "remote": {"url": "https://example.com/mcp", "headers": {"Authorization": "Bearer TOKEN"}},
        "off":    {"command": "...", "disabled": true}
    }}

Say "Jarvis, reload your connectors" after editing (or restart him). Each server's tools show up for
him as "<server>__<tool>". Tools the server marks read-only just run; anything else goes through the
approval card (category "App connectors", which can be set to always allow).

Servers started with "command" run on your PC; many need Node.js (for npx) or uv (for uvx) installed.
A server's own messages go to Documents\\Jarvis\\logs\\mcp-<name>.log, which is where to look if one
won't connect.
"""
import asyncio
import json
import os
import re
import shutil
import threading
import time
from contextlib import AsyncExitStack

import config

FILE = config.JARVIS_DIR / "mcp.json"
MAX_TOOLS = 60                      # across all servers: each tool costs a little speed and attention
CALL_TIMEOUT = 90


def _safe(s):
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(s))


def _get(obj, *names, default=None):
    """Works with both the old (camelCase) and new (snake_case) MCP library field names."""
    for n in names:
        v = getattr(obj, n, None)
        if v is not None:
            return v
    return default


class Connectors:
    def __init__(self, log=print):
        self.log = log
        self.servers = {}          # name -> {"status", "error", "tools", "session", "stack", "cfg"}
        self.by_tool = {}          # claude tool name -> (server, tool name, read_only)
        self._specs = []
        self.loop = None
        self._ready = threading.Event()
        self.on_change = lambda: None

    # ---------------------------------------------------------------- lifecycle
    def start(self):
        if self.loop is None:
            def run():
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                self._ready.set()
                self.loop.run_forever()
            threading.Thread(target=run, daemon=True, name="connectors").start()
            self._ready.wait(5)
        self.reload()

    def read_config(self):
        try:
            d = json.loads(FILE.read_text(encoding="utf-8"))
            return {k: v for k, v in (d.get("mcpServers") or {}).items() if isinstance(v, dict) and not v.get("disabled")}
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            self.log(f"[connectors] can't read {FILE}: {e}")
            return {}

    def reload(self, wait=20):
        """(Re)connect to everything in mcp.json. Returns a one-line summary."""
        try:
            fut = asyncio.run_coroutine_threadsafe(self._reload(), self.loop)
            fut.result(timeout=wait)
        except Exception as e:
            self.log(f"[connectors] still connecting in the background ({type(e).__name__})")
        return self.summary()

    async def _reload(self):
        for name, s in list(self.servers.items()):
            await self._close(name)
        self.servers = {}
        cfg = self.read_config()
        await asyncio.gather(*(self._connect(n, c) for n, c in cfg.items()), return_exceptions=True)
        self._rebuild()

    async def _close(self, name):
        s = self.servers.get(name)
        if s and s.get("stack"):
            try:
                await s["stack"].aclose()
            except Exception:
                pass

    async def _connect(self, name, cfg):
        from mcp import ClientSession
        s = {"status": "connecting", "error": None, "tools": [], "cfg": cfg, "stack": AsyncExitStack()}
        self.servers[name] = s
        stack = s["stack"]
        try:
            if cfg.get("url"):
                url, headers = cfg["url"], cfg.get("headers") or {}
                if cfg.get("type") == "sse" or url.rstrip("/").endswith("/sse"):
                    from mcp.client.sse import sse_client
                    streams = await stack.enter_async_context(sse_client(url, headers=headers))
                else:
                    import mcp.client.streamable_http as sh
                    if hasattr(sh, "streamable_http_client"):          # current library
                        client = sh.create_mcp_http_client(headers=headers) if headers else None
                        cm = sh.streamable_http_client(url, http_client=client) if client else sh.streamable_http_client(url)
                    else:                                              # older library
                        cm = sh.streamablehttp_client(url, headers=headers)
                    streams = await stack.enter_async_context(cm)
            elif cfg.get("command"):
                from mcp import StdioServerParameters
                from mcp.client.stdio import stdio_client
                cmd = shutil.which(cfg["command"]) or cfg["command"]      # finds npx.cmd etc. on Windows
                env = {**os.environ, **{k: str(v) for k, v in (cfg.get("env") or {}).items()}}
                logdir = config.JARVIS_DIR / "logs"
                logdir.mkdir(parents=True, exist_ok=True)
                errlog = stack.enter_context(open(logdir / f"mcp-{_safe(name)}.log", "a", encoding="utf-8"))
                params = StdioServerParameters(command=cmd, args=[str(a) for a in cfg.get("args") or []], env=env,
                                               cwd=cfg.get("cwd"))
                streams = await stack.enter_async_context(stdio_client(params, errlog=errlog))
            else:
                raise ValueError("needs either \"command\" or \"url\"")
            read, write = streams[0], streams[1]
            session = await stack.enter_async_context(ClientSession(read, write))
            await asyncio.wait_for(session.initialize(), 30)
            res = await asyncio.wait_for(session.list_tools(), 30)
            s["session"] = session
            s["tools"] = list(_get(res, "tools", default=[]))
            s["status"] = "connected"
            self.log(f"[connectors] {name}: connected, {len(s['tools'])} tools")
        except BaseException as e:                 # never let one bad server take the others (or him) down
            s["status"], s["error"] = "failed", f"{type(e).__name__}: {e}"[:300]
            self.log(f"[connectors] {name}: couldn't connect ({s['error']})")
            try:
                await stack.aclose()
            except BaseException:
                pass

    def _rebuild(self):
        specs, by_tool = [], {}
        for name, s in self.servers.items():
            for t in s["tools"]:
                if len(specs) >= MAX_TOOLS:
                    self.log(f"[connectors] more than {MAX_TOOLS} connector tools; skipping the rest")
                    break
                tname = _get(t, "name")
                full = (f"{_safe(name)}__{_safe(tname)}")[:64]
                schema = _get(t, "input_schema", "inputSchema") or {}
                if not isinstance(schema, dict) or schema.get("type") != "object":
                    schema = {"type": "object", "properties": {}}
                ann = _get(t, "annotations")
                read_only = bool(ann is not None and _get(ann, "read_only_hint", "readOnlyHint", default=False))
                desc = (_get(t, "description") or _get(t, "title") or tname or "").strip()
                specs.append({"name": full, "description": f"[{name} connector] {desc}"[:1000], "input_schema": schema})
                by_tool[full] = (name, tname, read_only)
        self._specs, self.by_tool = specs, by_tool
        try:
            self.on_change()
        except Exception:
            pass

    # ---------------------------------------------------------------- used by tools.py
    def specs(self):
        return list(self._specs)

    def has(self, name):
        return name in self.by_tool

    def call(self, full, args):
        import tools
        server, tname, read_only = self.by_tool[full]
        s = self.servers.get(server) or {}
        if s.get("status") != "connected":
            return f"The {server} connector isn't connected right now."
        if not read_only:
            detail = json.dumps(args or {}, ensure_ascii=False, indent=1)[:900]
            if not tools._confirm(f"Use {server}: {tname}", detail, "connectors"):
                return tools.DENIED
        try:
            fut = asyncio.run_coroutine_threadsafe(s["session"].call_tool(tname, args or {}), self.loop)
            res = fut.result(timeout=CALL_TIMEOUT)
        except Exception as e:
            return f"The {server} connector failed: {type(e).__name__}: {e}"
        return self._format(server, res)

    @staticmethod
    def _format(server, res):
        texts, images = [], []
        for c in _get(res, "content", default=[]) or []:
            kind = _get(c, "type")
            if kind == "text":
                texts.append(_get(c, "text", default=""))
            elif kind == "image" and _get(c, "data"):
                images.append({"type": "image", "source": {"type": "base64", "media_type": _get(c, "mime_type", "mimeType", default="image/png"),
                                                           "data": _get(c, "data")}})
            elif kind == "resource":
                r = _get(c, "resource")
                texts.append(_get(r, "text", default="") if r is not None else "")
        structured = _get(res, "structured_content", "structuredContent")
        if not texts and structured is not None:
            texts.append(json.dumps(structured, ensure_ascii=False)[:8000])
        text = "\n".join(t for t in texts if t)[:8000] or "(no text returned)"
        if _get(res, "is_error", "isError", default=False):
            text = f"The {server} connector reported an error: {text}"
        if images:
            return [{"type": "text", "text": text}] + images[:3]
        return text

    def status(self):
        return [{"name": n, "status": s["status"], "tools": len(s["tools"]), "error": s["error"]} for n, s in self.servers.items()]

    def summary(self):
        if not self.servers:
            return "No connectors set up. Add them to mcp.json in your Jarvis documents folder."
        ok = [n for n, s in self.servers.items() if s["status"] == "connected"]
        bad = [n for n, s in self.servers.items() if s["status"] != "connected"]
        out = f"Connected to {len(ok)} connector{'s' if len(ok) != 1 else ''}" + (f": {', '.join(ok)}" if ok else "")
        if bad:
            out += f". Couldn't connect to {', '.join(bad)}; the log in Documents, Jarvis, logs says why"
        return out + "."


EXAMPLE = {
    "mcpServers": {
        "notes-folder": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:\\Users\\YOU\\Documents\\Notes"],
            "disabled": True,
        },
        "a-remote-app": {"url": "https://example.com/mcp", "headers": {"Authorization": "Bearer YOUR_TOKEN"}, "disabled": True},
    }
}


def ensure_file():
    """Create mcp.json with switched-off examples, so there's something to copy from."""
    if not FILE.exists():
        FILE.parent.mkdir(parents=True, exist_ok=True)
        FILE.write_text(json.dumps(EXAMPLE, indent=2), encoding="utf-8")
    return FILE
