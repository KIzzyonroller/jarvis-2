"""
Smart lights by voice: Philips Hue (talks to your Hue Bridge on your own network) and Home Assistant (covers almost
any brand: LIFX, Nanoleaf, Govee, Wiz, TP-Link... whatever you've added to it).

  * Hue: say "pair my Hue bridge", press the round button on the bridge, and she saves the key it hands out (encrypted,
    like your other keys). She finds the bridge on your network by herself, or set its address in Settings.
  * Home Assistant: put its address (like http://homeassistant.local:8123) and a long-lived access token (your
    profile page in Home Assistant, at the bottom) in Settings > Connected apps > Smart home.
  * "Her colours": when you switch between Juno, Jarvis and Ultron, the lights you pick change to that AI's colour.

Only lights are controlled (on/off, brightness, colour). No locks, alarms, cameras or anything else.
"""
import os
import re
import threading

import config

PERSONA_RGB = {"juno": (201, 123, 255), "jarvis": (70, 200, 255), "ultron": (255, 48, 70)}
COLORS = {"red": (255, 0, 0), "orange": (255, 120, 0), "yellow": (255, 210, 0), "green": (0, 220, 60),
          "teal": (0, 200, 180), "cyan": (0, 220, 255), "blue": (0, 70, 255), "purple": (140, 40, 255),
          "violet": (170, 80, 255), "pink": (255, 80, 180), "magenta": (255, 0, 200), "white": (255, 255, 255),
          "warm white": (255, 190, 120), "warm": (255, 180, 110), "cool white": (220, 235, 255), "cool": (210, 230, 255)}


def rgb_of(color):
    c = (color or "").strip().lower()
    if c in PERSONA_RGB:
        return PERSONA_RGB[c]
    if c in COLORS:
        return COLORS[c]
    m = re.fullmatch(r"#?([0-9a-f]{6})", c)
    if m:
        h = m.group(1)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return None


def _xy(rgb):
    """sRGB -> Hue's CIE xy."""
    def g(v):
        v /= 255
        return ((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92
    r, gg, b = (g(x) for x in rgb)
    X = r * 0.664511 + gg * 0.154324 + b * 0.162028
    Y = r * 0.283881 + gg * 0.668433 + b * 0.047685
    Z = r * 0.000088 + gg * 0.072310 + b * 0.986039
    s = X + Y + Z
    return [round(X / s, 4), round(Y / s, 4)] if s else [0.3227, 0.329]


def _req(method, url, **kw):
    import requests
    kw.setdefault("timeout", (2, 5))
    if url.startswith("https://") and _is_local(url):
        kw.setdefault("verify", False)                 # the Hue bridge has its own self-signed certificate
        import urllib3
        urllib3.disable_warnings()
    r = requests.request(method, url, **kw)
    r.raise_for_status()
    return r.json() if r.content else None


def _is_local(url):
    host = re.sub(r"^https?://", "", url).split("/")[0].split(":")[0]
    return bool(re.match(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|127\.|169\.254\.)", host)) or host.endswith(".local")


# ------------------------------------------------------------------ Hue
def hue_bridge():
    ip = (config.HUE_BRIDGE or "").strip()
    if ip:
        return ip
    try:
        found = _req("GET", "https://discovery.meethue.com/")
        if found:
            return found[0].get("internalipaddress")
    except Exception as e:
        print(f"[lights] couldn't find a Hue bridge: {e}")
    return None


def _hue(method, path, body=None):
    ip, user = hue_bridge(), config.HUE_USER
    if not ip or not user:
        raise RuntimeError("Hue isn't paired")
    for scheme in ("https", "http"):
        try:
            return _req(method, f"{scheme}://{ip}/api/{user}{path}", json=body)
        except Exception as e:
            last = e
    raise last


def hue_pair():
    """Press the bridge's button, then call this within 30 seconds."""
    ip = hue_bridge()
    if not ip:
        return "I couldn't find a Hue bridge on your network. Put its address in Settings > Connected apps > Smart home."
    out = None
    for scheme in ("https", "http"):
        try:
            out = _req("POST", f"{scheme}://{ip}/api", json={"devicetype": "juno#pc"})
            break
        except Exception:
            continue
    if not out:
        return f"Couldn't reach the Hue bridge at {ip}."
    r = out[0] if isinstance(out, list) and out else {}
    if "success" in r:
        user = r["success"]["username"]
        import settings
        settings.save({"JUNO_HUE_USER": user, "JUNO_HUE_BRIDGE": ip})
        os.environ["JUNO_HUE_USER"], os.environ["JUNO_HUE_BRIDGE"] = user, ip
        config.HUE_USER, config.HUE_BRIDGE = user, ip
        return f"Paired with the Hue bridge at {ip}. Your lights are mine now. Kidding. Mostly."
    if r.get("error", {}).get("type") == 101:
        return "Press the round button on top of the Hue bridge, then ask me to pair again within 30 seconds."
    return f"The bridge said: {r.get('error', {}).get('description', 'something went wrong')}."


def _hue_targets(target):
    """[(kind, id, name)] lights or rooms matching target ('all' = group 0)."""
    t = (target or "all").strip().lower()
    if t in ("all", "everything", "lights", "all lights", "the lights", ""):
        return [("groups", "0", "all lights")]
    out = []
    for kind in ("groups", "lights"):
        for i, v in (_hue("GET", f"/{kind}") or {}).items():
            if t in str(v.get("name", "")).lower():
                out.append((kind, i, v["name"]))
        if out:
            return out
    return out


def _hue_set(target, state):
    hits = _hue_targets(target)
    if not hits:
        return None
    for kind, i, _ in hits:
        _hue("PUT", f"/{kind}/{i}/{'action' if kind == 'groups' else 'state'}", state)
    return [n for _, _, n in hits]


# ------------------------------------------------------------------ Home Assistant
def _ha(method, path, body=None):
    url, tok = (config.HA_URL or "").rstrip("/"), config.HA_TOKEN
    if not url or not tok:
        raise RuntimeError("Home Assistant isn't set up")
    return _req(method, f"{url}/api{path}", json=body, headers={"Authorization": f"Bearer {tok}"})


def _ha_lights(target):
    t = (target or "all").strip().lower()
    states = _ha("GET", "/states") or []
    lights = [s for s in states if s["entity_id"].startswith("light.")]
    if t in ("all", "everything", "lights", "all lights", "the lights", ""):
        return lights
    return [s for s in lights if t in s["entity_id"].lower() or t in str(s.get("attributes", {}).get("friendly_name", "")).lower()]


def _ha_set(target, on=True, bri=None, rgb=None):
    hits = _ha_lights(target)
    if not hits:
        return None
    body = {"entity_id": [s["entity_id"] for s in hits]}
    if on:
        if bri is not None:
            body["brightness_pct"] = int(bri)
        if rgb:
            body["rgb_color"] = list(rgb)
    _ha("POST", f"/services/light/{'turn_on' if on else 'turn_off'}", body)
    return [s.get("attributes", {}).get("friendly_name") or s["entity_id"] for s in hits]


# ------------------------------------------------------------------ one front door for both
def available():
    return {"hue": bool(config.HUE_USER), "ha": bool(config.HA_URL and config.HA_TOKEN)}


def control(action, target="all", value=None, color=None):
    a = (action or "").lower()
    av = available()
    if a == "pair_hue":
        return hue_pair()
    if not (av["hue"] or av["ha"]):
        return ("No smart lights connected yet. For Philips Hue say 'pair my Hue bridge' (and press the bridge's "
                "button). For anything else, connect Home Assistant in Settings > Connected apps > Smart home.")
    if a == "list":
        names = []
        try:
            if av["hue"]:
                names += [f"{v['name']} (Hue room)" for v in (_hue("GET", "/groups") or {}).values()]
                names += [f"{v['name']} (Hue)" for v in (_hue("GET", "/lights") or {}).values()]
            if av["ha"]:
                names += [s.get("attributes", {}).get("friendly_name") or s["entity_id"] for s in _ha_lights("all")]
        except Exception as e:
            return f"Couldn't reach the lights: {e}"
        return "Lights: " + (", ".join(names) if names else "none found")
    rgb = None
    bri = None
    if a == "color":
        rgb = rgb_of(color or value)
        if not rgb:
            return f"I don't know the colour '{color or value}'. Try a name like purple or warm white, or a hex code."
    if a == "brightness":
        try:
            bri = max(1, min(100, int(float(value))))
        except (TypeError, ValueError):
            return "Brightness from 1 to 100."
    on = a != "off"
    if a not in ("on", "off", "color", "brightness"):
        return "action must be on, off, brightness, color, list or pair_hue."
    done = []
    try:
        if av["hue"]:
            st = {"on": on}
            if bri is not None:
                st["bri"] = round(bri / 100 * 254)
            if rgb:
                st["xy"] = _xy(rgb)
            done += _hue_set(target, st) or []
        if av["ha"]:
            done += _ha_set(target, on, bri, rgb) or []
    except Exception as e:
        return f"Couldn't reach the lights: {e}"
    if not done:
        return f"No light or room called '{target}'. Ask me to list the lights."
    what = {"on": "on", "off": "off", "brightness": f"at {bri}%", "color": f"{color or value}"}[a]
    return f"{', '.join(done[:4])}{' and more' if len(done) > 4 else ''}: {what}."


# ------------------------------------------------------------------ her colours follow whoever's talking
_last = {"p": None}


def feed(ev):
    if not config.LIGHTS_SYNC or ev.get("type") != "persona":
        return
    key = ev.get("key")
    if key not in PERSONA_RGB or key == _last["p"]:
        return
    _last["p"] = key
    av = available()
    if not (av["hue"] or av["ha"]):
        return

    def go():
        try:
            control("color", config.LIGHTS_SYNC_TARGET or "all", color=key)
        except Exception as e:
            print(f"[lights] colour sync: {e}")
    threading.Thread(target=go, daemon=True).start()
