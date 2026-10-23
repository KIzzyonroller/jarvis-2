"""
The mini HUD: a small always-on-top widget in the top-right corner that
appears while the main window is minimized, so you can still see him
listen, think and talk.

Why it's never actually hidden: the first version created it hidden and
showed it with a raw Win32 call, and it came up as a black box. WebView2
paints black when Windows Forms thinks the window is invisible, or when the
window is left "layered" (which pywebview's hidden-window trick does). Both
are avoided now: the widget stays shown the whole time and is just parked
off-screen when it isn't needed. Showing it is a move, which never
activates anything or steals focus.

It can never take focus. The window is created with WS_EX_NOACTIVATE (clicks
work but Windows doesn't switch to it) and WS_EX_TOOLWINDOW (no taskbar or
alt-tab entry), and if WebView2 ever manages to grab focus anyway, a small
guard hands it straight back to whatever you were using.
"""
import sys
import threading
import time

import config

TITLE = "Jarvis Mini"
W, H, H_CONFIRM = 340, 108, 232          # logical pixels; scaled by the monitor's DPI
MARGIN = 14
PARK = -30000                            # off-screen spot where the widget waits while you're using the full HUD

# What the mini cares about. Everything else (transcript, telemetry, memory...) is skipped.
PASS = {"state", "voice", "voice_env", "level", "caption", "persona", "mic", "turn_start", "turn_end",
        "confirm", "confirm_done", "dictation", "sync"}
ACTIVITY = {"thinking_start", "tool_pending", "tool_start", "tool_done"}

IS_WINDOWS = sys.platform == "win32"
_U = None


def _u():
    """user32 with real 64-bit HWND types (its own instance so nobody else's argtypes clash)."""
    global _U
    if _U is None:
        import ctypes
        from ctypes import wintypes as wt
        u = ctypes.WinDLL("user32")
        H = wt.HWND
        u.SetWindowPos.argtypes = [H, H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
        u.ShowWindowAsync.argtypes = [H, ctypes.c_int]
        u.GetWindowRect.argtypes = [H, ctypes.POINTER(wt.RECT)]
        u.GetWindowLongW.argtypes = [H, ctypes.c_int]
        u.SetWindowLongW.argtypes = [H, ctypes.c_int, ctypes.c_long]
        u.FindWindowW.argtypes, u.FindWindowW.restype = [wt.LPCWSTR, wt.LPCWSTR], H
        try:
            u.GetDpiForWindow.argtypes, u.GetDpiForWindow.restype = [H], wt.UINT
        except AttributeError:
            pass
        _U = u
    return _U


def _detail(name, args):
    """One short line about a step, computed here so we never ship big tool arguments to the widget."""
    if not isinstance(args, dict):
        return ""
    if name == "blender":
        return str(args.get("action", "")) + (": " + args["name"] if args.get("name") else "")
    if name == "mouse":
        return (args.get("action", "").replace("_", " ") + (": " + args["what"] if args.get("what") else "")).strip()
    for k in ("target", "name", "query", "url", "title", "path", "page", "message", "command", "action"):
        v = args.get(k)
        if isinstance(v, str) and v.strip():
            v = v.strip().replace("\n", " ")
            return v if len(v) <= 48 else v[:45] + "..."
    return ""


class Mini:
    def __init__(self, emitter_cls):
        self.em = emitter_cls()
        self.window = None
        self.hwnd = 0
        self.visible = False
        self.pos = None                 # where the user last dragged it
        self.on_expand = lambda: None
        self.bridge = None
        self.snap = {}                  # latest persona / state / mic / caption / confirm, replayed on show
        self._confirm = False
        self._lock = threading.Lock()
        self._guard_on = threading.Event()

    # ------------------------------------------------------------------ events
    def feed(self, ev):
        """Called for every event the core emits (via the main tee)."""
        t = ev.get("type")
        if t == "activity":
            if ev.get("kind") not in ACTIVITY:
                return
            d = ev.get("data") or {}
            ev = {"type": "activity", "kind": ev["kind"], "name": d.get("name", ""),
                  "detail": _detail(d.get("name", ""), d.get("args")), "ok": d.get("ok", True)}
        elif t not in PASS:
            return
        with self._lock:
            if t in ("persona", "state", "mic", "caption", "dictation"):
                self.snap[t] = ev
            elif t == "confirm":
                self.snap["confirm"] = ev
            elif t == "confirm_done":
                self.snap.pop("confirm", None)
        if t == "confirm":
            self._set_confirm(True)
        elif t == "confirm_done":
            self._set_confirm(False)
        if self.visible:
            self.em(ev)

    # ------------------------------------------------------------------ window
    def create(self, webview):
        self.bridge = MiniBridge(self)
        try:
            self.window = webview.create_window(
                TITLE, url=str(config.RES_DIR / "ui" / "mini.html"), js_api=self.bridge,
                width=W, height=H, x=PARK, y=PARK, frameless=True, easy_drag=False, on_top=True,
                focus=False, resizable=False, background_color="#02060b", shadow=False,
            )
        except TypeError:          # older pywebview without focus/shadow
            self.window = webview.create_window(
                TITLE, url=str(config.RES_DIR / "ui" / "mini.html"), js_api=self.bridge,
                width=W, height=H, x=PARK, y=PARK, frameless=True, easy_drag=False, on_top=True,
                resizable=False, background_color="#02060b",
            )
        self.em.window = self.window
        return self.window

    def _handle(self):
        if self.hwnd or not IS_WINDOWS:
            return self.hwnd
        try:
            self.hwnd = _u().FindWindowW(None, TITLE) or 0      # plain Win32: safe from any thread
        except Exception:
            self.hwnd = 0
        if not self.hwnd:
            try:
                self.hwnd = int(self.window.native.Handle.ToInt64())
            except Exception:
                self.hwnd = 0
        if self.hwnd:
            self._style()
        return self.hwnd

    def _style(self):
        """No activation, no taskbar button, no alt-tab entry, rounded corners on Windows 11."""
        import ctypes
        u = _u()
        GWL_EXSTYLE, NOACTIVATE, TOOLWINDOW, APPWINDOW = -20, 0x08000000, 0x80, 0x40000
        try:
            ex = u.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            # WS_EX_LAYERED (left behind by window-opacity tricks) makes WebView2 paint black, so strip it
            ex = ((ex | NOACTIVATE | TOOLWINDOW) & ~APPWINDOW & ~0x00080000) & 0xFFFFFFFF
            u.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex - (1 << 32) if ex >= 1 << 31 else ex)
            # SWP_NOMOVE|NOSIZE|NOZORDER|NOACTIVATE|FRAMECHANGED
            u.SetWindowPos(self.hwnd, None, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0004 | 0x0010 | 0x0020)
            # The taskbar only re-checks a window when it's shown, so blink it once (it's
            # parked off-screen at this point) to drop the taskbar button it got at creation.
            u.ShowWindowAsync(self.hwnd, 0)       # SW_HIDE
            u.ShowWindowAsync(self.hwnd, 4)       # SW_SHOWNOACTIVATE
        except Exception as e:
            print(f"[mini] style failed: {e}")
        try:
            pref = ctypes.c_int(2)            # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(self.hwnd, 33, ctypes.byref(pref), 4)
        except Exception:
            pass

    def _scale(self):
        try:
            return (_u().GetDpiForWindow(self.hwnd) or 96) / 96
        except Exception:
            return 1.0

    def _rect(self, height):
        """Top-right of the primary screen's work area (above the taskbar), or where the user dragged it."""
        import ctypes
        from ctypes import wintypes as wt
        u = ctypes.windll.user32
        s = self._scale()
        w, h = int(W * s), int(height * s)
        if self.pos:
            vx, vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
            vw, vh = u.GetSystemMetrics(78), u.GetSystemMetrics(79)
            x, y = self.pos
            if vx <= x <= vx + vw - 40 and vy <= y <= vy + vh - 40:
                return x, y, w, h
        r = wt.RECT()
        u.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)       # SPI_GETWORKAREA
        m = int(MARGIN * s)
        return r.right - w - m, r.top + m, w, h

    def _place(self, height):
        x, y, w, h = self._rect(height)
        # HWND_TOPMOST, SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS: a move, never an activation
        _u().SetWindowPos(self.hwnd, -1, x, y, w, h, 0x0010 | 0x4000)

    def _park(self):
        # SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS
        _u().SetWindowPos(self.hwnd, None, PARK, PARK, 0, 0, 0x0001 | 0x0004 | 0x0010 | 0x4000)

    def settle(self, main_title):
        """Right after launch: find the widget, style it, make sure it's parked, and if
        creating it pulled focus away from the main window, give focus back."""
        import tools
        if not IS_WINDOWS:
            return
        time.sleep(0.5)
        for _ in range(100):
            if self._handle():
                break
            time.sleep(0.1)
        else:
            print("[mini] widget window never appeared; corner widget disabled")
            self.window = None
            return
        if not self.visible:
            self._park()
        for _ in range(20):
            time.sleep(0.15)
            if tools._fg() == self.hwnd:
                main = _u().FindWindowW(None, main_title)
                if main:
                    tools._force_foreground(main)
                break

    def _remember_pos(self):
        import ctypes
        from ctypes import wintypes as wt
        r = wt.RECT()
        if self.hwnd and _u().GetWindowRect(self.hwnd, ctypes.byref(r)) and r.left > PARK + 1000:
            self.pos = (r.left, r.top)

    def show(self):
        if not config.MINI_HUD or not self.window or not IS_WINDOWS or self.visible:
            return
        if not self._handle():
            return
        with self._lock:
            snap = [self.snap[k] for k in ("persona", "mic", "dictation", "state", "caption", "confirm") if k in self.snap]
        self.visible = True
        self.em({"type": "sync", "events": snap})
        self.em({"type": "window", "visible": True})
        try:
            self._place(H_CONFIRM if self._confirm else H)
        except Exception as e:
            print(f"[mini] show failed: {e}")
        self._guard_on.set()
        threading.Thread(target=self._guard, daemon=True, name="mini-guard").start()

    def hide(self):
        if not self.visible:
            return
        self.visible = False
        self._guard_on.clear()
        self.em({"type": "window", "visible": False})
        try:
            self._remember_pos()
            self._park()
        except Exception as e:
            print(f"[mini] hide failed: {e}")

    def _set_confirm(self, on):
        self._confirm = on
        if self.visible and self.hwnd:
            try:
                self._remember_pos()
                self._place(H_CONFIRM if on else H)
            except Exception:
                pass

    def _guard(self):
        """Belt and braces: if the widget somehow ends up with focus, give it
        straight back to the app the user was in."""
        import tools
        last = 0
        while self._guard_on.is_set():
            time.sleep(0.15)
            fg = tools._fg()
            if not fg:
                continue
            if fg == self.hwnd:
                if last:
                    tools._force_foreground(last)
            elif tools._is_user_app(fg):
                last = fg

    def close(self):
        self._guard_on.clear()
        self.em.close()
        try:
            if self.window:
                self.window.destroy()
        except Exception:
            pass


class MiniBridge:
    """window.pywebview.api.* for the mini widget."""

    def __init__(self, mini):
        self._mini = mini
        self._core = None

    def ready(self):
        self._mini.em.mark_ready()
        print("[mini] corner widget loaded")
        return True

    def expand(self):
        self._mini.on_expand()

    def toggle_mute(self):
        if self._core:
            threading.Thread(target=self._core.toggle_mute, daemon=True).start()

    def stop(self):
        if self._core:
            self._core.stop_speaking()

    def confirm(self, cid, approved, always=False):
        if self._core:
            self._core.resolve_confirm(cid, bool(approved), always=bool(always))

    def drag_start(self):
        m = self._mini
        m._remember_pos()
        m._drag0 = m.pos

    def drag_to(self, dx, dy):
        m = self._mini
        if not (m.hwnd and getattr(m, "_drag0", None)):
            return
        x0, y0 = m._drag0
        # SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS
        _u().SetWindowPos(m.hwnd, None, int(x0 + dx), int(y0 + dy), 0, 0, 0x0001 | 0x0004 | 0x0010 | 0x4000)

    def drag_end(self):
        self._mini._remember_pos()
        self._mini._drag0 = None
