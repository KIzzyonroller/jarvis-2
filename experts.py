"""
Expert modes: Blender and Unreal, each on ITS OWN AI key.

Locked until a key is added (first-run card, the Studio panel, or Settings). While locked, Jarvis can still chat
about Blender or Unreal, but he can't drive either editor. Once unlocked, Jarvis hands the job to the expert
(blender_expert / unreal_expert tools). The expert runs on that mode's key, so its spending is on that key's bill,
and it works in the editor itself:

  * it checks the real API of the version the user has open (live lookup inside the editor), instead of
    guessing from memory, which is where AI usually goes wrong with Blender and Unreal (renamed functions);
  * it runs code in the editor, looks at the result (render / screenshot / log) and fixes problems;
  * anything that saves, deletes, imports or reaches outside the editor asks the user first. In Unreal everything
    it does is one undo step (Ctrl+Z).

Keys: Claude (sk-ant-), OpenRouter (sk-or-) or OpenAI (sk-); providers.py works out which.
"""
import ast
import os
import re

import providers

MODES = {
    "blender": {"name": "Blender", "key": "BLENDER_AI_KEY", "model": "BLENDER_AI_MODEL"},
    "unreal": {"name": "Unreal", "key": "UNREAL_AI_KEY", "model": "UNREAL_AI_MODEL"},
}
LIVE_KEYS = {m[k] for m in MODES.values() for k in ("key", "model")}     # take effect without a restart
_LAST_MODEL = {}


def key(mode):
    v = (os.environ.get(MODES[mode]["key"]) or "").strip()
    return v if providers.detect(v) else ""


def model_setting(mode):
    return (os.environ.get(MODES[mode]["model"]) or "").strip()


def unlocked(mode):
    return bool(key(mode))


def locked_note(mode):
    n = MODES[mode]["name"]
    return (f"{n} mode is locked: it runs on its own AI key, and none is set. The user can add one in the Studio panel "
            f"(the cube button at the top of the window) or in Settings > {n} mode: a Claude, OpenRouter or OpenAI key.")


# ============================================================ Blender expert
BLENDER_LOOKUP = r'''
import bpy, bmesh, mathutils, inspect, difflib
_n = {name!r}
_parts = _n.split(".")
_roots = {{"bpy": bpy, "bmesh": bmesh, "mathutils": mathutils}}
_o = _roots.get(_parts[0])
_rest = _parts[1:]
if _o is None:
    _o, _rest = getattr(bpy.types, _parts[0], None), _parts[1:]
_parent = None
for _p in _rest:
    _parent = _o
    _o = getattr(_o, _p, None) if _o is not None else None
print(_n + "  (Blender " + bpy.app.version_string + ")")
_rna = None
if _o is not None and hasattr(_o, "get_rna_type"):
    try:
        _rna = _o.get_rna_type()
    except Exception:
        _o = None                                   # bpy.ops makes up a wrapper for any name; this one doesn't exist
def _similar(pool, word):
    return difflib.get_close_matches(word, pool, n=8, cutoff=0.5) or [x for x in pool if word[:4].lower() in x.lower()][:12]
if _o is None:
    _pool = [x for x in dir(_parent) if not x.startswith("_")] if _parent is not None else dir(bpy.types)
    print("Not found in this version. Similar: " + ", ".join(_similar(_pool, _parts[-1])))
elif _rna is not None:
    print(_rna.description)
    for _pr in _rna.properties:
        if _pr.identifier == "rna_type":
            continue
        _d = getattr(_pr, "default", "")
        _e = [i.identifier for i in getattr(_pr, "enum_items", [])][:12]
        print("  " + _pr.identifier + ": " + _pr.type.lower() + (" = " + repr(_d) if _d not in ("", None) else "")
              + (" one of " + "/".join(_e) if _e else "") + "  " + (_pr.description or "")[:80])
elif hasattr(_o, "bl_rna"):
    _r = _o.bl_rna
    _inherited = {{p.identifier for p in getattr(_r.base, "properties", [])}} if _r.base else set()
    print(_r.description + (" (a kind of " + _r.base.identifier + ")" if _r.base else ""))
    for _pr in _r.properties:
        if _pr.identifier == "rna_type" or _pr.identifier in _inherited:
            continue
        _e = [i.identifier for i in getattr(_pr, "enum_items", [])][:10]
        print("  " + _pr.identifier + ": " + _pr.type.lower() + (" one of " + "/".join(_e) if _e else "")
              + "  " + (_pr.description or "")[:70])
    _f = [f.identifier for f in _r.functions]
    if _f:
        print("Functions: " + ", ".join(_f)[:400])
else:
    print((inspect.getdoc(_o) or "")[:1200])
    if inspect.ismodule(_o) or inspect.isclass(_o):
        print("Members: " + ", ".join(m for m in dir(_o) if not m.startswith("_"))[:700])
'''


def blender_lookup(name):
    """The real Blender API for the version the user has: an operator's options, a type's properties..."""
    import tools
    if not re.fullmatch(r"[A-Za-z_][\w.]{0,120}", name or ""):
        return "Give a name like bpy.ops.mesh.bevel, Object, bpy.types.BevelModifier or bmesh.ops.extrude_face_region."
    code = BLENDER_LOOKUP.format(name=name)
    res = tools._bl_send({"cmd": "run", "code": code}, timeout=30)
    if res is None:
        out = tools._bl_background([{"cmd": "run", "code": code}], timeout=90)
        if out == "NO_BLENDER":
            return "Blender isn't installed, so I can't look up its API. Go by memory and say so."
        res = out[0]
    if not res.get("ok"):
        return "Lookup failed: " + (res.get("error") or "")
    return (res.get("output") or "").strip()[-2000:] or "Nothing printed."


BLENDER_PROMPT = """You are the Blender expert inside Jarvis, a voice assistant. Jarvis handed you a job; do it in the user's
Blender with the tools, then reply with a short, plain summary Jarvis can say out loud (a sentence or two: what you
made or changed, sizes if relevant, anything you couldn't do). No markdown.

How to work:
- Start with blender status (and scene if the job builds on what's there).
- When you're not certain of an operator's options or a property name in THIS Blender version, use blender_lookup
  first (e.g. bpy.ops.mesh.bevel, BevelModifier, bmesh.ops.bevel). APIs change between versions; don't guess.
- Build in steps, LOOK at each render, and fix problems (proportions, gaps, floating or intersecting parts) before
  you finish. Real-world size in meters, Z up, objects sit on z=0 when they stand on something.
- Prefer modifiers and bmesh over long vertex lists. Clear names, materials with a base color so renders show it.
- Don't read or write files in code; use save/export. Anything that touches files or Blender's settings asks
  the user first (that's fine, but don't do it unless the job needs it).
- Detailed organic sculpts (faces, characters) aren't realistic this way: say so rather than faking it."""


# ============================================================ Unreal expert
_UE_SAFE_IMPORTS = {"unreal", "math", "random", "json", "re", "itertools", "collections", "colorsys", "string",
                    "statistics", "functools"}
_UE_RISKY_ATTRS = {"delete_asset", "delete_directory", "delete_loaded_asset", "delete_loaded_assets", "save_asset",
                   "save_directory", "save_loaded_asset", "save_loaded_assets", "save_packages", "save_current_level",
                   "save_dirty_packages", "save_map", "save_all_dirty_levels", "rename_asset", "rename_directory",
                   "rename_assets", "consolidate_assets", "import_asset_tasks", "import_assets_automated",
                   "execute_console_command", "quit_editor", "close_editor", "new_level", "load_level", "load_map",
                   "export_assets", "export_asset", "run_asset_export_task", "execute_python_command",
                   "set_project_settings", "delete_actors"}


def unreal_risk(code):
    """(syntax error or None, [reasons to ask first]). A tripwire, not a sandbox."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"Syntax error on line {e.lineno}: {e.msg}", []
    why = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            why |= {f"imports {a.name}" for a in n.names if a.name.split(".")[0] not in _UE_SAFE_IMPORTS}
        elif isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] not in _UE_SAFE_IMPORTS:
            why.add(f"imports {n.module}")
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in (
                "open", "exec", "eval", "compile", "__import__", "globals", "setattr", "delattr", "breakpoint"):
            why.add(f"calls {n.func.id}()")
        elif isinstance(n, ast.Attribute):
            if n.attr in _UE_RISKY_ATTRS:
                why.add(f"uses .{n.attr}")
            elif n.attr.startswith("__"):
                why.add(f"touches {n.attr}")
        elif isinstance(n, ast.Name) and n.id in ("os", "sys", "subprocess", "shutil", "ctypes", "socket", "pathlib"):
            why.add(f"uses {n.id}")
    return None, sorted(why)


def unreal_python(code, what=""):
    import tools
    import unreal_bridge
    if not (code or "").strip():
        return "Give the Python to run."
    syntax, why = unreal_risk(code)
    if syntax:
        return f"Didn't run it. {syntax}"
    if why and not tools._confirm(f"Run Unreal code{': ' + what if what else ''}",
                                  "It " + ", ".join(why) + ".\n\n" + code[:900], "unreal"):
        return tools.DENIED
    try:
        ok, text = unreal_bridge.run(code)
    except Exception as e:
        return f"Couldn't talk to Unreal: {type(e).__name__}: {e}"
    return ("Ran it (one undo step in Unreal).\n" if ok else "It failed (nothing to undo past the error).\n") + text


def unreal_status():
    import unreal_bridge
    ed, how = unreal_bridge.status()
    if ed is None:
        return how
    if how == "http":
        return "Connected to Unreal through Remote Control (project and version unknown that way)."
    return (f"Connected to Unreal {ed.get('engine_version', '?')}, project {ed.get('project_name', '?')} "
            f"({ed.get('project_root', '')}).")


def unreal_look(question=""):
    import tools
    return tools.look_at_screen(question or "What's in the Unreal Editor viewport?", "Unreal Editor", "high")


UNREAL_PROMPT = """You are the Unreal Engine expert inside Jarvis, a voice assistant. Jarvis handed you a job; do it in the
user's open Unreal Editor with the tools, then reply with a short, plain summary Jarvis can say out loud (a sentence or
two: what you did, anything you couldn't). No markdown.

How to work:
- Start with unreal_status. If Unreal isn't reachable, stop and say what to switch on (the tool tells you).
- The editor's Python API changes between engine versions. Before using a class or function you're not certain of,
  check it with unreal_lookup (e.g. EditorActorSubsystem, EditorAssetLibrary, StaticMeshActor). Prefer editor
  subsystems: unreal.get_editor_subsystem(unreal.EditorActorSubsystem), LevelEditorSubsystem, UnrealEditorSubsystem,
  and EditorAssetLibrary for assets. Units are centimeters, Z is up.
- unreal_python runs your code inside one undo step; print() what you need to know. Keep each run small and check
  the result (the printout, unreal_log for errors, unreal_look to see the viewport) before the next.
- Don't save, delete, rename or import unless the job asks; those ask the user first anyway.
- Blueprint graphs can't really be built from Python: for Blueprint logic, explain the nodes to add instead. For C++,
  write the code in your reply (Jarvis will show it); you can't compile it from here.
- If something needs a plugin or setting that's off, say exactly which one."""


# ============================================================ specs for each expert
def _s(name, desc, props=None, req=None):
    return {"name": name, "description": desc, "input_schema": {"type": "object", "properties": props or {},
                                                                 "required": req or []}}


def _blender_specs():
    import tools
    base = next(s for s in tools.TOOL_SPECS if s["name"] == "blender")
    return [base, _s("blender_lookup", "Look up the exact Blender Python API for the user's Blender version: an operator "
                     "(bpy.ops.mesh.bevel), a type (Object, BevelModifier) or bmesh.ops function. Shows its options/properties.",
                     {"name": {"type": "string"}}, ["name"])]


def _unreal_specs():
    S = {"type": "string"}
    return [
        _s("unreal_status", "Is the user's Unreal Editor reachable? Which project and engine version."),
        _s("unreal_python", "Run Python in the user's open Unreal Editor (import unreal is done). One undo step. "
                            "print() results. Saving/deleting/importing/console commands ask the user first.",
           {"code": S, "what": {"type": "string", "description": "a few words on what it does, for the approval card"}},
           ["code"]),
        _s("unreal_lookup", "The real Unreal Python API in the user's engine version: docs and members of a class or "
                            "function, e.g. EditorActorSubsystem or EditorAssetLibrary.save_asset.",
           {"name": S}, ["name"]),
        _s("unreal_log", "The end of the project's log: errors and warnings (Python, Blueprint, compile).",
           {"lines": {"type": "number"}}),
        _s("unreal_look", "Screenshot of the Unreal Editor window, to check the result visually.", {"question": S}),
    ]


def _run_tool_for(mode):
    import tools
    import unreal_bridge
    if mode == "blender":
        fns = {"blender": tools.blender, "blender_lookup": blender_lookup}
    else:
        fns = {"unreal_status": unreal_status, "unreal_python": unreal_python, "unreal_lookup": unreal_bridge.lookup,
               "unreal_log": unreal_bridge.project_log, "unreal_look": unreal_look}

    def run(name, args):
        fn = fns.get(name)
        if fn is None:
            return f"Unknown tool {name}."
        out = fn(**(args or {}))
        return out if isinstance(out, list) else str(out)
    return run


def _context(mode):
    """A line about the editor the expert will work in, so it knows the version from the start."""
    try:
        if mode == "blender":
            import tools
            res = tools._bl_send({"cmd": "scene"}, timeout=5)
            if res:
                return f"The user's Blender {res.get('blender', '')} is open with the Jarvis Bridge add-on (live)."
            exe = tools._blender_exe()
            return f"Blender isn't open live; it builds in the background with {exe}." if exe else "Blender isn't installed."
        return unreal_status()
    except Exception as e:
        return f"(couldn't check the editor: {type(e).__name__})"


def run(mode, task):
    """What Jarvis's blender_expert / unreal_expert tools call."""
    import tools
    import usage
    if mode not in MODES:
        return "Unknown mode."
    if not unlocked(mode):
        return locked_note(mode)
    name = MODES[mode]["name"]
    if not (task or "").strip():
        return f"What should the {name} expert do?"
    try:
        ag = providers.agent(key(mode), model_setting(mode))
    except Exception as e:
        return f"The {name} key couldn't be used: {e}"
    _LAST_MODEL[mode] = ag.model
    system = (BLENDER_PROMPT if mode == "blender" else UNREAL_PROMPT) + "\n\nRight now: " + _context(mode)
    specs = _blender_specs() if mode == "blender" else _unreal_specs()
    on_event = getattr(tools._CTX, "on_event", None)
    cancel = getattr(tools._CTX, "cancel", None)
    print(f"[expert] {name} on {providers.LABEL[ag.provider]} {ag.model}: {task[:80]!r}")
    try:
        text = ag.run(system, task, specs, _run_tool_for(mode), on_event=on_event, cancel=cancel)
    except providers.Stopped:
        return "Stopped."
    except Exception as e:
        msg = str(e)
        if type(e).__name__ in ("AuthenticationError", "PermissionDeniedError") or "401" in msg:
            return f"The {name} key was refused by {providers.LABEL[ag.provider]}. Check it in the Studio panel."
        if "credit" in msg.lower() or "balance" in msg.lower() or "402" in msg:
            return f"The {name} key is out of credit on {providers.LABEL[ag.provider]}."
        return f"The {name} expert hit a problem: {type(e).__name__}: {msg[:300]}"
    finally:
        try:
            usage.record_mode(mode, ag.usage)
        except Exception as e:
            print(f"[expert] couldn't record usage: {e}")
    return f"[{name} expert] " + (text or "Done.")


# ============================================================ for the Studio panel
def editor_status(mode):
    try:
        if mode == "blender":
            import tools
            res = tools._bl_send({"cmd": "ping"}, timeout=3)
            if res is not None:
                return {"ok": True, "text": "Connected live to your Blender"}
            exe = tools._blender_exe()
            if exe:
                return {"ok": True, "text": "Installed. Builds in the background until you install the add-on",
                        "action": "install_addon"}
            return {"ok": False, "text": "Blender isn't installed (free at blender.org)"}
        import unreal_bridge
        ed, how = unreal_bridge.status()
        if ed is None:
            return {"ok": False, "text": "Unreal isn't open, or remote execution is off", "setup": True}
        if how == "http":
            return {"ok": True, "text": "Connected through Remote Control"}
        return {"ok": True, "text": f"Connected: {ed.get('project_name', '?')}, Unreal {ed.get('engine_version', '?')}"}
    except Exception as e:
        return {"ok": False, "text": f"Couldn't check ({type(e).__name__})"}


def view(probe=False):
    """What the Studio panel shows. Never includes a key, just which service and its last 4 characters."""
    import usage
    out = []
    for mode, m in MODES.items():
        k = key(mode)
        p = providers.detect(k) if k else None
        row = {"mode": mode, "name": m["name"], "unlocked": bool(k)}
        if k:
            row.update(provider=providers.LABEL[p], hint=k[-4:], model=model_setting(mode) or _LAST_MODEL.get(mode) or "",
                       model_auto=not model_setting(mode))
            try:
                row["today"] = usage.mode_today(mode)
            except Exception:
                row["today"] = None
        if probe:
            row["editor"] = editor_status(mode)
        out.append(row)
    return out
