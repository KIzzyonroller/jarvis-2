"""
The living desktop: Jarvis, Juno and Ultron become the wallpaper.

How it works (the same trick Wallpaper Engine and Lively use on Windows 10):
  * Explorer draws the wallpaper in a window called WorkerW, underneath the window that holds the desktop icons
    (SHELLDLL_DefView). Sending Progman message 0x052C makes Explorer create that WorkerW if it hasn't yet.
  * Our page (ui/desktop.html, a normal pywebview window) is made a child of that WorkerW and stretched over every
    monitor, so it sits exactly where the wallpaper is: behind the icons and behind every app window.
  * The desktop icons are hidden while he runs (their list view is simply hidden; Explorer itself is untouched)
    and shown again when he quits. If he ever crashes with them hidden, the next start shows them again
    (flags.json remembers), and restarting Explorer always brings them back too.

It never takes focus or clicks: the icon layer sits on top of it and gets every click on the desktop.
It stops drawing while a fullscreen game or video is in front, so it costs nothing while you play.
If Explorer restarts (it re-creates WorkerW), it re-attaches within a couple of seconds.

The window is never hidden, only parked off-screen until it's attached: WebView2 paints black when Windows
Forms thinks its window is invisible (see mini.py).
"""
import atexit
import base64
import io
import json
import sys
import re
import threading
import time

import config

TITLE = "Jarvis Desktop"
PARK = -30000
IS_WINDOWS = sys.platform == "win32"
PASS = {"state", "voice", "persona", "turn_start", "turn_end", "merged", "confirm", "confirm_done", "fps", "music",
        "telemetry", "instant", "briefing", "discord", "cards", "phone_note", "game", "desk_viz",
        "widgets", "w_gpu", "w_np", "w_weather", "w_cal", "w_notes"}           # the w_ ones feed the desktop widgets      # the last four feed the pop-up panels
FLAG = "desk_icons_hidden"

_U = None
_PROCS = []          # keep ctypes callbacks alive


def _flags(key, value=None):
    path = config.JARVIS_DIR / "flags.json"
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    if value is None:
        return d.get(key)
    d[key] = value
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(d), encoding="utf-8")
    except OSError:
        pass


def _u():
    """user32 with real 64-bit handle types (its own instance so nobody else's argtypes clash)."""
    global _U
    if _U is None:
        import ctypes
        from ctypes import wintypes as wt
        u = ctypes.WinDLL("user32")
        H, P = wt.HWND, ctypes.POINTER
        sig = {
            "FindWindowW": ([wt.LPCWSTR, wt.LPCWSTR], H),
            "FindWindowExW": ([H, H, wt.LPCWSTR, wt.LPCWSTR], H),
            "SendMessageTimeoutW": ([H, wt.UINT, wt.WPARAM, wt.LPARAM, wt.UINT, wt.UINT, P(ctypes.c_size_t)], ctypes.c_ssize_t),
            "SetParent": ([H, H], H),
            "PostMessageW": ([H, wt.UINT, wt.WPARAM, wt.LPARAM], wt.BOOL),
            "GetParent": ([H], H),
            "GetAncestor": ([H, wt.UINT], H),
            "GetDesktopWindow": ([], H),
            "ArrangeIconicWindows": ([H], wt.UINT),
            "SystemParametersInfoW": ([wt.UINT, wt.UINT, ctypes.c_void_p, wt.UINT], wt.BOOL),
            "IsWindow": ([H], wt.BOOL),
            "IsIconic": ([H], wt.BOOL),
            "ShowWindow": ([H, ctypes.c_int], wt.BOOL),
            "IsWindowVisible": ([H], wt.BOOL),
            "SetWindowPos": ([H, H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT], wt.BOOL),
            "GetWindowRect": ([H, P(wt.RECT)], wt.BOOL),
            "GetForegroundWindow": ([], H),
            "GetClassNameW": ([H, wt.LPWSTR, ctypes.c_int], ctypes.c_int),
            "MonitorFromWindow": ([H, wt.DWORD], wt.HMONITOR),
            "GetMonitorInfoW": ([wt.HMONITOR, ctypes.c_void_p], wt.BOOL),
            "RedrawWindow": ([H, ctypes.c_void_p, ctypes.c_void_p, wt.UINT], wt.BOOL),
            "GetSystemMetrics": ([ctypes.c_int], ctypes.c_int),
            "GetWindowLongPtrW": ([H, ctypes.c_int], ctypes.c_ssize_t),
            "SetWindowLongPtrW": ([H, ctypes.c_int, ctypes.c_ssize_t], ctypes.c_ssize_t),
        }
        for name, (args, res) in sig.items():
            f = getattr(u, name)
            f.argtypes, f.restype = args, res
        _U = u
    return _U


def _monitor_struct():
    import ctypes
    from ctypes import wintypes as wt

    class MI(ctypes.Structure):
        _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]
    return MI


def virtual_rect():
    u = _u()
    return u.GetSystemMetrics(76), u.GetSystemMetrics(77), u.GetSystemMetrics(78), u.GetSystemMetrics(79)


def monitors():
    """Every monitor as fractions of the whole desktop (what the page needs to lay itself out)."""
    import ctypes
    from ctypes import wintypes as wt
    MI = _monitor_struct()
    out = []
    vx, vy, vw, vh = virtual_rect()

    def cb(hmon, hdc, rect, lp):
        mi = MI()
        mi.cbSize = ctypes.sizeof(MI)
        if _u().GetMonitorInfoW(hmon, ctypes.byref(mi)):
            m, w = mi.rcMonitor, mi.rcWork
            out.append({"x": (m.left - vx) / vw, "y": (m.top - vy) / vh, "w": (m.right - m.left) / vw, "h": (m.bottom - m.top) / vh,
                        "wx": (w.left - vx) / vw, "wy": (w.top - vy) / vh, "ww": (w.right - w.left) / vw, "wh": (w.bottom - w.top) / vh,
                        "primary": bool(mi.dwFlags & 1)})
        return True
    proto = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC, ctypes.POINTER(wt.RECT), wt.LPARAM)
    fn = proto(cb)
    ctypes.windll.user32.EnumDisplayMonitors(None, None, fn, 0)
    return out


def _class(h):
    import ctypes
    buf = ctypes.create_unicode_buffer(64)
    _u().GetClassNameW(h, buf, 64)
    return buf.value


def find_wallpaper_layer():
    """(WorkerW to draw in, the icon view) or (None, None)."""
    import ctypes
    from ctypes import wintypes as wt
    u = _u()
    progman = u.FindWindowW("Progman", None)
    if not progman:
        return None, None
    res = ctypes.c_size_t()
    u.SendMessageTimeoutW(progman, 0x052C, 0xD, 0x1, 0, 1000, ctypes.byref(res))     # ask Explorer for a WorkerW
    u.SendMessageTimeoutW(progman, 0x052C, 0, 0, 0, 1000, ctypes.byref(res))
    found = {"w": None, "dv": None}

    def cb(h, lp):
        dv = u.FindWindowExW(h, None, "SHELLDLL_DefView", None)
        if dv:
            found["dv"] = dv
            found["w"] = u.FindWindowExW(None, h, "WorkerW", None)    # the WorkerW right after the icons' one
        return True
    proto = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    fn = proto(cb)
    ctypes.windll.user32.EnumWindows(fn, 0)
    w = found["w"] or u.FindWindowExW(progman, None, "WorkerW", None)     # newer Windows 11 keeps it inside Progman
    return w, found["dv"]


def _icons(defview, show):
    u = _u()
    lv = u.FindWindowExW(defview, None, "SysListView32", None) if defview else None
    if lv:
        u.ShowWindow(lv, 5 if show else 0)
        _flags(FLAG, not show)
    return bool(lv)


_MINMETRICS = None


def _hide_minimized_strips(hide):
    """Windows draws minimized windows that have no taskbar button as little title bars in the bottom-left
    corner (NVIDIA's overlay leaves one there). While they're the desktop, park those off-screen instead.
    Only for this session (never saved), and put back exactly as it was when he closes."""
    global _MINMETRICS
    import ctypes
    from ctypes import wintypes as wt

    class MM(ctypes.Structure):
        _fields_ = [("cbSize", wt.UINT), ("iWidth", ctypes.c_int), ("iHorzGap", ctypes.c_int), ("iVertGap", ctypes.c_int), ("iArrange", ctypes.c_int)]
    u = _u()
    try:
        if hide:
            if _MINMETRICS is None:
                cur = MM(); cur.cbSize = ctypes.sizeof(MM)
                if not u.SystemParametersInfoW(0x002B, ctypes.sizeof(MM), ctypes.byref(cur), 0):   # SPI_GETMINIMIZEDMETRICS
                    return
                _MINMETRICS = (cur.iWidth, cur.iHorzGap, cur.iVertGap, cur.iArrange)
            new = MM(ctypes.sizeof(MM), _MINMETRICS[0], _MINMETRICS[1], _MINMETRICS[2], _MINMETRICS[3] | 8)   # ARW_HIDE
            u.SystemParametersInfoW(0x002C, ctypes.sizeof(MM), ctypes.byref(new), 0)               # 0 = this session only
        elif _MINMETRICS is not None:
            old = MM(ctypes.sizeof(MM), *_MINMETRICS)
            u.SystemParametersInfoW(0x002C, ctypes.sizeof(MM), ctypes.byref(old), 0)
            _MINMETRICS = None
        u.ArrangeIconicWindows(u.GetDesktopWindow())
    except Exception as e:
        print(f"[desktop] minimized windows: {e}")


def recover_icons():
    """At startup: if a previous run hid the icons and never put them back (crash, power cut), show them."""
    if not IS_WINDOWS or not _flags(FLAG):
        return
    try:
        _, dv = find_wallpaper_layer()
        _icons(dv, True)
        print("[desktop] put your desktop icons back (they were left hidden last time)")
    except Exception as e:
        print(f"[desktop] couldn't restore the icons: {e}")


def _fullscreen_in_front():
    """A game or video covering a whole monitor (then the wallpaper can't be seen, so stop drawing it)."""
    import ctypes
    from ctypes import wintypes as wt
    u = _u()
    fg = u.GetForegroundWindow()
    if not fg or _class(fg) in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"):
        return False
    r = wt.RECT()
    if not u.GetWindowRect(fg, ctypes.byref(r)):
        return False
    MI = _monitor_struct()
    mi = MI()
    mi.cbSize = ctypes.sizeof(MI)
    if not u.GetMonitorInfoW(u.MonitorFromWindow(fg, 2), ctypes.byref(mi)):
        return False
    m = mi.rcMonitor
    return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom


def _short(v, n):
    if isinstance(v, str):
        return v if len(v) <= n else v[:n] + "..."
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    return None                                  # lists, dicts: the panels don't need them


def _panel_activity(ev):
    """What the desktop's pop-up panels need from a step she takes, kept small (no screenshots, short results)."""
    kind, d = ev.get("kind"), ev.get("data")
    if kind == "thinking":
        return {"type": "activity", "kind": "thinking", "data": str(d or "")[:400]}
    if kind not in ("tool_pending", "tool_start", "tool_done"):
        return None
    d = d or {}
    args = {k: _short(v, 300) for k, v in (d.get("args") or {}).items() if _short(v, 300) is not None} if isinstance(d.get("args"), dict) else {}
    out = {"name": d.get("name", ""), "args": args}
    if kind == "tool_done":
        out["ok"] = d.get("ok", True)
        out["result"] = str(d.get("result") or "")[:800]
    return {"type": "activity", "kind": kind, "data": out}


class LiveDesk:
    def __init__(self, emitter_cls, core=None):
        self.em = emitter_cls()
        self.core = core
        self.window = None
        self.hwnd = 0
        self.layer = None
        self.defview = None
        self.attached = False
        self.paused = False
        self._stop = threading.Event()
        self._vrect = None
        self.snap = {}
        self.glass_url = None
        self._min_all = False
        self._perm = None

    # ------------------------------------------------------------------ events from the core
    def feed(self, ev):
        t = ev.get("type")
        if t == "activity":
            ev = _panel_activity(ev)
            if ev is None:
                return
        elif t == "msg":
            if ev.get("role") != "user":
                return
            ev = {"type": "msg", "role": "user", "text": str(ev.get("text", ""))[:200]}
        elif t not in PASS:
            return
        if t in ("persona", "state", "merged", "music", "fps", "widgets", "w_gpu", "w_np", "w_weather", "w_cal", "w_notes"):
            self.snap[t] = ev
        if self.attached:
            self.em(ev)

    # ------------------------------------------------------------------ window
    def create(self, webview):
        kw = dict(url=str(config.RES_DIR / "ui" / "desktop.html"), js_api=DeskBridge(self), width=800, height=600,
                  x=PARK, y=PARK, frameless=True, easy_drag=False, resizable=False, background_color="#07050c")
        try:
            self.window = webview.create_window(TITLE, focus=False, shadow=False, **kw)
        except TypeError:          # older pywebview without focus/shadow
            self.window = webview.create_window(TITLE, **kw)
        self.em.window = self.window
        atexit.register(self.close)
        return self.window

    def _find_hwnd(self):
        for _ in range(150):
            if self._stop.is_set():
                return 0
            h = _u().FindWindowW(None, TITLE)
            if h:
                return h
            time.sleep(0.1)
        return 0

    def _style(self):
        GWL_EXSTYLE, NOACTIVATE, TOOLWINDOW, APPWINDOW, LAYERED = -20, 0x08000000, 0x80, 0x40000, 0x80000
        u = _u()
        ex = u.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        u.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, (ex | NOACTIVATE | TOOLWINDOW) & ~APPWINDOW & ~LAYERED)

    def _attach(self):
        import ctypes
        from ctypes import wintypes as wt
        u = _u()
        layer, dv = find_wallpaper_layer()
        if not layer:
            return False
        self.layer, self.defview = layer, dv
        self._style()
        # A true child window (WS_CHILD, no popup/caption/min-max): then "Show desktop" and minimize-all can't
        # minimize it, and Windows never parks it as a little "Jarvis Desktop" bar in the bottom-left corner.
        GWL_STYLE = -16
        st = u.GetWindowLongPtrW(self.hwnd, GWL_STYLE)
        st = (st & ~0x80000000 & ~0x00C00000 & ~0x00040000 & ~0x00020000 & ~0x00010000 & ~0x00080000) | 0x40000000
        u.SetWindowLongPtrW(self.hwnd, GWL_STYLE, st)
        if u.IsIconic(self.hwnd):
            u.ShowWindow(self.hwnd, 9)                    # SW_RESTORE
        u.SetParent(self.hwnd, layer)
        vx, vy, vw, vh = virtual_rect()
        lr = wt.RECT()
        u.GetWindowRect(layer, ctypes.byref(lr))
        # SWP_NOACTIVATE | SWP_SHOWWINDOW | SWP_FRAMECHANGED, HWND_BOTTOM so nothing of ours ever covers the icons
        u.SetWindowPos(self.hwnd, wt.HWND(1), vx - lr.left, vy - lr.top, vw, vh, 0x0010 | 0x0040 | 0x0020)
        self._vrect = (vx, vy, vw, vh)
        _icons(dv, False)
        _hide_minimized_strips(True)
        self.attached = True
        return True

    def start(self):
        """Runs in its own thread once the windows exist: attach, play Juno's intro, then keep watch."""
        if not IS_WINDOWS:
            return
        self.hwnd = self._find_hwnd()
        if not self.hwnd:
            print("[desktop] the desktop window never appeared; living desktop off")
            return
        if not self.em.ready.wait(30):
            print("[desktop] the desktop page never loaded; living desktop off")
            return
        shot = self._screenshot() if config.DESK_INTRO else None
        try:
            if not self._attach():
                print("[desktop] couldn't find the wallpaper layer (WorkerW); living desktop off")
                return
        except Exception as e:
            print(f"[desktop] attaching failed: {e}")
            return
        merged = bool(_flags("merged"))
        persona = getattr(self.core, "persona_key", "juno") if self.core else "juno"
        self.em({"type": "desk_init", "monitors": monitors(), "shot": shot, "intro": bool(config.DESK_INTRO),
                 "persona": persona, "merged": merged, "quality": config.DESK_QUALITY, "viz": config.DESK_VIZ,
                 "fps": config.ANIM_FPS})
        for k in ("state", "music", "fps", "widgets", "w_gpu", "w_np", "w_weather", "w_cal", "w_notes"):
            if k in self.snap:
                self.em(self.snap[k])
        self._allow_camera()
        if self.glass_url:
            self.em({"type": "glass", "url": self.glass_url})
        print(f"[desktop] living desktop on ({len(monitors())} monitor(s))")
        self._watch()

    # ------------------------------------------------------------------ glass mode on the desktop
    def glass(self, url):
        """Show glass mode (url) on the wallpaper, or take it off (None). False if the desktop isn't running."""
        if url and not self.attached:
            return False
        self.glass_url = url
        self.em({"type": "glass", "url": url})
        if IS_WINDOWS:
            try:
                tray = _u().FindWindowW("Shell_TrayWnd", None)
                if url and not self._min_all:                  # show the desktop so you can see it (like Win+D)
                    _u().PostMessageW(tray, 0x0111, 419, 0)    # WM_COMMAND: minimize all
                    self._min_all = True
                elif not url and self._min_all:
                    _u().PostMessageW(tray, 0x0111, 416, 0)    # undo minimize all
                    self._min_all = False
            except Exception as e:
                print(f"[desktop] show desktop: {e}")
        return True

    def _allow_camera(self):
        """Let glass mode's page (our own localhost server, inside the desktop) use the camera. Nothing else gets it:
        the wallpaper can't show WebView2's permission prompt, and no other page in it should ever ask."""
        if not IS_WINDOWS or self._perm is not None:
            return
        try:
            import clr  # noqa: F401  (pythonnet, which pywebview uses on Windows)
            from System import Action
            form = self.window.native
            br = getattr(form, "browser", None)
            wv = getattr(form, "webview", None) or getattr(br, "webview", None) or getattr(br, "web_view", None)
            if wv is None:
                print("[desktop] no WebView2 to give the camera to; glass mode will use its own window")
                return

            def hook():
                from Microsoft.Web.WebView2.Core import CoreWebView2PermissionKind as K, CoreWebView2PermissionState as St
                def on_perm(sender, args):
                    try:
                        uri = str(args.Uri or "")
                        ours = re.match(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?(/|$)", uri, re.I)
                        # an iframe's request can be reported with the wallpaper page's own address (file:///...)
                        host_page = uri.lower().startswith("file:") and bool(self.glass_url)
                        allow = args.PermissionKind == K.Camera and (ours or host_page)
                        args.State = St.Allow if allow else St.Deny
                        print(f"[desktop] {args.PermissionKind} requested by {uri[:80]}: {'allowed' if allow else 'denied'}")
                    except Exception as e:
                        print(f"[desktop] camera permission: {e}")
                wv.CoreWebView2.PermissionRequested += on_perm
                self._perm = on_perm
            form.Invoke(Action(hook))
        except Exception as e:
            self._perm = None
            print(f"[desktop] couldn't let glass mode use the camera here: {e}")

    def _screenshot(self):
        """The desktop as it is right now, for Juno to grab. Stays on this PC: it only goes into our own page."""
        try:
            from PIL import ImageGrab
            im = ImageGrab.grab(all_screens=True).convert("RGB")
            if im.width > 2560:
                im = im.resize((2560, round(im.height * 2560 / im.width)))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=72)
            return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception as e:
            print(f"[desktop] no screenshot for the intro: {e}")
            return None

    def _watch(self):
        u = _u()
        while not self._stop.wait(1.5):
            try:
                # GA_PARENT: the real parent. (GetParent gives the OWNER for our kind of window, so it never matched
                # and 1.0.21 re-attached and redrew everything every 1.5 seconds: the flashing.)
                if not u.IsWindow(self.layer) or (u.GetAncestor(self.hwnd, 1) or 0) != (self.layer or 0):   # Explorer restarted
                    self.attached = False
                    if self._attach():
                        print("[desktop] Explorer restarted; back on the desktop")
                        self.em({"type": "desk_layout", "monitors": monitors()})
                    continue
                if u.IsIconic(self.hwnd):                      # something minimized it anyway: put it back
                    self._attach()
                    continue
                v = virtual_rect()
                if v != self._vrect:                                   # monitor added, removed or resized
                    self._attach()
                    self.em({"type": "desk_layout", "monitors": monitors()})
                full = _fullscreen_in_front()
                if full != self.paused:
                    self.paused = full
                    self.em({"type": "desk_pause", "on": full})
            except Exception as e:
                print(f"[desktop] watch: {e}")

    def close(self):
        """Give the normal desktop back: icons visible, our window out of the wallpaper, wallpaper repainted."""
        if self._stop.is_set():
            return
        self._stop.set()
        self.em.close()
        if not IS_WINDOWS:
            return
        try:
            u = _u()
            _icons(self.defview or find_wallpaper_layer()[1], True)
            _hide_minimized_strips(False)
            if self.hwnd and self.attached:
                st = u.GetWindowLongPtrW(self.hwnd, -16)
                u.SetWindowLongPtrW(self.hwnd, -16, (st & ~0x40000000) | 0x80000000)     # back to a normal popup
                u.SetParent(self.hwnd, None)
                u.SetWindowPos(self.hwnd, None, PARK, PARK, 0, 0, 0x0001 | 0x0004 | 0x0010)
            if self.layer:
                u.RedrawWindow(self.layer, None, None, 0x0001 | 0x0004 | 0x0080 | 0x0100)   # INVALIDATE|ERASE|ALLCHILDREN|UPDATENOW
            self.attached = False
        except Exception as e:
            print(f"[desktop] restoring the desktop: {e}")


def _glass_port():
    """The port glass mode's server actually got (it moves up if the usual one is busy)."""
    try:
        import tools
        hub = tools._GLASS["get"]() if tools._GLASS["get"] else None
        return hub.port if hub else config.GLASS_PORT
    except Exception:
        return config.GLASS_PORT


class DeskBridge:
    """What ui/desktop.js can call (window.pywebview.api.*)."""

    def __init__(self, desk):
        self._desk = desk

    def picture(self, name):
        """One of her pictures as a data: link. WebView2 won't let the graphics card read a picture loaded
        straight from a file:// page (it counts as another site), but it will read one handed over like this."""
        import base64
        import config
        if not re.fullmatch(r"[\w-]+\.png", name or ""):
            return ""
        p = config.RES_DIR / "ui" / name
        return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode("ascii") if p.exists() else ""

    def ready(self):
        self._desk.em.mark_ready()
        return True
