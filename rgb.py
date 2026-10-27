"""
RGB lighting through the software already on the PC: "make my lights red", "turn my keyboard blue",
"RGB off", "rainbow", "brightness 40", "put it back to normal".

Each program has its own way in, and each needs one setting switched on (status() says which):
  * OpenRGB    (most brands)        OpenRGB > SDK Server tab > Start Server. Colors, modes, saved profiles.
  * SignalRGB                        Nothing to switch on. Effects, presets, brightness, on/off. It can't be told an
                                     exact color from outside, so for a color it picks a matching effect or preset.
  * Corsair iCUE                     iCUE > Settings > General: "Enable SDK" (third-party control).
  * Razer Synapse / Chroma           Chroma Connect / "Chroma Apps" allowed in Synapse (on by default).
  * Logitech G HUB                   G HUB > Settings: "Allow games & applications to control my lighting".

For iCUE, Razer and G HUB a color Jarvis sets lasts while he's running; "put my lighting back" (or quitting him)
hands control back and their own lighting returns. OpenRGB and SignalRGB keep what you set.
"Auto" uses every one that's running, so a PC with several brands changes everything at once.
"""
import ctypes
import json
import re
import socket
import sys
import threading
import time

BRANDS = ("openrgb", "signalrgb", "icue", "razer", "logitech")
LABEL = {"openrgb": "OpenRGB", "signalrgb": "SignalRGB", "icue": "Corsair iCUE", "razer": "Razer Chroma",
         "logitech": "Logitech G HUB"}
ALIASES = {"corsair": "icue", "icue": "icue", "cue": "icue", "razer": "razer", "chroma": "razer", "synapse": "razer",
           "logitech": "logitech", "ghub": "logitech", "g hub": "logitech", "lghub": "logitech", "openrgb": "openrgb",
           "open rgb": "openrgb", "signal": "signalrgb", "signalrgb": "signalrgb", "signal rgb": "signalrgb"}
DEVICES = {   # what people say -> the kinds of device each program knows
    "keyboard": {"razer": ["keyboard", "keypad"], "icue": ["Keyboard"], "openrgb": ["KEYBOARD"], "logitech": "rgb"},
    "mouse": {"razer": ["mouse"], "icue": ["Mouse"], "openrgb": ["MOUSE"], "logitech": "rgb"},
    "headset": {"razer": ["headset"], "icue": ["Headset", "HeadsetStand"], "openrgb": ["HEADSET", "HEADSET_STAND"], "logitech": "rgb"},
    "mousepad": {"razer": ["mousepad"], "icue": ["Mousemat"], "openrgb": ["MOUSEMAT"], "logitech": "rgb"},
    "pc": {"razer": ["chromalink"], "icue": ["FanLedController", "LedController", "MemoryModule", "Cooler", "Motherboard",
                                             "GraphicsCard"],
           "openrgb": ["MOTHERBOARD", "DRAM", "GPU", "COOLER", "LEDSTRIP", "CASE"], "logitech": None},
    "fans": {"icue": ["FanLedController", "Cooler"], "openrgb": ["COOLER"], "razer": ["chromalink"], "logitech": None},
    "ram": {"icue": ["MemoryModule"], "openrgb": ["DRAM"], "razer": [], "logitech": None},
}
DEVICE_WORDS = {"keyboards": "keyboard", "keys": "keyboard", "mice": "mouse", "headphones": "headset",
                "mousemat": "mousepad", "mouse pad": "mousepad", "case": "pc", "tower": "pc", "computer": "pc",
                "fan": "fans", "memory": "ram", "everything": "all", "all": "all", "lights": "all", "": "all"}

COLORS = {
    "red": (255, 0, 0), "crimson": (220, 20, 60), "dark red": (139, 0, 0), "orange": (255, 110, 0),
    "amber": (255, 170, 0), "yellow": (255, 220, 0), "gold": (255, 180, 0), "lime": (140, 255, 0),
    "green": (0, 255, 0), "dark green": (0, 120, 0), "mint": (60, 255, 160), "teal": (0, 200, 170),
    "cyan": (0, 255, 255), "turquoise": (64, 224, 208), "light blue": (90, 180, 255), "sky blue": (90, 180, 255),
    "blue": (0, 60, 255), "navy": (0, 0, 140), "dark blue": (0, 0, 160), "indigo": (75, 0, 200),
    "purple": (150, 0, 255), "violet": (170, 60, 255), "magenta": (255, 0, 255), "pink": (255, 60, 160),
    "hot pink": (255, 20, 147), "rose": (255, 80, 120), "white": (255, 255, 255), "warm white": (255, 190, 120),
    "cool white": (200, 220, 255), "black": (0, 0, 0), "off": (0, 0, 0),
}


def parse_color(text):
    """'red', '#ff0000', 'ff0000', 'rgb(255, 0, 0)', '255 0 0' -> (r, g, b) or None."""
    t = str(text or "").strip().lower()
    if t in COLORS:
        return COLORS[t]
    m = re.fullmatch(r"#?([0-9a-f]{6})", t)
    if m:
        h = m.group(1)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = re.fullmatch(r"(?:rgb)?\(?\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*\)?", t)
    if m:
        return tuple(max(0, min(255, int(x))) for x in m.groups())
    t2 = re.sub(r"\b(light|lights|colou?r|rgb|my|the|to)\b", " ", t).strip()
    t2 = re.sub(r"\s+", " ", t2)
    return COLORS.get(t2)


def _scale(rgb, brightness):
    if brightness is None:
        return rgb
    f = max(0, min(100, float(brightness))) / 100
    return tuple(int(round(c * f)) for c in rgb)


def _port_open(port, host="127.0.0.1", timeout=0.4):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _procs():
    try:
        import psutil
        return {(p.info["name"] or "").lower() for p in psutil.process_iter(["name"])}
    except Exception:
        return set()


def _http(method, url, body=None, timeout=4):
    import requests
    return requests.request(method, url, json=body, timeout=timeout)


# ============================================================ OpenRGB
class OpenRGB:
    name = "openrgb"
    PORT = 6742

    def __init__(self):
        self.cli = None

    def present(self, procs):
        return "openrgb.exe" in procs or _port_open(self.PORT)

    def _client(self):
        if self.cli is None:
            from openrgb import OpenRGBClient
            self.cli = OpenRGBClient("127.0.0.1", self.PORT, "Jarvis")
        return self.cli

    def setup_hint(self):
        return "In OpenRGB, open the SDK Server tab and click Start Server (tick 'Start at launch' in Settings to keep it on)."

    def ready(self):
        if not _port_open(self.PORT):
            return False, "OpenRGB is open but its SDK server is off. " + self.setup_hint()
        try:
            import openrgb  # noqa: F401
        except ImportError:
            return False, "the openrgb-python package isn't installed (pip install openrgb-python)."
        return True, ""

    def _devices(self, kind):
        cli = self._client()
        try:
            cli.update()
        except Exception:
            pass
        devs = list(cli.devices)
        if kind == "all":
            return devs
        want = set(DEVICES.get(kind, {}).get("openrgb") or [])
        return [d for d in devs if getattr(getattr(d, "type", None), "name", "") in want]

    def color(self, rgb, kind):
        from openrgb.utils import RGBColor
        devs = self._devices(kind)
        if not devs:
            return 0
        c = RGBColor(*rgb)
        for d in devs:
            for mode in ("direct", "static"):
                try:
                    d.set_mode(mode)
                    break
                except Exception:
                    continue
            d.set_color(c)
        return len(devs)

    def effect(self, name):
        cli = self._client()
        profiles = [getattr(p, "name", str(p)) for p in getattr(cli, "profiles", [])]
        hit = _best(name, profiles)
        if hit:
            cli.load_profile(hit)
            return f"loaded the OpenRGB profile '{hit}'"
        changed = []
        for d in self._devices("all"):
            modes = [m.name for m in getattr(d, "modes", [])]
            m = _best(name, modes)
            if m:
                try:
                    d.set_mode(m)
                    changed.append(d.name)
                except Exception:
                    pass
        if changed:
            return f"set {', '.join(changed[:4])} to their '{name}' mode"
        return None

    def effects(self):
        cli = self._client()
        profiles = [getattr(p, "name", str(p)) for p in getattr(cli, "profiles", [])]
        modes = sorted({m.name for d in self._devices("all") for m in getattr(d, "modes", [])})
        return (("profiles: " + ", ".join(profiles) + "; ") if profiles else "") + "modes: " + ", ".join(modes[:30])

    def devices(self):
        return [f"{d.name} ({getattr(getattr(d, 'type', None), 'name', '?').lower()})" for d in self._devices("all")]

    def release(self):
        return False                                  # OpenRGB keeps what's set; there's nothing to hand back


# ============================================================ SignalRGB
class SignalRGB:
    name = "signalrgb"
    BASE = "http://127.0.0.1:16038/api/v1"

    def present(self, procs):
        return "signalrgb.exe" in procs or "signalrgblauncher.exe" in procs or _port_open(16038)

    def setup_hint(self):
        return "SignalRGB needs to be open (its local API is on by default)."

    def ready(self):
        try:
            r = _http("GET", self.BASE + "/lighting", timeout=2)
            return r.ok, "" if r.ok else f"SignalRGB answered with an error ({r.status_code})."
        except Exception:
            return False, "SignalRGB is installed but its API didn't answer. Make sure SignalRGB is open."

    def _effects(self):
        r = _http("GET", self.BASE + "/lighting/effects", timeout=8)
        items = (r.json().get("data") or {}).get("items") or []
        return [(i.get("id"), (i.get("attributes") or {}).get("name") or i.get("id")) for i in items]

    def _apply(self, eid):
        for path in (f"/lighting/effects/{eid}/apply", f"/lighting/effect/{eid}/apply"):   # the docs use both
            r = _http("POST", self.BASE + path, timeout=6)
            if r.ok:
                return True
        return False

    def effect(self, name):
        effs = self._effects()
        hit = _best(name, [n for _, n in effs])
        if not hit:
            return None
        eid = next(i for i, n in effs if n == hit)
        return f"applied the SignalRGB effect '{hit}'" if self._apply(eid) else None

    def color(self, rgb, kind, color_name=""):
        """SignalRGB can't be given an exact color; look for an effect or a preset named after it."""
        if not color_name:
            return None
        effs = self._effects()
        for eid, n in effs:
            try:
                r = _http("GET", f"{self.BASE}/lighting/effects/{eid}/presets", timeout=4)
                if not r.ok:
                    r = _http("GET", f"{self.BASE}/lighting/effect/{eid}/presets", timeout=4)
                presets = [p.get("id") for p in ((r.json().get("data") or {}).get("items") or [])]
            except Exception:
                presets = []
            p = _best(color_name, presets, cutoff=0.85)
            if p and re.search(r"solid|static|color|colour", n, re.I):
                self._apply(eid)
                _http("PATCH", f"{self.BASE}/lighting/effects/{eid}/presets", {"preset": p}, timeout=4)
                return f"applied your '{p}' preset of {n}"
        hit = _best(color_name, [n for _, n in effs], cutoff=0.85)
        if hit:
            eid = next(i for i, n in effs if n == hit)
            if self._apply(eid):
                return f"applied the '{hit}' effect"
        return None

    def brightness(self, value):
        r = _http("PATCH", self.BASE + "/lighting/global_brightness", {"global_brightness": int(value)})
        return r.ok

    def enabled(self, on):
        r = _http("PATCH", self.BASE + "/lighting/enabled", {"enabled": bool(on)})
        return r.ok

    def step(self, which):
        r = _http("POST", self.BASE + {"next": "/lighting/next", "previous": "/lighting/previous",
                                       "random": "/lighting/shuffle"}[which])
        try:
            return ((r.json().get("data") or {}).get("attributes") or {}).get("name") or "the next effect"
        except Exception:
            return "the next effect" if r.ok else None

    def effects(self):
        return ", ".join(n for _, n in self._effects()[:60])

    def current(self):
        try:
            a = ((_http("GET", self.BASE + "/lighting", timeout=2).json().get("data") or {}).get("attributes") or {})
            return f"'{a.get('name')}' at {a.get('global_brightness')}% brightness" + ("" if a.get("enabled", True) else " (lights off)")
        except Exception:
            return ""

    def release(self):
        return False


# ============================================================ Razer Chroma (REST)
class Razer:
    name = "razer"
    BASE = "http://localhost:54235/razer/chromasdk"
    KINDS = ["keyboard", "mouse", "headset", "mousepad", "keypad", "chromalink"]

    def __init__(self):
        self.uri = None
        self.beat = None
        self.stop = threading.Event()

    def present(self, procs):
        return any(p.startswith(("razer", "rzsdk", "rzchroma")) for p in procs) or _port_open(54235, "127.0.0.1", 0.3)

    def setup_hint(self):
        return "In Razer Synapse, make sure Chroma Apps / Chroma Connect is allowed (it is by default)."

    def ready(self):
        try:
            _http("GET", self.BASE, timeout=2)
            return True, ""
        except Exception:
            return False, "Razer's Chroma service didn't answer. Open Synapse and check Chroma Connect is on."

    def _session(self):
        if self.uri:
            return self.uri
        body = {"title": "Jarvis", "description": "Voice control for your lighting",
                "author": {"name": "Jarvis", "contact": "local"}, "device_supported": self.KINDS,
                "category": "application"}
        r = _http("POST", self.BASE, body, timeout=5).json()
        self.uri = r.get("uri")
        if not self.uri:
            raise RuntimeError(f"Chroma refused to start a session ({r.get('result')})")
        time.sleep(1.0)                                # Chroma needs a moment before the first command lands
        self.stop.clear()
        self.beat = threading.Thread(target=self._heartbeat, daemon=True, name="chroma-heartbeat")
        self.beat.start()
        return self.uri

    def _heartbeat(self):
        while not self.stop.wait(2.0):                 # the session dies after 15 s without a command
            try:
                _http("PUT", self.uri + "/heartbeat", timeout=3)
            except Exception:
                pass

    def color(self, rgb, kind):
        uri = self._session()
        kinds = self.KINDS if kind == "all" else (DEVICES.get(kind, {}).get("razer") or [])
        bgr = rgb[0] | (rgb[1] << 8) | (rgb[2] << 16)  # Chroma wants 0x00BBGGRR
        n = 0
        for k in kinds:
            try:
                body = {"effect": "CHROMA_NONE"} if rgb == (0, 0, 0) else {"effect": "CHROMA_STATIC", "param": {"color": bgr}}
                r = _http("PUT", f"{uri}/{k}", body, timeout=4)
                if r.ok and (r.json().get("result", 0) == 0):
                    n += 1
            except Exception:
                continue
        return n

    def release(self):
        if not self.uri:
            return False
        self.stop.set()
        try:
            _http("DELETE", self.uri, timeout=4)
        except Exception:
            pass
        self.uri = None
        return True


# ============================================================ Corsair iCUE (iCUE SDK v4, cuesdk package)
class ICue:
    name = "icue"

    def __init__(self):
        self.sdk = None
        self.state = None
        self.controlled = set()

    def present(self, procs):
        return "icue.exe" in procs or "corsair.service.exe" in procs

    def setup_hint(self):
        return "In iCUE: Settings > General, turn on 'Enable SDK' (third-party control)."

    def ready(self):
        try:
            import cuesdk  # noqa: F401
        except ImportError:
            return False, "the cuesdk package isn't installed (pip install cuesdk)."
        return True, ""

    def _connect(self):
        if self.sdk is not None and self._connected():
            return self.sdk
        from cuesdk import CueSdk
        self.sdk = CueSdk()

        def changed(evt):
            self.state = getattr(evt, "state", None)
        err = self.sdk.connect(changed)
        end = time.time() + 5
        while time.time() < end and not self._connected():
            time.sleep(0.1)
        if not self._connected():
            raise RuntimeError("iCUE didn't accept the connection. " + self.setup_hint())
        return self.sdk

    def _connected(self):
        return str(self.state).lower().endswith("connected")          # CorsairSessionState.CSS_Connected

    def _devices(self, kind):
        from cuesdk import CorsairDeviceFilter, CorsairDeviceType
        sdk = self._connect()
        mask = getattr(CorsairDeviceType, "CDT_All", 0xFFFFFFFF)
        devs, err = sdk.get_devices(CorsairDeviceFilter(device_type_mask=mask))
        devs = devs or []
        if kind == "all":
            return devs
        want = {w.lower() for w in (DEVICES.get(kind, {}).get("icue") or [])}
        out = []
        for d in devs:
            t = str(getattr(d, "type", "")).lower()
            if any(w.lower() in t for w in want):
                out.append(d)
        return out

    def color(self, rgb, kind):
        from cuesdk import CorsairLedColor
        sdk = self._connect()
        n = 0
        for d in self._devices(kind):
            did = d.device_id
            if did not in self.controlled:
                try:
                    from cuesdk import CorsairAccessLevel
                    sdk.request_control(did, CorsairAccessLevel.CAL_ExclusiveLightingControl)
                    self.controlled.add(did)
                except Exception:
                    pass                               # shared control still works, iCUE may just blend
            leds, err = sdk.get_led_positions(did)
            if not leds:
                continue
            sdk.set_led_colors(did, [CorsairLedColor(id=l.id, r=rgb[0], g=rgb[1], b=rgb[2], a=255) for l in leds])
            n += 1
        return n

    def devices(self):
        return [f"{getattr(d, 'model', '?')} ({str(getattr(d, 'type', '')).split('.')[-1].replace('CDT_', '').lower()})"
                for d in self._devices("all")]

    def release(self):
        if self.sdk is None:
            return False
        for did in list(self.controlled):
            try:
                self.sdk.release_control(did)
            except Exception:
                pass
        self.controlled.clear()
        try:
            self.sdk.disconnect()
        except Exception:
            pass
        self.sdk, self.state = None, None
        return True


# ============================================================ Logitech G HUB (LED SDK through G HUB's own DLL)
class Logitech:
    name = "logitech"
    CLSID = "{a6519e67-7632-4375-afdf-caa889744403}"     # the LED SDK G HUB (and old LGS) registers
    TARGET_ALL, TARGET_RGB = 0x7, 0x6                    # monochrome | rgb | per-key rgb

    def __init__(self):
        self.dll = None

    def present(self, procs):
        return "lghub.exe" in procs or "lghub_agent.exe" in procs or "lcore.exe" in procs

    def setup_hint(self):
        return "In G HUB: Settings, turn on 'Allow games & applications to control my lighting'."

    def _dll_path(self):
        import os
        try:
            import winreg
            for hive, key in ((winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Classes\CLSID\{self.CLSID}\ServerBinary"),
                              (winreg.HKEY_CLASSES_ROOT, rf"CLSID\{self.CLSID}\ServerBinary"),
                              (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Classes\WOW6432Node\CLSID\{self.CLSID}\ServerBinary")):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        p = winreg.QueryValueEx(k, "")[0]
                        if p and os.path.exists(p):
                            return p
                except OSError:
                    continue
        except ImportError:
            pass
        pf = os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles", r"C:\Program Files")
        for p in (rf"{pf}\LGHUB\sdk_legacy_led_x64.dll", rf"{pf}\Logitech Gaming Software\SDK\LED\x64\LogitechLed.dll"):
            if os.path.exists(p):
                return p
        return None

    def ready(self):
        if sys.platform != "win32":
            return False, "Windows only."
        return (True, "") if self._dll_path() else (False, "couldn't find G HUB's lighting SDK. Update G HUB.")

    def _init(self):
        if self.dll is not None:
            return self.dll
        dll = ctypes.cdll.LoadLibrary(self._dll_path())
        ok = False
        for fn, args in (("LogiLedInitWithName", (ctypes.c_char_p(b"Jarvis"),)), ("LogiLedInit", ())):
            f = getattr(dll, fn, None)
            if f is not None:
                ok = bool(f(*args))
                if ok:
                    break
        if not ok:
            raise RuntimeError("G HUB didn't let me in. " + self.setup_hint())
        time.sleep(0.4)
        if hasattr(dll, "LogiLedSaveCurrentLighting"):
            dll.LogiLedSaveCurrentLighting()
        self.dll = dll
        return dll

    def color(self, rgb, kind):
        if kind not in ("all", "keyboard", "mouse", "headset", "mousepad"):
            return 0
        dll = self._init()
        if hasattr(dll, "LogiLedSetTargetDevice"):
            dll.LogiLedSetTargetDevice(self.TARGET_ALL)
        pct = [int(round(c * 100 / 255)) for c in rgb]  # the LED SDK takes 0-100, not 0-255
        return 1 if dll.LogiLedSetLighting(*pct) else 0

    def release(self):
        if self.dll is None:
            return False
        try:
            if hasattr(self.dll, "LogiLedRestoreLighting"):
                self.dll.LogiLedRestoreLighting()
            self.dll.LogiLedShutdown()
        except Exception:
            pass
        self.dll = None
        return True


def _best(word, options, cutoff=0.6):
    import difflib
    w = str(word or "").strip().lower()
    opts = [o for o in options if o]
    low = {o.lower(): o for o in opts}
    if w in low:
        return low[w]
    contains = sorted((o for o in opts if w and w in o.lower()), key=len)
    if contains:
        return contains[0]
    m = difflib.get_close_matches(w, list(low), n=1, cutoff=cutoff)
    return low[m[0]] if m else None


# ============================================================ the tool
_B = {"openrgb": OpenRGB(), "signalrgb": SignalRGB(), "razer": Razer(), "icue": ICue(), "logitech": Logitech()}
_LOCK = threading.Lock()


def _pick(software):
    """The programs to use: the one asked for, or every one that's running."""
    procs = _procs()
    s = ALIASES.get(str(software or "auto").strip().lower())
    names = [s] if s else [n for n in BRANDS if _B[n].present(procs)]
    return names, procs


def _kind(device):
    d = str(device or "").strip().lower()
    d = DEVICE_WORDS.get(d, d)
    return d if d in DEVICES or d == "all" else "all"


def status():
    names, procs = _pick("auto")
    if not names:
        return ("No RGB software is running. I work with OpenRGB, SignalRGB, Corsair iCUE, Razer Synapse and Logitech "
                "G HUB; open the one you use.")
    lines = []
    for n in names:
        ok, why = _B[n].ready()
        extra = ""
        if ok and n == "signalrgb":
            extra = " Playing " + _B[n].current() + "." if _B[n].current() else ""
        lines.append(f"{LABEL[n]}: " + ("ready." + extra if ok else why))
    return " ".join(lines)


def control(action, color=None, device="all", software="auto", value=None, effect=None):
    a = (action or "").lower()
    with _LOCK:
        names, procs = _pick(software)
        if a == "status":
            return status()
        if not names:
            asked = ALIASES.get(str(software or "").lower())
            return (f"{LABEL[asked]} isn't running. Open it and ask again." if asked else
                    "No RGB software is running (OpenRGB, SignalRGB, iCUE, Synapse or G HUB). Open the one you use.")
        kind = _kind(device)
        done, problems = [], []

        def each(fn):
            for n in names:
                b = _B[n]
                ok, why = b.ready()
                if not ok:
                    problems.append(f"{LABEL[n]}: {why}")
                    continue
                try:
                    r = fn(n, b)
                except Exception as e:
                    msg = str(e) or type(e).__name__
                    problems.append(f"{LABEL[n]}: {msg[:160]}" + ("" if "setting" in msg.lower() else f" ({b.setup_hint()})"))
                    continue
                if r:
                    done.append(f"{LABEL[n]} {r}" if isinstance(r, str) else LABEL[n])

        if a in ("color", "off"):
            rgb = (0, 0, 0) if a == "off" else parse_color(color)
            if rgb is None:
                return f"I don't know the color '{color}'. Say a name (red, purple, warm white) or a hex like #ff8800."
            rgb = _scale(rgb, value) if a == "color" and value not in (None, "") else rgb

            def go(n, b):
                if n == "signalrgb":
                    if a == "off":
                        return "turned off" if b.enabled(False) else None
                    b.enabled(True)
                    r = b.color(rgb, kind, str(color or ""))
                    if r is None:
                        problems.append("SignalRGB: it can't be told an exact color from outside. Make a preset of its "
                                        f"Solid Color effect named '{color}' and I'll use that, or pick one of its effects.")
                    return r
                cnt = b.color(rgb, kind)
                if not cnt:
                    return None
                return f"({cnt} device{'s' if cnt != 1 else ''})" if n in ("openrgb", "icue") else True
            each(go)
            what = "off" if a == "off" else (color or "that color")
            if done:
                held = [d for d in done if d.startswith((LABEL["icue"], LABEL["razer"], LABEL["logitech"]))]
                tail = (" (iCUE/Razer/G HUB lighting stays like this while I'm running; 'put my lighting back' returns "
                        "control)" if held and a != "off" else "")
                out = f"Lights {'turned ' if a == 'off' else 'set to '}{what}{'' if kind == 'all' else ' on the ' + kind}: " \
                      + "; ".join(done) + "." + tail
            else:
                out = "Nothing changed."
            return out + (" Problems: " + " ".join(problems) if problems else "")

        if a == "on":
            def go(n, b):
                if n == "signalrgb":
                    return "back on" if b.enabled(True) else None
                return "handed back" if b.release() else None
            each(go)
            return ("Lights on: " + "; ".join(done) + "." if done else "They're already on.") + \
                (" Problems: " + " ".join(problems) if problems else "")

        if a == "brightness":
            if value in (None, ""):
                return "What brightness, 0 to 100?"
            v = max(0, min(100, int(float(value))))

            def go(n, b):
                if n == "signalrgb":
                    return f"at {v}%" if b.brightness(v) else None
                problems.append(f"{LABEL[n]}: brightness only works with a color here; say e.g. 'blue at {v} percent'.")
                return None
            each(go)
            return ("Brightness: " + "; ".join(done) + "." if done else "Couldn't change brightness.") + \
                (" " + " ".join(problems) if problems else "")

        if a in ("effect", "next", "previous", "random"):
            def go(n, b):
                if a == "effect":
                    if not hasattr(b, "effect"):
                        return None
                    return b.effect(effect or color or "")
                if n != "signalrgb":
                    return None
                name = b.step(a)
                return f"switched to '{name}'" if name else None
            each(go)
            if done:
                return "; ".join(done) + "."
            have = [LABEL[n] for n in names if n in ("signalrgb", "openrgb")]
            if not have:
                return ("Effects need SignalRGB or OpenRGB. iCUE, Razer and G HUB only take a solid color from outside; "
                        "their own effects are picked in their apps.")
            return f"Couldn't find an effect called '{effect}'. Ask for the list of effects." + \
                (" " + " ".join(problems) if problems else "")

        if a == "effects":
            parts = []
            for n in names:
                b = _B[n]
                if hasattr(b, "effects") and b.ready()[0]:
                    try:
                        parts.append(f"{LABEL[n]}: {b.effects()}")
                    except Exception as e:
                        parts.append(f"{LABEL[n]}: couldn't list ({type(e).__name__})")
            return " | ".join(parts) or "Only SignalRGB and OpenRGB have effects I can switch between."

        if a == "devices":
            parts = []
            for n in names:
                b = _B[n]
                if hasattr(b, "devices") and b.ready()[0]:
                    try:
                        parts.append(f"{LABEL[n]}: " + ", ".join(b.devices()))
                    except Exception as e:
                        parts.append(f"{LABEL[n]}: couldn't list ({type(e).__name__})")
                else:
                    parts.append(f"{LABEL[n]}: running")
            return " | ".join(parts)

        if a in ("reset", "release", "normal"):
            for n in names:
                if _B[n].release():
                    done.append(LABEL[n])
            return ("Handed lighting back to " + ", ".join(done) + "; their own lighting is back." if done
                    else "I wasn't controlling any lighting, so nothing to hand back.")
        return "Unknown action."


def release_all():
    """When Jarvis quits: give every program its lighting back."""
    for b in _B.values():
        try:
            b.release()
        except Exception:
            pass
