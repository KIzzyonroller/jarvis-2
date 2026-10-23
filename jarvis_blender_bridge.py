"""
Jarvis Bridge for Blender.

One file, three jobs:
  * Blender add-on: install it in Blender (Edit > Preferences > Add-ons > Install
    from Disk) and Jarvis / Ultron can build live inside your open Blender. It
    listens on 127.0.0.1 only, so nothing outside your PC can reach it.
  * Background runner: when Blender isn't open, Jarvis runs
        blender -b <file> --python jarvis_blender_bridge.py -- job.json result.json
    and the same code builds, renders and saves without a window.
  * The actual commands (handle()), shared by both.

Everything Jarvis does here is one undo step in live mode, so Ctrl+Z takes it back.
"""
bl_info = {
    "name": "Jarvis Bridge",
    "author": "John Deadlock (Kizzy)",
    "version": (1, 0, 0),
    "blender": (3, 3, 0),
    "location": "View3D > Sidebar > Jarvis",
    "description": "Lets Jarvis and Ultron build models in this Blender session",
    "category": "System",
}

import base64
import contextlib
import io
import json
import math
import os
import queue
import socket
import sys
import tempfile
import threading
import traceback

import bpy

HOST, PORT = "127.0.0.1", 9877
SHAPES = ("MESH", "CURVE", "SURFACE", "META", "FONT", "CURVES", "POINTCLOUD", "VOLUME", "GPENCIL", "GREASEPENCIL")


# =================================================================== helpers
def _view3d():
    """A 3D viewport (window, area, region) if Blender has a window open, for ops that need one."""
    wm = bpy.context.window_manager
    for win in getattr(wm, "windows", []):
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                for region in area.regions:
                    if region.type == "WINDOW":
                        return win, area, region
    return None


@contextlib.contextmanager
def _ctx():
    v = _view3d()
    if v and hasattr(bpy.context, "temp_override"):
        with bpy.context.temp_override(window=v[0], area=v[1], region=v[2]):
            yield
    else:
        yield


def _object_mode():
    try:
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        pass


def _bbox(objs):
    from mathutils import Vector
    pts = []
    for o in objs:
        try:
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
        except Exception:
            pass
    if not pts:
        return None
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def _visible_shapes():
    out = []
    for o in bpy.context.scene.objects:
        if o.type in SHAPES:
            try:
                if not o.visible_get():
                    continue
            except Exception:
                pass
            out.append(o)
    return out


def _cm(v):
    return round(v * bpy.context.scene.unit_settings.scale_length * 100, 1)


def _scene_info(limit=40):
    objs = list(bpy.context.scene.objects)
    rows = []
    for o in objs[:limit]:
        d = o.dimensions
        mats = []
        try:
            mats = [s.material.name for s in o.material_slots if s.material]
        except Exception:
            pass
        rows.append({
            "name": o.name, "type": o.type,
            "size_cm": [_cm(d.x), _cm(d.y), _cm(d.z)],
            "location_cm": [_cm(o.location.x), _cm(o.location.y), _cm(o.location.z)],
            "materials": mats,
            "modifiers": [m.type.lower() for m in getattr(o, "modifiers", [])],
            "verts": len(o.data.vertices) if o.type == "MESH" and o.data else None,
        })
    box = _bbox(_visible_shapes())
    overall = [_cm(box[1].x - box[0].x), _cm(box[1].y - box[0].y), _cm(box[1].z - box[0].z)] if box else None
    return {"objects": rows, "count": len(objs), "overall_size_cm": overall,
            "file": bpy.data.filepath or "(unsaved)", "blender": bpy.app.version_string}


# =================================================================== commands
def cmd_run(job, live):
    import bmesh
    import mathutils
    import random
    code = job.get("code") or ""
    before = {o.name for o in bpy.data.objects}
    if live:
        try:
            bpy.ops.ed.undo_push(message="Jarvis: before build")
        except Exception:
            pass
    _object_mode()
    ns = {"bpy": bpy, "bmesh": bmesh, "math": math, "mathutils": mathutils, "random": random,
          "Vector": mathutils.Vector, "Matrix": mathutils.Matrix, "Euler": mathutils.Euler,
          "C": bpy.context, "D": bpy.data, "__name__": "jarvis_build"}
    out = io.StringIO()
    err = None
    try:
        with contextlib.redirect_stdout(out), _ctx():
            exec(compile(code, "<jarvis>", "exec"), ns)
    except Exception:
        tb = traceback.format_exc().strip().splitlines()
        where = [l.strip() for l in tb if l.strip().startswith('File "<jarvis>"')][-1:]
        err = "; ".join(where + tb[-1:]).replace('File "<jarvis>", ', "")
    try:
        bpy.context.view_layer.update()      # so sizes and positions reflect what the code just did
    except Exception:
        pass
    if live:
        try:
            bpy.ops.ed.undo_push(message="Jarvis: build")
        except Exception:
            pass
    added = sorted({o.name for o in bpy.data.objects} - before)
    return {"ok": err is None, "error": err, "output": out.getvalue()[-2000:], "added": added[:30],
            "scene": _scene_info()}


VIEWS = {
    "iso": (1.0, -1.15, 0.85), "front": (0, -1, 0.0001), "back": (0, 1, 0.0001), "left": (-1, 0, 0.0001),
    "right": (1, 0, 0.0001), "side": (1, 0, 0.0001), "top": (0.0001, -0.0001, 1), "bottom": (0.0001, -0.0001, -1),
    "iso_back": (-1.0, 1.15, 0.85),
}


def cmd_look(job, live):
    """Render the model from an angle with a throwaway camera. The user's own camera,
    engine and output settings are put back afterwards."""
    from mathutils import Vector
    scene = bpy.context.scene
    try:
        bpy.context.view_layer.update()
    except Exception:
        pass
    objs = _visible_shapes()
    name = job.get("object")
    if name:
        objs = [o for o in objs if o.name.lower() == name.lower()] or [o for o in objs if name.lower() in o.name.lower()] or objs
    box = _bbox(objs)
    if not box:
        return {"ok": False, "error": "There's nothing visible in the scene to look at yet."}
    lo, hi = box
    center = (lo + hi) / 2
    size = max((hi - lo).length, 0.001)
    d = Vector(VIEWS.get(job.get("angle") or "iso", VIEWS["iso"])).normalized()

    r = scene.render
    saved = dict(camera=scene.camera, engine=r.engine, x=r.resolution_x, y=r.resolution_y, pct=r.resolution_percentage,
                 path=r.filepath, fmt=r.image_settings.file_format, film=r.film_transparent)
    cam_data = bpy.data.cameras.new("JarvisLookCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = size * 1.45          # render is 4:3, so leave room for the short side
    cam_data.clip_end = size * 50 + 100
    cam = bpy.data.objects.new("JarvisLookCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = center + d * size * 3
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    tmp = os.path.join(tempfile.gettempdir(), "jarvis_blender_look.png")
    try:
        scene.camera = cam
        r.resolution_x, r.resolution_y, r.resolution_percentage = 960, 720, 100
        r.filepath = tmp
        r.image_settings.file_format = "PNG"
        r.film_transparent = False
        err = None
        for engine in ("BLENDER_WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
            try:
                r.engine = engine
            except Exception:
                continue
            try:
                if engine == "BLENDER_WORKBENCH":
                    sh = scene.display.shading
                    sh.light, sh.color_type = "STUDIO", "MATERIAL"
                    sh.show_cavity = True
                    sh.show_object_outline = True
                if engine == "CYCLES":
                    scene.cycles.samples = 12
                    scene.cycles.device = "CPU"
                bpy.ops.render.render(write_still=True)
                err = None
                break
            except Exception as e:
                err = f"{engine}: {e}"
        if err:
            return {"ok": False, "error": "Couldn't render a preview: " + err}
        with open(tmp, "rb") as f:
            png = base64.b64encode(f.read()).decode()
    finally:
        scene.camera = saved["camera"]
        try:
            r.engine = saved["engine"]
        except Exception:
            pass
        r.resolution_x, r.resolution_y, r.resolution_percentage = saved["x"], saved["y"], saved["pct"]
        r.filepath, r.image_settings.file_format, r.film_transparent = saved["path"], saved["fmt"], saved["film"]
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cam_data)
    return {"ok": True, "png": png, "angle": job.get("angle") or "iso",
            "size_cm": [_cm(hi.x - lo.x), _cm(hi.y - lo.y), _cm(hi.z - lo.z)]}


def cmd_clear(job, live):
    if live:
        try:
            bpy.ops.ed.undo_push(message="Jarvis: before clear")
        except Exception:
            pass
    _object_mode()
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.curves, bpy.data.cameras, bpy.data.lights):
        for item in list(coll):
            if item.users == 0:
                coll.remove(item)
    return {"ok": True}


def cmd_save(job, live):
    path = job["path"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # copy=True: in live mode your open file keeps its own name and unsaved state
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=bool(live))
    return {"ok": True, "path": path}


def cmd_export(job, live):
    path, fmt = job["path"], (job.get("format") or "stl").lower()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _object_mode()
    sel = bool(job.get("selected_only"))
    tries = {
        # Blender works in meters; slicers read STL numbers as millimeters, hence x1000
        "stl": [("wm.stl_export", dict(filepath=path, global_scale=1000.0, export_selected_objects=sel, apply_modifiers=True)),
                ("export_mesh.stl", dict(filepath=path, global_scale=1000.0, use_selection=sel, use_mesh_modifiers=True))],
        "obj": [("wm.obj_export", dict(filepath=path, export_selected_objects=sel, apply_modifiers=True)),
                ("export_scene.obj", dict(filepath=path, use_selection=sel))],
        "fbx": [("export_scene.fbx", dict(filepath=path, use_selection=sel))],
        "glb": [("export_scene.gltf", dict(filepath=path, export_format="GLB", use_selection=sel))],
        "gltf": [("export_scene.gltf", dict(filepath=path, export_format="GLTF_SEPARATE", use_selection=sel))],
    }
    if fmt not in tries:
        return {"ok": False, "error": f"Can't export {fmt}. Options: stl, obj, fbx, glb, gltf."}
    errors = []
    for op, kw in tries[fmt]:
        mod, name = op.split(".")
        fn = getattr(getattr(bpy.ops, mod), name, None)
        if fn is None:
            continue
        try:
            with _ctx():
                fn(**kw)
            if os.path.exists(path):
                return {"ok": True, "path": path, "format": fmt}
        except Exception as e:
            errors.append(f"{op}: {e}")
    return {"ok": False, "error": "Export failed. " + " | ".join(errors)[-600:]}


COMMANDS = {
    "ping": lambda job, live: {"ok": True, "blender": bpy.app.version_string, "file": bpy.data.filepath or "(unsaved)"},
    "run": cmd_run, "look": cmd_look, "scene": lambda job, live: {"ok": True, **_scene_info()},
    "clear": cmd_clear, "save": cmd_save, "export": cmd_export,
}


def handle(job, live=False):
    fn = COMMANDS.get(job.get("cmd"))
    if not fn:
        return {"ok": False, "error": f"Unknown command {job.get('cmd')!r}."}
    try:
        return fn(job, live)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-1500:]}


# =================================================================== live server (add-on mode)
class _Server:
    def __init__(self):
        self.q = queue.Queue()
        self.sock = None
        self.running = False
        self.error = None
        self.jobs = 0

    def start(self):
        if self.running:
            return
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, PORT))
            s.listen(4)
        except OSError as e:
            self.error = f"Port {PORT} is busy ({e})"
            print(f"[Jarvis Bridge] {self.error}")
            return
        self.sock, self.running, self.error = s, True, None
        threading.Thread(target=self._accept, daemon=True, name="jarvis-bridge").start()
        if not bpy.app.timers.is_registered(self._pump):
            bpy.app.timers.register(self._pump, first_interval=0.2, persistent=True)
        print(f"[Jarvis Bridge] listening on {HOST}:{PORT}")

    def stop(self):
        self.running = False
        try:
            self.sock and self.sock.close()
        except Exception:
            pass
        if bpy.app.timers.is_registered(self._pump):
            bpy.app.timers.unregister(self._pump)

    def _accept(self):
        while self.running:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(conn,), daemon=True).start()

    def _client(self, conn):
        with conn:
            try:
                f = conn.makefile("rwb")
                job = json.loads(f.readline().decode("utf-8") or "{}")
                box, done = {}, threading.Event()
                self.q.put((job, box, done))          # bpy is only safe on Blender's main thread
                if not done.wait(float(job.get("timeout", 120))):
                    box["result"] = {"ok": False, "error": "Blender was busy for too long (a render or a heavy operation?)."}
                f.write((json.dumps(box["result"]) + "\n").encode("utf-8"))
                f.flush()
            except Exception as e:
                print(f"[Jarvis Bridge] connection error: {e}")

    def _pump(self):
        if not self.running:
            return None
        while True:
            try:
                job, box, done = self.q.get_nowait()
            except queue.Empty:
                break
            box["result"] = handle(job, live=True)
            self.jobs += 1
            done.set()
        return 0.1


_SERVER = _Server()


class JARVIS_PT_panel(bpy.types.Panel):
    bl_label = "Jarvis Bridge"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Jarvis"

    def draw(self, context):
        col = self.layout.column()
        if _SERVER.running:
            col.label(text="Connected and listening", icon="CHECKMARK")
            col.label(text=f"Builds this session: {_SERVER.jobs}")
            col.label(text="Ctrl+Z undoes anything he does")
        else:
            col.label(text=_SERVER.error or "Not running", icon="ERROR")
            col.operator("jarvis.bridge_restart", text="Start")


class JARVIS_OT_restart(bpy.types.Operator):
    bl_idname = "jarvis.bridge_restart"
    bl_label = "Start Jarvis Bridge"

    def execute(self, context):
        _SERVER.start()
        return {"FINISHED"}


def register():
    bpy.utils.register_class(JARVIS_OT_restart)
    bpy.utils.register_class(JARVIS_PT_panel)
    if not bpy.app.background:          # only the Blender window you're using listens, never background runs
        _SERVER.start()


def unregister():
    _SERVER.stop()
    bpy.utils.unregister_class(JARVIS_PT_panel)
    bpy.utils.unregister_class(JARVIS_OT_restart)


# =================================================================== background runner
def _run_job_file():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) < 2:
        print("usage: blender -b [file.blend] --python jarvis_blender_bridge.py -- job.json result.json")
        return
    with open(argv[0], encoding="utf-8") as f:
        job = json.load(f)
    results = []
    if job.get("fresh"):
        cmd_clear({}, False)
    changed = bool(job.get("fresh"))
    for step in job.get("steps", []):
        res = handle(step, live=False)
        results.append(res)
        changed = changed or step.get("cmd") in ("run", "clear")
        if not res.get("ok") and step.get("cmd") == "run":
            break
    if changed and job.get("workspace"):
        os.makedirs(os.path.dirname(job["workspace"]), exist_ok=True)
        try:
            bpy.context.preferences.filepaths.save_version = 0     # no current.blend1 backups piling up
        except Exception:
            pass
        bpy.ops.wm.save_as_mainfile(filepath=job["workspace"])
    with open(argv[1], "w", encoding="utf-8") as f:
        json.dump(results, f)


if __name__ == "__main__":
    _run_job_file()
