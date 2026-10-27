"""
Meshy (meshy.ai): text or a picture -> a detailed 3D model. It's the key that unlocks Blender mode.

The Blender expert uses it for what code can't build well: creatures, characters, statues, figurines, detailed
props. It sends the request, waits (usually 1 to 3 minutes), downloads the model and brings it into Blender, where
the expert scales it to the size asked for, stands it on the floor, checks a render and fixes it up.

Key: meshy.ai/developers/keys (needs Meshy Pro or higher; Meshy only gives API keys on paid plans).
Costs (Meshy's credits): a model is about 20, textures about 10 more; failed jobs are refunded.
API: https://docs.meshy.ai (text-to-3d v2 preview + refine, image-to-3d v1, balance v1).
"""
import base64
import mimetypes
import re
import time
from datetime import datetime
from pathlib import Path

BASE = "https://api.meshy.ai"
SITE = "meshy.ai/developers/keys"
_BAL = {"t": 0.0, "key": None, "v": None}


class MeshyError(Exception):
    pass


def _req(method, path, key, body=None, timeout=30):
    import requests
    r = requests.request(method, BASE + path, json=body, timeout=timeout,
                         headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if r.status_code == 401:
        raise MeshyError(f"Meshy says the key isn't valid. Make a new one at {SITE}.")
    if r.status_code == 402:
        raise MeshyError("Meshy is out of credits on that account (or it's on the free plan, which can't be used "
                         "from other apps). Top up or upgrade at meshy.ai/pricing.")
    if r.status_code == 429:
        raise MeshyError("Meshy is rate-limiting right now; try again in a minute.")
    if r.status_code >= 400:
        try:
            msg = r.json().get("message") or r.text
        except ValueError:
            msg = r.text
        raise MeshyError(f"Meshy refused ({r.status_code}): {str(msg)[:200]}")
    return r.json() if r.content else {}


def looks_valid(key):
    k = (key or "").strip()
    if not k or " " in k or len(k) < 16:
        return f"That doesn't look like a Meshy API key. Copy it from {SITE}."
    if k.startswith(("sk-ant-", "sk-or-", "gsk_")):
        return f"That's an AI chat key, not a Meshy key. Blender mode uses a Meshy key from {SITE}."
    return None


def check(key):
    """(ok, sentence). Asks Meshy for the balance, which is free."""
    try:
        b = balance(key, fresh=True)
        return True, f"Meshy accepted the key ({b['balance']} credits)."
    except MeshyError as e:
        return False, str(e)
    except Exception as e:
        return True, f"Couldn't reach Meshy to check it right now ({type(e).__name__}); saved anyway."


def balance(key, fresh=False):
    """{"balance", "monthly_credits", "permanent_credits", "monthly_resets_at"}, cached a minute."""
    if not fresh and _BAL["key"] == key and time.time() - _BAL["t"] < 60 and _BAL["v"]:
        return _BAL["v"]
    v = _req("GET", "/openapi/v1/balance", key, timeout=10)
    _BAL.update(t=time.time(), key=key, v=v)
    return v


def _wait(path, key, timeout, on_progress=None, cancel=None):
    end = time.time() + timeout
    last = -1
    while time.time() < end:
        if cancel is not None and cancel.is_set():
            raise MeshyError("Stopped.")
        t = _req("GET", path, key)
        st = t.get("status")
        if st == "SUCCEEDED":
            return t
        if st in ("FAILED", "CANCELED"):
            raise MeshyError("Meshy couldn't make it: " + ((t.get("task_error") or {}).get("message") or st.lower())
                             + " (failed jobs are refunded).")
        p = int(t.get("progress") or 0)
        if on_progress and p != last:
            on_progress(p, t.get("preceding_tasks"))
            last = p
        time.sleep(4)
    raise MeshyError(f"Meshy was still working after {int(timeout / 60)} minutes. It may finish on Meshy's site "
                     "(your models are listed there).")


def _image_data(path):
    p = Path(path)
    if not p.is_file():
        raise MeshyError(f"Couldn't find the picture {p}.")
    if p.stat().st_size > 20 * 2**20:
        raise MeshyError("Meshy takes pictures up to 20 MB; that one's bigger.")
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    if mime not in ("image/png", "image/jpeg", "image/webp"):
        raise MeshyError("Meshy takes PNG, JPG or WebP pictures.")
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def generate(key, prompt="", image=None, textured=True, polycount=None, quality="standard",
             on_progress=None, cancel=None):
    """Make the model. Returns {"glb": url, "stl": url, "thumbnail": url, "credits": n, "task": id}."""
    common = {"target_formats": ["glb", "stl"]}
    if polycount:
        common.update(should_remesh=True, target_polycount=max(100, min(300000, int(polycount))))
    used = 0
    if image:
        body = {"image_url": _image_data(image), "should_texture": bool(textured), **common}
        if textured:
            body["enable_pbr"] = True
        if prompt:
            body["texture_prompt"] = prompt[:800]
        tid = _req("POST", "/openapi/v1/image-to-3d", key, body)["result"]
        t = _wait(f"/openapi/v1/image-to-3d/{tid}", key, 600, on_progress, cancel)
        used += int(t.get("consumed_credits") or 0)
    else:
        if not prompt.strip():
            raise MeshyError("What should it make?")
        body = {"mode": "preview", "prompt": prompt[:800], **common}
        if quality in ("2k", "4k"):
            body["geometry_resolution"] = quality
        tid = _req("POST", "/openapi/v2/text-to-3d", key, body)["result"]
        t = _wait(f"/openapi/v2/text-to-3d/{tid}", key, 600,
                  (lambda p, q: on_progress(p // 2 if textured else p, q)) if on_progress else None, cancel)
        used += int(t.get("consumed_credits") or 0)
        if textured:
            rid = _req("POST", "/openapi/v2/text-to-3d", key,
                       {"mode": "refine", "preview_task_id": tid, "enable_pbr": True, "target_formats": ["glb", "stl"]})["result"]
            t = _wait(f"/openapi/v2/text-to-3d/{rid}", key, 600,
                      (lambda p, q: on_progress(50 + p // 2, q)) if on_progress else None, cancel)
            used += int(t.get("consumed_credits") or 0)
            tid = rid
    urls = t.get("model_urls") or {}
    if not urls.get("glb"):
        raise MeshyError("Meshy finished but didn't give back a model file.")
    _BAL["t"] = 0                                   # the balance changed
    return {"glb": urls.get("glb"), "stl": urls.get("stl"), "thumbnail": t.get("thumbnail_url"),
            "credits": used, "task": tid}


def download(url, folder, name):
    import requests
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w\- ]+", "", name or "").strip()[:40] or "model"
    p = folder / f"{safe}-{datetime.now():%Y%m%d-%H%M%S}.glb"
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(p, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    return p
