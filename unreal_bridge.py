"""
Talking to the user's open Unreal Editor, so the Unreal expert can actually do things in it.

Main route: Unreal's own "Python remote execution" (the same thing Epic's Send to Unreal add-on for Blender uses).
One-time setup in Unreal, per project:
  Edit > Plugins: "Python Editor Script Plugin" ticked (restart the editor if it asks).
  Edit > Project Settings > Plugins > Python: tick "Enable Remote Execution".
How it works: a "ping" goes out on the local multicast group 239.0.0.1:6766, each open editor answers with its
project name and engine version, then the editor connects back to us over TCP on this PC and runs the Python
we send, returning what it printed. Nothing leaves this computer (multicast TTL 0).

Fallback: the Remote Control web API (Remote Control API plugin, http://127.0.0.1:30010), if that's what's on.

Everything the expert runs is wrapped in an editor transaction, so Ctrl+Z in Unreal undoes it.
"""
import json
import re
import socket
import struct
import time
import uuid

MCAST_GROUP = "239.0.0.1"
MCAST_PORT = 6766
HTTP_URL = "http://127.0.0.1:30010"
NODE_ID = str(uuid.uuid4())
SETUP = ("Unreal isn't reachable. In Unreal: Edit > Plugins, make sure 'Python Editor Script Plugin' is ticked; then "
         "Edit > Project Settings > Plugins > Python, tick 'Enable Remote Execution' (restart the editor if asked). "
         "The editor has to be open with a project loaded.")
MARK = "@@JARVIS@@"


def _msg(kind, dest=None, data=None):
    m = {"version": 1, "magic": "ue_py", "type": kind, "source": NODE_ID}
    if dest:
        m["dest"] = dest
    if data is not None:
        m["data"] = data
    return json.dumps(m).encode("utf-8")


def _udp():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except OSError:
            pass
    s.bind(("0.0.0.0", MCAST_PORT))
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 0)          # never leaves this PC
    # Unreal listens on 127.0.0.1 by default (Project Settings > Python > Multicast Bind Address)
    try:
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton("127.0.0.1"))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                     socket.inet_aton(MCAST_GROUP) + socket.inet_aton("127.0.0.1"))
    except OSError:
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                     struct.pack("4sl", socket.inet_aton(MCAST_GROUP), socket.INADDR_ANY))
    s.settimeout(0.1)
    return s


def _recv_json(sock):
    try:
        data, _ = sock.recvfrom(65535)
        return json.loads(data.decode("utf-8"))
    except (socket.timeout, BlockingIOError, ValueError, UnicodeDecodeError, OSError):
        return None


def find(timeout=1.2):
    """Open Unreal editors with remote execution on: [{node_id, project_name, engine_version, project_root...}]."""
    try:
        s = _udp()
    except OSError:
        return []
    found = {}
    try:
        s.sendto(_msg("ping"), (MCAST_GROUP, MCAST_PORT))
        end = time.time() + timeout
        while time.time() < end:
            m = _recv_json(s)
            if not m or m.get("magic") != "ue_py" or m.get("type") != "pong":
                continue
            if m.get("dest") not in (None, NODE_ID):
                continue
            d = dict(m.get("data") or {})
            d["node_id"] = m.get("source")
            found[d["node_id"]] = d
    finally:
        s.close()
    return list(found.values())


def _remote_run(node, code, exec_mode="ExecuteFile", timeout=120):
    """Run code in that editor over the command connection. Returns {"success", "result", "output": [text...]}."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    srv.settimeout(6)
    port = srv.getsockname()[1]
    udp = _udp()
    conn = None
    try:
        udp.sendto(_msg("open_connection", node, {"command_ip": "127.0.0.1", "command_port": port}),
                   (MCAST_GROUP, MCAST_PORT))
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            raise RuntimeError("Unreal answered but didn't open the command connection. Check a firewall isn't "
                               "blocking Unreal on this PC.")
        conn.settimeout(timeout)
        conn.sendall(_msg("command", node, {"command": code, "unattended": True, "exec_mode": exec_mode}))
        buf = b""
        end = time.time() + timeout
        while time.time() < end:
            try:
                chunk = conn.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
            try:
                m = json.loads(buf.decode("utf-8"))
            except ValueError:
                continue
            if m.get("type") == "command_result":
                d = m.get("data") or {}
                out = [o.get("output", "") if isinstance(o, dict) else str(o) for o in (d.get("output") or [])]
                return {"success": bool(d.get("success")), "result": d.get("result"), "output": out}
        raise RuntimeError(f"Unreal didn't answer within {timeout} seconds (it may be busy compiling or a dialog is open).")
    finally:
        try:
            udp.sendto(_msg("close_connection", node), (MCAST_GROUP, MCAST_PORT))
        except OSError:
            pass
        udp.close()
        if conn:
            conn.close()
        srv.close()


def _http_info():
    try:
        import requests
        r = requests.get(HTTP_URL + "/remote/info", timeout=1.5)
        return r.ok
    except Exception:
        return False


def _http_run(code, timeout=120):
    import requests
    body = {"objectPath": "/Script/PythonScriptPlugin.Default__PythonScriptLibrary",
            "functionName": "ExecutePythonCommandEx",
            "parameters": {"PythonCommand": code, "ExecutionMode": "ExecuteFile", "FileExecutionScope": "Public"}}
    r = requests.put(HTTP_URL + "/remote/object/call", json=body, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"Unreal's Remote Control refused ({r.status_code}): {r.text[:200]}. Remote execution "
                           "(Project Settings > Plugins > Python) is the more reliable way in.")
    d = r.json()
    out = [o.get("Output", "") for o in (d.get("LogOutput") or []) if isinstance(o, dict)]
    return {"success": bool(d.get("ReturnValue", True)), "result": d.get("CommandResult"), "output": out}


def status():
    """(editor info or None, how) where how is 'remote', 'http' or the setup sentence."""
    eds = find()
    if eds:
        return eds[0], "remote"
    if _http_info():
        return {"project_name": "?", "engine_version": "?"}, "http"
    return None, SETUP


def _wrap(code, undo_name="Jarvis"):
    """Put the expert's code inside an undoable editor transaction and report errors clearly."""
    return (
        "import unreal, traceback, json\n"
        "_jarvis_ok = True\n"
        "try:\n"
        f"    with unreal.ScopedEditorTransaction({undo_name!r}):\n"
        f"        exec(compile({code!r}, '<jarvis>', 'exec'), globals())\n"
        "except Exception:\n"
        "    _jarvis_ok = False\n"
        f"    print({MARK!r} + 'ERROR ' + traceback.format_exc()[-1500:])\n"
        f"print({MARK!r} + ('OK' if _jarvis_ok else 'FAILED'))\n")


def run(code, undoable=True, timeout=120):
    """Run Python in the open editor. Returns (ok, text) with what it printed (and the error if it failed)."""
    ed, how = status()
    if ed is None:
        return False, how
    src = _wrap(code) if undoable else code
    if how == "remote":
        res = _remote_run(ed["node_id"], src, timeout=timeout)
    else:
        res = _http_run(src, timeout=timeout)
    lines = [str(x).rstrip() for x in res.get("output") or [] if str(x).strip()]
    failed = (not res.get("success")) or any(MARK + "FAILED" in x or MARK + "ERROR" in x for x in lines)
    clean = [x.replace(MARK + "ERROR ", "Error: ") for x in lines if x.strip() not in (MARK + "OK", MARK + "FAILED")]
    text = "\n".join(clean).strip()
    if res.get("result") not in (None, "", "None") and not undoable:
        text = (text + "\n" if text else "") + f"Result: {res['result']}"
    return (not failed), (text[-6000:] or ("Done (it printed nothing)." if not failed else "It failed without saying why."))


LOOKUP_CODE = r'''
import unreal, inspect
_name = {name!r}
_parts = _name.replace("unreal.", "", 1).split(".")
_obj = unreal
for _p in _parts:
    _obj = getattr(_obj, _p, None)
    if _obj is None:
        break
if _obj is None:
    _hits = [n for n in dir(unreal) if _parts[0].lower() in n.lower()][:40]
    print("No unreal." + ".".join(_parts) + " in this engine version. Similar names: " + ", ".join(_hits))
else:
    _doc = (inspect.getdoc(_obj) or "").strip()
    print("unreal." + ".".join(_parts) + ":")
    print(_doc[:{doc_chars}])
    if inspect.isclass(_obj):
        _members = [m for m in dir(_obj) if not m.startswith("_")]
        print("\nMembers (" + str(len(_members)) + "): " + ", ".join(_members[:250]))
print("Engine " + unreal.SystemLibrary.get_engine_version())
'''


def lookup(name, doc_chars=2500):
    """The real API for THIS engine version: docs and members of unreal.<name>."""
    if not re.fullmatch(r"[A-Za-z_][\w.]{0,120}", name or ""):
        return "Give a name like EditorActorSubsystem or EditorAssetLibrary.save_asset."
    ok, text = run(LOOKUP_CODE.format(name=name, doc_chars=int(doc_chars)), undoable=False, timeout=30)
    return text


def project_log(lines=60):
    """The end of the open project's log (compile errors, Python errors, warnings)."""
    import os
    ed, how = status()
    if ed is None:
        return how
    root = ed.get("project_root") or ""
    name = ed.get("project_name") or ""
    path = os.path.join(root, "Saved", "Logs", f"{name}.log") if root and name else ""
    if not path or not os.path.exists(path):
        return "Couldn't find the project's log file."
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        tail = f.readlines()[-max(10, min(int(lines), 300)):]
    keep = [l.rstrip() for l in tail if re.search(r"(Error|Warning|LogPython|LogBlueprint|LogCompile)", l)] or \
        [l.rstrip() for l in tail[-20:]]
    return "\n".join(keep)[-6000:]
