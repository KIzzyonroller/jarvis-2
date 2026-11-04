"""
The desktop characters' own process: Jarvis, Ultron (or the merged one) as see-through figures living on your
desktop. Started by buddies.py as `Jarvis.exe --buddies <port> <token> <ui folder>` (or `python buddies_qt.py ...`
from source) and talked to over a local socket. Kept in its own process because it uses Qt (the main window is
WebView2, which can't do see-through windows) and so a crash here can never take Jarvis down.

What it does on its own, many times a second, using almost nothing:
  * walks them along the top of the taskbar, sits them on the window you're using (riding along when you drag it),
    peeks them in from the screen edges, naps them when you're away, hides them during fullscreen games and video
  * dances them when your PC plays music (the speakers' level, not what's playing)
  * fades them and lets every click go straight through when the mouse is over them; hold Ctrl to grab and move
    one, double-click (with Ctrl) to open his window
  * plays the entrances when he opens an app: Ultron reaches out and tears it open, Jarvis throws a ring of light

Windows only. Everything that touches Windows is wrapped so a failure just leaves the figure standing still.
"""
import ctypes
import json
import math
import os
import random
import socket
import sys
import threading
import time

IS_WINDOWS = sys.platform == "win32"
SCALES = {"s": .15, "m": .22, "l": .3}
FOOT = 180            # figure units between the hem and the bottom of its window (room for falling motes)


# ====================================================================== Windows
class Win:
    def __init__(self):
        self.ok = IS_WINDOWS
        self.mine = set()                     # our own windows: never perch on them or call them "fullscreen"
        self.pid = os.getpid()
        if not self.ok:
            return
        from ctypes import wintypes as wt
        self.wt = wt
        u = self.u = ctypes.WinDLL("user32")
        H = wt.HWND
        u.GetForegroundWindow.restype = H
        u.GetWindowRect.argtypes = [H, ctypes.POINTER(wt.RECT)]
        u.IsZoomed.argtypes = u.IsIconic.argtypes = u.IsWindowVisible.argtypes = [H]
        u.GetClassNameW.argtypes = [H, wt.LPWSTR, ctypes.c_int]
        u.MonitorFromWindow.argtypes, u.MonitorFromWindow.restype = [H, wt.DWORD], wt.HANDLE
        u.MonitorFromPoint.argtypes, u.MonitorFromPoint.restype = [wt.POINT, wt.DWORD], wt.HANDLE
        u.GetMonitorInfoW.argtypes = [wt.HANDLE, ctypes.c_void_p]
        u.GetWindowLongW.argtypes, u.GetWindowLongW.restype = [H, ctypes.c_int], ctypes.c_long
        u.SetWindowLongW.argtypes = [H, ctypes.c_int, ctypes.c_long]
        u.GetAsyncKeyState.argtypes, u.GetAsyncKeyState.restype = [ctypes.c_int], ctypes.c_short
        u.FindWindowW.argtypes, u.FindWindowW.restype = [wt.LPCWSTR, wt.LPCWSTR], H
        u.GetWindowThreadProcessId.argtypes = [H, ctypes.POINTER(wt.DWORD)]
        try:
            u.GetDpiForWindow.argtypes, u.GetDpiForWindow.restype = [H], wt.UINT
        except AttributeError:
            pass
        try:
            self.dwm = ctypes.WinDLL("dwmapi")
        except OSError:
            self.dwm = None

        class MI(ctypes.Structure):
            _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", wt.RECT), ("rcWork", wt.RECT), ("dwFlags", wt.DWORD)]

        class LII(ctypes.Structure):
            _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]
        self.MI, self.LII = MI, LII

    def rect(self, h):
        wt = self.wt
        r = wt.RECT()
        if self.dwm is not None:              # the visible frame, without the invisible resize border
            if self.dwm.DwmGetWindowAttribute(wt.HWND(h), 9, ctypes.byref(r), ctypes.sizeof(r)) == 0:
                return (r.left, r.top, r.right, r.bottom)
        self.u.GetWindowRect(h, ctypes.byref(r))
        return (r.left, r.top, r.right, r.bottom)

    def monitor(self, h=None, pt=None):
        """(monitor rect, work area) of a window or point."""
        if h:
            m = self.u.MonitorFromWindow(h, 2)
        else:
            m = self.u.MonitorFromPoint(self.wt.POINT(int(pt[0]), int(pt[1])), 2)
        mi = self.MI()
        mi.cbSize = ctypes.sizeof(mi)
        self.u.GetMonitorInfoW(m, ctypes.byref(mi))
        a, b = mi.rcMonitor, mi.rcWork
        return (a.left, a.top, a.right, a.bottom), (b.left, b.top, b.right, b.bottom)

    def cls(self, h):
        buf = ctypes.create_unicode_buffer(128)
        self.u.GetClassNameW(h, buf, 128)
        return buf.value

    def foreground(self):
        """(hwnd, rect, kind) of the window you're using. kind: 'normal', 'max', 'full', 'desktop' or 'mine'."""
        h = self.u.GetForegroundWindow()
        if not h:
            return None, None, "desktop"
        hv = int(h)
        pid = self.wt.DWORD()
        self.u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        if hv in self.mine or pid.value == self.pid:
            return hv, None, "mine"
        c = self.cls(h)
        if c in ("Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Windows.UI.Core.CoreWindow"):
            return hv, None, "desktop"
        if self.u.IsIconic(h) or not self.u.IsWindowVisible(h):
            return hv, None, "desktop"
        r = self.rect(h)
        mon, work = self.monitor(h=h)
        if r[0] <= mon[0] and r[1] <= mon[1] and r[2] >= mon[2] and r[3] >= mon[3]:
            return hv, r, "full"
        if self.u.IsZoomed(h):
            return hv, r, "max"
        return hv, r, "normal"

    def cursor(self):
        p = self.wt.POINT()
        self.u.GetCursorPos(ctypes.byref(p))
        return p.x, p.y

    def down(self, vk):
        return bool(self.u.GetAsyncKeyState(vk) & 0x8000)

    def idle_seconds(self):
        li = self.LII()
        li.cbSize = ctypes.sizeof(li)
        if not self.u.GetLastInputInfo(ctypes.byref(li)):
            return 0
        return max(0, (ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000.0

    def dpi(self, h):
        try:
            return self.u.GetDpiForWindow(h) or 96
        except Exception:
            return 96

    def click_through(self, h, on):
        """WS_EX_TRANSPARENT on or off (Qt made the window layered for us, which this needs)."""
        GWL_EXSTYLE, WS_EX_TRANSPARENT, WS_EX_LAYERED = -20, 0x20, 0x80000
        ex = self.u.GetWindowLongW(h, GWL_EXSTYLE)
        want = (ex | WS_EX_TRANSPARENT | WS_EX_LAYERED) if on else (ex & ~WS_EX_TRANSPARENT)
        if want != ex:
            self.u.SetWindowLongW(h, GWL_EXSTYLE, want)

    def no_activate(self, h):
        GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = -20, 0x08000000, 0x80
        ex = self.u.GetWindowLongW(h, GWL_EXSTYLE)
        self.u.SetWindowLongW(h, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)


class Speakers:
    """How loud the PC is playing right now (0..1), from Windows' own meter. No audio is captured."""

    def __init__(self):
        self.meter = None
        self.level = 0.0
        self._stop = False
        if IS_WINDOWS:
            threading.Thread(target=self._run, daemon=True, name="speaker-meter").start()

    def _run(self):
        try:
            import comtypes
            comtypes.CoInitialize()
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
            dev = AudioUtilities.GetSpeakers()
            dev = getattr(dev, "_dev", dev)
            from ctypes import POINTER, cast
            iface = dev.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
            self.meter = cast(iface, POINTER(IAudioMeterInformation))
        except Exception as e:
            print(f"[buddies] no speaker meter: {e}", flush=True)
            return
        while not self._stop:
            try:
                self.level = float(self.meter.GetPeakValue())
            except Exception:
                self.level = 0.0
            time.sleep(0.07)

    def stop(self):
        self._stop = True


# ====================================================================== Qt
def run(port, token, ui_dir):
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")        # Qt pixels = Windows pixels
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-logging --log-level=3")
    from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
    from PySide6.QtWebEngineCore import QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    win = Win()
    page_path = os.path.join(ui_dir, "buddies.html")

    class Page(QWebEnginePage):
        def __init__(self, pane):
            super().__init__(pane.view)
            self.pane = pane

        def javaScriptConsoleMessage(self, level, msg, line, src):
            if msg.startswith("@@"):
                try:
                    self.pane.on_js(json.loads(msg[2:]))
                except Exception:
                    pass
            elif int(getattr(level, "value", level)) >= 2:          # errors only
                print(f"[buddies js] {msg} ({line})", flush=True)

    class Pane(QWidget):
        """A see-through, never-focused, always-on-top window holding one page."""

        def __init__(self, query, w, h, on_js=None):
            flags = (Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus |
                     Qt.NoDropShadowWindowHint | Qt.WindowTransparentForInput)
            super().__init__(None, flags)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating)
            self.setAttribute(Qt.WA_NoSystemBackground)
            self.view = QWebEngineView(self)
            self.view.setAttribute(Qt.WA_TranslucentBackground)
            self.view.setStyleSheet("background: transparent")
            self.page = Page(self)
            self.page.setBackgroundColor(Qt.transparent)
            self.view.setPage(self.page)
            self.ready = False
            self.queue = []
            self.cb = on_js
            self.through = True
            self.resize(w, h)
            self.view.resize(w, h)
            url = QUrl.fromLocalFile(page_path)
            url.setQuery(query)
            self.view.load(url)
            self.move(-32000, -32000)
            self.show()
            self.hwnd = int(self.winId())
            win.mine.add(self.hwnd)
            if win.ok:
                win.no_activate(self.hwnd)

        def resizeEvent(self, e):
            self.view.resize(self.width(), self.height())

        def send(self, msg):
            if not self.ready:
                self.queue.append(msg)
                return
            self.page.runJavaScript(f"window.B && B.feed({json.dumps(msg)})")

        def on_js(self, m):
            if m.get("e") == "ready":
                self.ready = True
                for q in self.queue:
                    self.page.runJavaScript(f"window.B && B.feed({json.dumps(q)})")
                self.queue = []
            if self.cb:
                self.cb(self, m)

        def set_through(self, on):
            if on != self.through and win.ok:
                self.through = on
                win.click_through(self.hwnd, on)

        def bye(self):
            win.mine.discard(self.hwnd)
            self.close()
            self.deleteLater()

    class Link(QObject):
        got = Signal(dict)

    link = Link()
    sock = socket.create_connection(("127.0.0.1", int(port)), timeout=10)
    sock.settimeout(None)
    sock.sendall((json.dumps({"t": "hello", "token": token}) + "\n").encode())
    wlock = threading.Lock()

    def tell(obj):
        try:
            with wlock:
                sock.sendall((json.dumps(obj) + "\n").encode())
        except OSError:
            pass

    def reader():
        buf = b""
        while True:
            try:
                data = sock.recv(65536)
            except OSError:
                data = b""
            if not data:
                link.got.emit({"t": "quit"})
                return
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                try:
                    link.got.emit(json.loads(line))
                except ValueError:
                    pass

    threading.Thread(target=reader, daemon=True, name="buddies-link").start()
    speakers = Speakers()
    d = Director(app, win, Pane, tell, speakers, QTimer)
    link.got.connect(d.on_host)
    tell({"t": "ready"})
    code = app.exec()
    speakers.stop()
    return code


# ====================================================================== behaviour
class Figure:
    """One character: its window, where it is, what it's doing."""
    SPEED = {"jarvis": 75, "ultron": 58, "merged": 66}

    def __init__(self, d, who, sc, clone=False):
        self.d, self.who, self.sc, self.clone = d, who, sc, clone
        self.W, self.H = int(1300 * sc), int(1600 * sc)
        q = f"role=figure&who={who}&sc={sc:.3f}" + ("&clone=1" if clone else "")
        self.pane = d.Pane(q, self.W, self.H, on_js=d.on_js)
        self.x, self.y = -32000.0, -32000.0
        self.vx = 0.0
        self.tx = None
        self.mode, self.until = "arrive", 0
        self.dir = 1
        self.sent = {}
        self.held = None
        self.perch_h = None
        self.perch_off = 0.0
        self.peek_side = 0
        self.life = time.time() + 45 if clone else None
        self.visible = False
        self.alpha_on = False
        self.acting = False
        self.home = None

    # coordinates: (ox, oy) is the hem, on the floor or a window's top edge
    def origin(self):
        return self.x + self.W / 2, self.y + self.H - FOOT * self.sc

    def put(self, ox, oy):
        self.x, self.y = ox - self.W / 2, oy - (self.H - FOOT * self.sc)

    def place(self):
        self.pane.move(int(self.x), int(self.y))

    def say(self, key, msg):
        """Send only what changed."""
        if self.sent.get(key) != msg:
            self.sent[key] = msg
            self.pane.send(msg)

    def show(self, on):
        if on != self.alpha_on:
            self.alpha_on = on
            self.pane.send({"k": "show", "on": on})
            self.pane.send({"k": "sleep", "on": False})

    def inner(self):
        """The part of the window the figure actually fills, for hovering and grabbing."""
        return (self.x + self.W * .28, self.y + self.H * .18, self.x + self.W * .72, self.y + self.H * .97)


class Director:
    def __init__(self, app, win, Pane, tell, speakers, QTimer):
        self.app, self.win, self.Pane, self.tell, self.spk = app, win, Pane, tell, speakers
        self.opts = {"desktop_who": "persona", "desktop_size": "m", "roam": True, "perch": True, "peek": True,
                     "nap": True, "dance": True, "hover_fade": True, "merged": False}
        self.persona = "jarvis"
        self.duo = False
        self.state = "idle"
        self.figs = []
        self.clones = []
        self.fx = None
        self.fx_busy = 0
        self.act = None
        self.music = 0.0
        self.music_since = None
        self.last = time.time()
        self.fg = (None, None, "desktop")
        self.fg_t = 0
        self.hidden = False
        self.merging = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    # ------------------------------------------------------------ from the main app
    def on_host(self, m):
        t = m.get("t")
        if t == "quit":
            for f in self.figs + self.clones:
                f.pane.bye()
            if self.fx:
                self.fx.bye()
            self.app.quit()
        elif t == "init" or t == "opts":
            old = dict(self.opts)
            self.opts.update(m.get("opts", {}))
            self.persona = m.get("persona", self.persona)
            self.duo = m.get("duo", self.duo)
            if t == "init" and m.get("pos"):
                self._home = m["pos"]
            if t == "init" or old.get("desktop_size") != self.opts["desktop_size"] or old.get("desktop_who") != self.opts["desktop_who"]:
                self.rebuild()
            elif old.get("merged") != self.opts["merged"]:
                self.start_merge(self.opts["merged"])
        elif t == "persona":
            self.persona = m.get("key", self.persona)
            if self.opts["desktop_who"] == "persona" and not self.opts["merged"] and len(self.figs) == 1:
                f = self.figs[0]
                if f.who != self.persona:
                    f.who = self.persona
                    f.pane.send({"k": "who", "who": self.persona})
                    f.pane.send({"k": "flash"})
        elif t == "duo":
            self.duo = bool(m.get("on"))
        elif t == "state":
            self.state = m.get("state", "idle")
            for f in self.figs:
                f.say("state", {"k": "state", "state": self.state})
        elif t == "env":
            f = self.speaker_fig(m.get("who"))
            if f:
                f.pane.send({"k": "env", "env": m.get("env"), "step": m.get("step", .05), "delay": m.get("delay", 0)})
        elif t == "mic":
            for f in self.figs:
                f.pane.send({"k": "mic", "v": m.get("v", 0)})
        elif t == "act_start":
            self.act_start(m.get("who"), m.get("id"))
        elif t == "act_go":
            self.act_go(m.get("id"), m.get("rect"))
        elif t == "act_cancel":
            self.act_cancel(m.get("id"))
        elif t == "pointer":
            self.pointer(m.get("at"), m.get("kind"))
        elif t == "clone":
            self.make_clones(int(m.get("n") or 3))
        elif t == "clones_away":
            for c in self.clones:
                c.life = time.time()

    def speaker_fig(self, who):
        if not self.figs:
            return None
        for f in self.figs:
            if f.who == who:
                return f
        return self.figs[0]

    # ------------------------------------------------------------ who's out
    def wanted(self):
        if self.opts.get("merged"):
            return ["merged"]
        w = self.opts.get("desktop_who", "persona")
        if w == "both":
            return ["jarvis", "ultron"]
        if w in ("jarvis", "ultron"):
            return [w]
        return [self.persona if self.persona in ("jarvis", "ultron") else "jarvis"]

    def scale_for(self, h=None):
        sc = SCALES.get(self.opts.get("desktop_size", "m"), .22)
        return sc

    def rebuild(self):
        for f in self.figs:
            f.pane.bye()
        self.figs = []
        sc = self.scale_for()
        mon, work = self.monitor_now()
        names = self.wanted()
        home = getattr(self, "_home", None)
        for i, who in enumerate(names):
            f = Figure(self, who, sc)
            if home and i == 0:
                f.put(home[0], home[1])
            else:
                f.put(work[0] + (work[2] - work[0]) * (.7 + .12 * i), work[3])
            f.mode, f.until = "idle", time.time() + 2
            f.place()
            f.say("state", {"k": "state", "state": self.state})
            self.figs.append(f)
        if self.fx is None:
            self.fx = self.Pane("role=fx", 640, 360, on_js=self.on_js)

    # ------------------------------------------------------------ the merge (the secret code)
    def start_merge(self, on):
        """Merging: the two walk together, a flash, and the merged one stands there. Splitting: the reverse."""
        if not self.figs:
            return self.rebuild()
        if on:
            mid = sum(f.origin()[0] for f in self.figs) / len(self.figs)
            oy = self.figs[0].origin()[1]
            for f in self.figs:
                f.mode, f.tx, f.until = "merge", mid, time.time() + 4
            self.merging = {"on": True, "at": (mid, oy), "t": time.time()}
        else:
            ox, oy = self.figs[0].origin()
            self.flash(ox, oy - 700 * self.figs[0].sc)
            self.rebuild()
            for i, f in enumerate(self.figs):
                f.put(ox + (i - .5) * f.W * .5, oy)
                f.mode, f.tx = "walk", ox + (i - .5) * f.W * 1.6
                f.place()

    def finish_merge(self):
        mid, oy = self.merging["at"]
        self.merging = None
        self.flash(mid, oy - 700 * self.scale_for())
        self._home = (mid, oy)
        self.rebuild()
        self._home = None
        for f in self.figs:
            f.pane.send({"k": "flash"})

    def flash(self, x, y):
        self.fx_show_at((x, y))
        mon = self.fx_mon
        self.fx.send({"k": "fx", "id": "flash", "kind": "flash", "at": [x - mon[0], y - mon[1]]})

    # ------------------------------------------------------------ clones
    def make_clones(self, n):
        if not self.figs:
            return
        base = self.figs[0]
        n = max(1, min(5, n))
        for c in self.clones:
            c.life = time.time()
        ox, oy = base.origin()
        for i in range(n):
            c = Figure(self, base.who, base.sc * .55, clone=True)
            c.put(ox + (i - n / 2) * 20, oy)
            c.mode, c.tx = "walk", ox + random.uniform(-500, 500)
            c.place()
            self.clones.append(c)
        base.pane.send({"k": "flash"})

    # ------------------------------------------------------------ opening an app
    def act_fig(self, who):
        if not self.figs:
            return None
        if self.opts.get("merged"):
            return self.figs[0]
        for f in self.figs:
            if f.who == who:
                return f
        return self.figs[0]

    def act_start(self, who, aid):
        f = self.act_fig(who)
        if f is None or not f.visible:
            self.tell({"t": "act_skip", "id": aid})
            return
        mon, work = self.monitor_now()
        guess = ((mon[0] + mon[2]) / 2, mon[1] + (mon[3] - mon[1]) * .35)
        self.act = {"id": aid, "fig": f, "rect": None, "t": time.time()}
        f.acting = True
        f.mode = "act"
        ox, oy = f.origin()
        f.dir = 1 if guess[0] >= ox else -1
        f.pane.send({"k": "face", "dir": f.dir})
        f.pane.send({"k": "act_start", "local": self.local(f, guess)})

    def local(self, f, pt):
        ox, oy = f.origin()
        return [(pt[0] - ox) / (f.sc * f.dir), (pt[1] - oy) / f.sc]

    def act_go(self, aid, rect):
        a = self.act
        if not a or a["id"] != aid or not rect:
            return
        f = a["fig"]
        l, t, r, b = rect
        center = ((l + r) / 2, (t + b) / 2)
        f.dir = 1 if center[0] >= f.origin()[0] else -1
        f.pane.send({"k": "face", "dir": f.dir})
        f.pane.send({"k": "act_target", "local": self.local(f, center)})
        f.pane.send({"k": "act_go"})
        self.fx_show_at(center)
        mon = self.fx_mon
        ox, oy = f.origin()
        self.fx.send({"k": "fx", "id": aid, "who": f.who, "origin": [ox - mon[0], oy - mon[1]], "sc": f.sc, "dir": f.dir,
                      "rect": [l - mon[0], t - mon[1], r - l, b - t]})
        self.fx_busy += 1

    def act_cancel(self, aid):
        a = self.act
        if a and a["id"] == aid:
            a["fig"].pane.send({"k": "act_cancel"})

    def pointer(self, at, kind):
        if not at or not self.figs or self.fx is None:
            return
        f = self.figs[0]
        self.fx_show_at(at)
        mon = self.fx_mon
        last = getattr(self, "_ptr", None)
        if not last or not (mon[0] <= last[0] < mon[2] and mon[1] <= last[1] < mon[3]):
            ox, oy = f.origin()
            last = (ox, oy - 600 * f.sc)
        self._ptr = tuple(at)
        self.fx.send({"k": "fx", "id": "ptr", "kind": "pointer", "who": f.who, "click": kind != "move",
                      "from": [last[0] - mon[0], last[1] - mon[1]], "at": [at[0] - mon[0], at[1] - mon[1]]})
        self.fx_busy += 1

    def fx_show_at(self, pt):
        mon, _ = self.win.monitor(pt=pt) if self.win.ok else ((0, 0, 1920, 1080), None)
        self.fx_mon = mon
        self.fx.setGeometry(mon[0], mon[1], mon[2] - mon[0], mon[3] - mon[1])
        self.fx.raise_()

    def on_js(self, pane, m):
        e = m.get("e")
        if e == "act_done":
            a = self.act
            if a and a["fig"].pane is pane:
                a["fig"].acting = False
                a["fig"].mode, a["fig"].until = "idle", time.time() + 3
                self.act = None
                self.tell({"t": "act_done", "id": a["id"]})
        elif e == "fx_done":
            if m.get("id") != "flash":
                self.fx_busy = max(0, self.fx_busy - 1)
            if self.fx_busy == 0:
                QTimer_single(lambda: self.fx.move(-32000, -32000) if self.fx_busy == 0 else None, 300)
        elif e == "dblclick":
            self.tell({"t": "open_window"})

    # ------------------------------------------------------------ the world
    def monitor_now(self):
        """The monitor you're working on (the one with the window you're using), and its work area."""
        if not self.win.ok:
            return (0, 0, 1920, 1080), (0, 0, 1920, 1040)
        h, r, kind = self.fg
        if h and kind not in ("mine",):
            try:
                return self.win.monitor(h=h)
            except Exception:
                pass
        return self.win.monitor(pt=self.win.cursor())

    def tick(self):
        now = time.time()
        dt = min(.1, now - self.last)
        self.last = now
        if not self.figs:
            return
        w = self.win
        if w.ok and now - self.fg_t > .25:
            self.fg_t = now
            try:
                self.fg = w.foreground()
            except Exception:
                self.fg = (None, None, "desktop")
        h, frect, kind = self.fg
        # fullscreen game or video: out of the way entirely (and drawing nothing)
        hide = kind == "full"
        if hide != self.hidden:
            self.hidden = hide
            for f in self.figs + self.clones:
                f.pane.send({"k": "sleep", "on": hide})
                if hide:
                    f.pane.move(-32000, -32000)
        if hide:
            return
        mon, work = self.monitor_now()
        idle = w.idle_seconds() if w.ok else 0
        napping = self.opts.get("nap") and idle > 300 and self.state in ("idle", "sleeping", "standby")
        # music: the speakers have been busy for a few seconds and it isn't him talking
        lvl = self.spk.level if self.state != "speaking" else 0
        self.music = self.music * .9 + lvl * .1
        if self.music > .04:
            self.music_since = self.music_since or now
        else:
            self.music_since = None
        dancing = bool(self.opts.get("dance") and self.music_since and now - self.music_since > 3 and not napping)
        cur = w.cursor() if w.ok else (-1, -1)
        ctrl = w.down(0x11) if w.ok else False
        lmb = w.down(0x01) if w.ok else False
        talking = self.state in ("listening", "thinking", "speaking", "working")

        if self.merging:
            done = all(abs(f.origin()[0] - self.merging["at"][0]) < 30 for f in self.figs)
            if done or now - self.merging["t"] > 4:
                self.finish_merge()
                return

        for i, f in enumerate(self.figs):
            f.visible = True
            f.show(True)
            self.step(f, i, dt, now, mon, work, frect, kind, napping, dancing, talking, cur, ctrl, lmb)
        for c in list(self.clones):
            if now > c.life:
                c.show(False)
                if now > c.life + 1.2:
                    c.pane.bye()
                    self.clones.remove(c)
                continue
            c.visible = True
            c.show(True)
            self.step(c, 9, dt, now, mon, work, frect, kind, False, dancing, False, cur, False, False)

    def step(self, f, i, dt, now, mon, work, frect, kind, napping, dancing, talking, cur, ctrl, lmb):
        floor = work[3]
        ox, oy = f.origin()
        # grabbing with Ctrl held: the window takes the mouse only then, so normally every click goes through
        il, it, ir, ib = f.inner()
        over = il <= cur[0] <= ir and it <= cur[1] <= ib
        f.pane.set_through(not (ctrl and over) and f.held is None)
        if f.held is not None:
            if lmb:
                f.x, f.y = cur[0] - f.held[0], cur[1] - f.held[1]
                f.place()
                return
            f.held = None
            f.mode, f.until = "idle", now + 8
            ox, oy = f.origin()
            if not f.clone:
                self.tell({"t": "moved", "pos": [ox, oy]})
            if abs(oy - floor) > 4 and not self.on_window_edge(f, frect):
                f.mode = "drop"
        elif ctrl and over and lmb and not f.acting:
            f.held = (cur[0] - f.x, cur[1] - f.y)
            f.mode = "held"
            return
        f.say("fade", {"k": "fade", "on": bool(self.opts.get("hover_fade") and over and not ctrl)})
        f.say("nap", {"k": "nap", "on": bool(napping)})
        f.say("dance", {"k": "dance", "v": round(min(1, self.music * 4), 1) if dancing else 0})

        speed = Figure.SPEED.get(f.who, 66) * (1.6 if f.clone else 1) * (f.sc / .22) ** .5
        roam = self.opts.get("roam", True) or f.clone
        if f.acting or f.mode == "act":
            self.settle(f, dt, oy)
            return
        if napping and not f.clone:
            f.mode = "nap"
        elif f.mode == "nap":
            f.mode, f.until = "idle", now + 2
        if talking and not f.clone and f.mode in ("walk", "idle"):
            # he's being talked to: stop and turn to face the middle of the screen
            f.tx = None
            want = 1 if (mon[0] + mon[2]) / 2 >= ox else -1
            if want != f.dir:
                f.dir = want
            f.say("motion", {"k": "motion", "m": "stand", "dir": f.dir, "lean": 0})
            self.settle(f, dt, self.ground(f, frect, kind, floor))
            return

        if f.mode == "merge":
            self.walk_to(f, f.tx, speed * 1.8, dt)
            self.settle(f, dt, oy)
            return
        if f.mode == "perch":
            ok = (frect and kind == "normal" and self.opts.get("perch") and frect[2] - frect[0] > f.W * .9
                  and frect[1] - mon[1] > f.H * .6 and self.fg[0] == f.perch_h)
            if not ok or now > f.until:
                f.mode = "drop"
            else:
                x = min(max(frect[0] + f.perch_off, frect[0] + f.W * .3), frect[2] - f.W * .3)
                f.put(x, frect[1] + 1)                     # riding along on the title bar
                f.say("motion", {"k": "motion", "m": "perch", "dir": f.dir, "lean": 0})
                f.place()
                return
        if f.mode == "drop":
            self.settle(f, dt, floor, fast=True)
            if abs(f.origin()[1] - floor) < 2:
                f.mode, f.until = "idle", now + random.uniform(2, 5)
            return
        if f.mode == "peek":
            if now > f.until:
                f.mode, f.tx = "walk", (work[0] + work[2]) / 2 + random.uniform(-300, 300)
            else:
                edge_x = mon[0] + f.W * .12 if f.peek_side < 0 else mon[2] - f.W * .12
                self.walk_to(f, edge_x, speed * 1.4, dt, lean=f.peek_side * -1.2)
                f.dir = -f.peek_side
                self.settle(f, dt, floor)
                return

        if f.mode in ("idle", "arrive", "nap") and now > f.until and roam and f.mode != "nap":
            r = random.random()
            if (self.opts.get("perch") and frect and kind == "normal" and r < .3 and not f.clone
                    and frect[1] - mon[1] > f.H * .6 and frect[2] - frect[0] > f.W):
                f.mode, f.perch_h, f.until = "perch", self.fg[0], now + random.uniform(20, 60)
                f.perch_off = random.uniform(f.W * .3, max(f.W * .31, frect[2] - frect[0] - f.W * .3))
                f.say("motion", {"k": "motion", "m": "perch", "dir": f.dir})
            elif self.opts.get("peek") and r < .4 and not f.clone:
                f.mode, f.until, f.peek_side = "peek", now + 9, random.choice((-1, 1))
            else:
                f.mode = "walk"
                f.tx = self.pick_x(f, i, work)
        if f.mode == "walk":
            if f.tx is None:
                f.tx = self.pick_x(f, i, work)
            arrived = self.walk_to(f, f.tx, speed, dt)
            if arrived:
                f.mode, f.until, f.tx = "idle", now + random.uniform(3, 9) * (.5 if f.clone else 1), None
            self.settle(f, dt, floor)
            return
        # standing still
        f.say("motion", {"k": "motion", "m": "nap" if f.mode == "nap" else "stand", "dir": f.dir, "lean": 0})
        self.settle(f, dt, self.ground(f, frect, kind, floor))

    def on_window_edge(self, f, frect):
        if not frect:
            return False
        ox, oy = f.origin()
        return abs(oy - frect[1]) < 12 and frect[0] < ox < frect[2]

    def ground(self, f, frect, kind, floor):
        return f.origin()[1] if f.mode in ("held",) else floor

    def pick_x(self, f, i, work):
        lo, hi = work[0] + f.W * .4, work[2] - f.W * .4
        x = random.uniform(lo, hi)
        for g in self.figs:                         # keep the two of them apart
            if g is not f and abs(g.origin()[0] - x) < f.W * .8:
                x = min(hi, max(lo, g.origin()[0] + (f.W if x > g.origin()[0] else -f.W)))
        return x

    def walk_to(self, f, tx, speed, dt, lean=None):
        ox, oy = f.origin()
        dx = tx - ox
        if abs(dx) < 3:
            f.say("motion", {"k": "motion", "m": "stand", "dir": f.dir, "lean": 0})
            return True
        f.dir = 1 if dx > 0 else -1
        step = math.copysign(min(abs(dx), speed * dt), dx)
        f.put(ox + step, oy)
        f.say("motion", {"k": "motion", "m": "walk", "dir": f.dir, "lean": lean if lean is not None else f.dir * .6})
        f.place()
        return False

    def settle(self, f, dt, target_y, fast=False):
        ox, oy = f.origin()
        if abs(oy - target_y) > 1:
            k = min(1, dt * (9 if fast else 5))
            f.put(ox, oy + (target_y - oy) * k)
        f.place()


def QTimer_single(fn, ms):
    from PySide6.QtCore import QTimer
    QTimer.singleShot(ms, fn)


if __name__ == "__main__":
    sys.exit(run(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else
                 os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")))
