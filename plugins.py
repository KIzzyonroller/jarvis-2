"""
Plugins: add your own skills to Jarvis without touching his code.

A plugin is one .py file in Documents\\Jarvis\\plugins. It lists the tools it adds, and Claude can then use them
like any of his own. Example (plugins\\coin_flip.py):

    NAME = "Coin flip"
    ABOUT = "Flips a coin or rolls dice."

    def flip(times: int = 1):
        import random
        return ", ".join(random.choice(["heads", "tails"]) for _ in range(int(times)))

    TOOLS = [
        {"name": "flip", "description": "Flip a coin, `times` times.",
         "params": {"times": "integer"}, "run": flip},
    ]

    def on_start(jarvis):      # optional: runs once when he starts; jarvis.say("...") talks
        pass

Safety, because a plugin is real code that runs on your PC:
  * New plugins are OFF until you turn them on. Turning one on shows an approval card with its file and what it
    says it does.
  * If the file changes after you approved it, it's switched off again until you approve the new version.
  * Only install plugins from people you trust, or ones you've read. Settings > What he knows > Plugins.
  * A plugin that crashes is switched off and reported; it can't take him down with it.
"""
import hashlib
import importlib.util
import json
import threading
import traceback
from pathlib import Path

import config

STATE_FILE = "plugins.json"
LOADED = {}            # file name -> {"name", "about", "tools": [spec names], "module"}
ERRORS = {}
_TYPES = {"string": "string", "str": "string", "integer": "integer", "int": "integer", "number": "number",
          "float": "number", "boolean": "boolean", "bool": "boolean"}
EXAMPLE = '''"""
An example Jarvis plugin. It's OFF until you turn it on in Settings > What he knows > Plugins.
Copy this file to make your own: TOOLS lists what Claude can call. See the README in this folder.
"""
NAME = "Coin flip and dice"
ABOUT = "Flips coins and rolls dice when you ask."


def flip(times=1):
    import random
    times = max(1, min(int(times or 1), 20))
    return ", ".join(random.choice(["heads", "tails"]) for _ in range(times))


def roll(sides=6, count=1):
    import random
    sides, count = max(2, int(sides or 6)), max(1, min(int(count or 1), 20))
    rolls = [random.randint(1, sides) for _ in range(count)]
    return f"{rolls} (total {sum(rolls)})"


TOOLS = [
    {"name": "flip", "description": "Flip a coin. times: how many flips.", "params": {"times": "integer"}, "run": flip},
    {"name": "roll", "description": "Roll dice. sides: faces per die (default 6). count: how many dice.",
     "params": {"sides": "integer", "count": "integer"}, "run": roll},
]
'''
README = """Jarvis plugins
===============

Put a .py file here and turn it on in Jarvis: Settings > What he knows > Plugins.

A plugin needs:
  NAME   a short name
  ABOUT  one line on what it does
  TOOLS  a list of {"name", "description", "params": {param: "string"|"integer"|"number"|"boolean"}, "run": function}
Optional:
  on_start(jarvis)  runs once at start. jarvis.say(text) speaks, jarvis.toast(text) shows a note.

Claude sees each tool as plugin_<file>_<name> and decides when to use it from the description, so write the
description the way you'd explain it to a person.

Plugins are real code with the same access to your PC as Jarvis. Only use ones you trust or have read.
Changing a file switches it off until you approve it again.
"""


def folder():
    d = config.JARVIS_DIR / "plugins"
    d.mkdir(parents=True, exist_ok=True)
    ex = d / "example_coin_flip.py"
    if not (d / "README.txt").exists():
        (d / "README.txt").write_text(README, encoding="utf-8")
        if not ex.exists():
            ex.write_text(EXAMPLE, encoding="utf-8")
    return d


def _state():
    try:
        return json.loads((config.JARVIS_DIR / STATE_FILE).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(s):
    (config.JARVIS_DIR / STATE_FILE).write_text(json.dumps(s, indent=1), encoding="utf-8")


def _hash(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _peek(p):
    """NAME and ABOUT without running the file (read the text), for the approval card and the list."""
    import ast
    try:
        tree = ast.parse(Path(p).read_text(encoding="utf-8"))
    except SyntaxError as e:
        return None, f"has a syntax error on line {e.lineno}"
    vals = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("NAME", "ABOUT") and isinstance(node.value, ast.Constant):
                vals[node.targets[0].id] = str(node.value.value)
    return vals.get("NAME") or Path(p).stem, vals.get("ABOUT") or ""


def listing():
    """[{file, name, about, on, changed, error, tools}] for Settings."""
    st = _state()
    out = []
    for p in sorted(folder().glob("*.py")):
        name, about = _peek(p)
        rec = st.get(p.name, {})
        changed = bool(rec.get("on")) and rec.get("sha") != _hash(p)
        out.append({"file": p.name, "name": name or p.stem, "about": about, "on": bool(rec.get("on")) and not changed,
                    "changed": changed, "error": ERRORS.get(p.name, ""), "tools": LOADED.get(p.name, {}).get("tools", [])})
    return out


def enable(file, confirm):
    p = folder() / Path(file).name
    if not p.exists():
        return f"No plugin called {file}."
    name, about = _peek(p)
    if name is None:
        return f"{file} {about}; fix it first."
    code = p.read_text(encoding="utf-8")
    if not confirm(f"Turn on the plugin \"{name}\"? It's real code that runs with Jarvis's access to your PC",
                   f"{p}\n{about}\n\nFirst lines:\n" + "\n".join(code.splitlines()[:25])):
        return "Left it off."
    st = _state()
    st[p.name] = {"on": True, "sha": _hash(p)}
    _save_state(st)
    return f"Turned on {name}. It loads next time he starts (or say \"reload plugins\")."


def disable(file):
    st = _state()
    rec = st.setdefault(Path(file).name, {})
    rec["on"] = False
    _save_state(st)
    return "Turned it off."


def _schema(params):
    props = {k: {"type": _TYPES.get(str(v).lower(), "string")} for k, v in (params or {}).items()}
    return {"type": "object", "properties": props}


def load(register):
    """Import the approved plugins and hand their tools to register(spec, func). Returns how many tools."""
    st = _state()
    n = 0
    for p in sorted(folder().glob("*.py")):
        rec = st.get(p.name, {})
        if not rec.get("on"):
            continue
        if rec.get("sha") != _hash(p):
            ERRORS[p.name] = "changed since you approved it: approve it again"
            print(f"[plugins] {p.name} changed since it was approved; left off")
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"jarvis_plugin_{p.stem}", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            names = []
            for t in getattr(mod, "TOOLS", []):
                fn = t["run"]
                tname = f"plugin_{p.stem}_{t['name']}"[:64].replace("-", "_").replace(" ", "_")
                register({"name": tname, "description": f"[Plugin: {getattr(mod, 'NAME', p.stem)}] {t['description']}",
                          "input_schema": _schema(t.get("params"))}, _guard(p.name, fn))
                names.append(tname)
                n += 1
            LOADED[p.name] = {"name": getattr(mod, "NAME", p.stem), "about": getattr(mod, "ABOUT", ""), "tools": names,
                              "module": mod}
            ERRORS.pop(p.name, None)
            print(f"[plugins] {p.name}: {len(names)} tool(s)")
        except Exception as e:
            ERRORS[p.name] = f"{type(e).__name__}: {e}"
            print(f"[plugins] {p.name} failed to load: {e}")
    return n


def _guard(file, fn):
    def run(**kw):
        try:
            return fn(**kw)
        except Exception as e:
            ERRORS[file] = f"{type(e).__name__}: {e}"
            traceback.print_exc()
            return f"The plugin {file} failed: {type(e).__name__}: {e}"
    return run


class _Api:
    def __init__(self, core):
        self._core = core

    def say(self, text):
        self._core.events.put(("say", str(text)))

    def toast(self, text):
        self._core.emit({"type": "toast", "text": str(text)})


def start_hooks(core):
    for f, rec in LOADED.items():
        fn = getattr(rec["module"], "on_start", None)
        if callable(fn):
            threading.Thread(target=_safe_start, args=(f, fn, _Api(core)), daemon=True, name=f"plugin-{f}").start()


def _safe_start(f, fn, api):
    try:
        fn(api)
    except Exception as e:
        ERRORS[f] = f"on_start: {type(e).__name__}: {e}"
        print(f"[plugins] {f} on_start failed: {e}")


def tool(action="list", file=None, confirm=None):
    a = (action or "list").lower()
    if a == "enable":
        return enable(file or "", confirm)
    if a == "disable":
        return disable(file or "")
    if a == "folder":
        import os
        os.startfile(str(folder()))
        return "Opened the plugins folder."
    items = listing()
    if not items:
        return "No plugins yet. They go in Documents\\Jarvis\\plugins (there's an example and a README there)."
    return "Plugins: " + "; ".join(f"{i['name']} ({i['file']}): {'on' if i['on'] else 'changed, needs approval' if i['changed'] else 'off'}"
                                    + (f", error: {i['error']}" if i['error'] else "") for i in items)
