"""
Juno's music player: a small pop-up that shows whatever music is playing, with her sitting on top of it, feet
dangling over the edge, bobbing her head to it.

Where the information comes from:
  * The song, artist, how far in, play/pause/next/previous: Windows' own media controls (the same thing the
    volume flyout and lock screen use), so it works for Spotify, Apple Music, Media Player, Tidal, Deezer and so on,
    without logging in to anything.
  * The sound waves and the beat she bobs to: the loudness of that app's sound, read about 30 times a second from
    Windows' audio meter. Windows only gives the level, not separate bass/treble, so the bars follow the loudness
    (each bar a bit differently) rather than being a true frequency spectrum.

When it shows: a music app starts playing (videos in a browser don't count). It goes away 15 seconds after the
music is paused or stops, while a fullscreen game or video is in front, or when you close it (until the next song).
Like the corner widget, it never takes focus and is never really hidden (WebView2 paints black when it is), just
parked off-screen. Its outline is cut to the panel and her shape, so the desktop shows around her.
"""
import asyncio
import queue
import sys
import re
import threading
import time
from datetime import datetime, timezone

import config

TITLE = "Juno Music"
W, H = 400, 360                 # the page's layout size; the panel at the bottom and her above it
SIZE = 1.25                     # drawn this much bigger than the layout (the page zooms to match)
MARGIN = 16
PARK = -30000
PAUSE_HIDE = 15                 # seconds paused before it goes away
IS_WINDOWS = sys.platform == "win32"

# Windows' name for the app (AUMID) contains one of these: it's a music app. Browsers are left out on purpose.
MUSIC_APPS = ("spotify", "applemusic", "apple music", "zunemusic", "itunes", "tidal", "deezer", "amazon music",
              "amazonmusic", "musicbee", "foobar", "winamp", "aimp", "soundcloud", "pandora", "ytmdesktop",
              "youtube music", "cider", "qobuz", "audirvana", "dopamine", "plexamp")
PASS = {"voice", "state", "fps", "react"}   # from her core: her voice (she glows when she talks) and frame rate changes


def _is_music(aumid):
    a = (aumid or "").lower()
    return any(k in a for k in MUSIC_APPS)


def _secs(td):
    try:
        return max(0.0, td.total_seconds())
    except Exception:
        try:
            return max(0.0, int(td.duration) / 1e7)       # older winrt: TimeSpan with .duration in 100 ns ticks
        except Exception:
            return 0.0


class MusicPlayer:
    def __init__(self, emitter_cls):
        class _Em(emitter_cls):
            COALESCE = {"level": 1 / 30, "voice": 1 / 15}
        self.em = _Em()
        self.window = None
        self.hwnd = 0
        self.visible = False
        self.pos = None
        self.bridge = None
        self.core = None
        self.track = {}                # what the page was last told
        self.app = ""
        self.closed_for = None         # (title, artist) you closed it on: stays closed until the song changes
        self.paused_since = None
        self.cmds = queue.Queue()
        self._stop = threading.Event()
        self._drag0 = None
        self._region_runs = None
        self.dpr = 0.0                 # the page's real scale (Windows display scaling), once it reports it

    # ------------------------------------------------------------------ window
    def create(self, webview):
        self.bridge = MusicBridge(self)
        kw = dict(url=str(config.RES_DIR / "ui" / "music.html"), js_api=self.bridge, width=W, height=H, x=PARK,
                  y=PARK, frameless=True, easy_drag=False, on_top=True, resizable=False, background_color="#0a0416")
        try:
            self.window = webview.create_window(TITLE, focus=False, shadow=False, **kw)
        except TypeError:
            self.window = webview.create_window(TITLE, **kw)
        self.em.window = self.window
        return self.window

    def _handle(self):
        if self.hwnd or not IS_WINDOWS:
            return self.hwnd
        from mini import _u
        try:
            self.hwnd = _u().FindWindowW(None, TITLE) or 0
        except Exception:
            self.hwnd = 0
        if self.hwnd:
            self._style()
        return self.hwnd

    def _style(self):
        """No activation, no taskbar button, no alt-tab entry, and never layered (WebView2 paints black)."""
        from mini import _u
        u = _u()
        try:
            ex = u.GetWindowLongW(self.hwnd, -20)
            ex = ((ex | 0x08000000 | 0x80) & ~0x40000 & ~0x00080000) & 0xFFFFFFFF
            u.SetWindowLongW(self.hwnd, -20, ex - (1 << 32) if ex >= 1 << 31 else ex)
            u.SetWindowPos(self.hwnd, None, 0, 0, 0, 0, 0x0002 | 0x0001 | 0x0004 | 0x0010 | 0x0020)
            u.ShowWindowAsync(self.hwnd, 0)
            u.ShowWindowAsync(self.hwnd, 4)
        except Exception as e:
            print(f"[music] style failed: {e}")

    def _scale(self):
        """Screen pixels per layout pixel. The page reports its own scale; asking Windows alone isn't enough, because
        when the app isn't DPI-aware Windows says 100% while WebView2 still draws at 125% or 150%, and the bottom of
        the player (the play buttons) got cut off."""
        from mini import _u
        s = self.dpr
        if not s:
            try:
                s = (_u().GetDpiForWindow(self.hwnd) or 96) / 96
            except Exception:
                s = 1.0
        return s * SIZE

    def layout(self, dpr):
        try:
            self.dpr = max(.5, min(4.0, float(dpr)))
        except (TypeError, ValueError):
            return
        if self.visible and self.hwnd:
            try:
                self._place()
            except Exception:
                pass

    def _rect(self):
        """Bottom-right of the main screen, just above the taskbar (or wherever you dragged it)."""
        import ctypes
        from ctypes import wintypes as wt
        u = ctypes.windll.user32
        s = self._scale()
        w, h = int(W * s), int(H * s)
        if self.pos:
            vx, vy = u.GetSystemMetrics(76), u.GetSystemMetrics(77)
            vw, vh = u.GetSystemMetrics(78), u.GetSystemMetrics(79)
            x, y = self.pos
            if vx <= x <= vx + vw - 60 and vy <= y <= vy + vh - 60:
                return x, y, w, h
        r = wt.RECT()
        u.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0)       # SPI_GETWORKAREA
        m = int(MARGIN * s)
        return r.right - w - m, r.bottom - h - m, w, h

    def _place(self):
        from mini import _u
        x, y, w, h = self._rect()
        _u().SetWindowPos(self.hwnd, -1, x, y, w, h, 0x0010 | 0x4000)      # TOPMOST, NOACTIVATE, ASYNC

    def _park(self):
        from mini import _u
        _u().SetWindowPos(self.hwnd, None, PARK, PARK, 0, 0, 0x0001 | 0x0004 | 0x0010 | 0x4000)

    def _remember_pos(self):
        import ctypes
        from ctypes import wintypes as wt
        from mini import _u
        r = wt.RECT()
        if self.hwnd and _u().GetWindowRect(self.hwnd, ctypes.byref(r)) and r.left > PARK + 1000:
            self.pos = (r.left, r.top)

    def shape(self, runs):
        """Cut the window to the panel and her outline. runs: [[x, y, w, h], ...] in page pixels."""
        if not (IS_WINDOWS and self._handle() and runs):
            return
        import ctypes
        g, u = ctypes.windll.gdi32, ctypes.windll.user32
        g.CreateRectRgn.restype = ctypes.c_void_p
        g.CombineRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        g.DeleteObject.argtypes = [ctypes.c_void_p]
        u.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        s = self._scale()
        rgn = g.CreateRectRgn(0, 0, 0, 0)
        for x, y, w, h in runs:
            r = g.CreateRectRgn(int(x * s), int(y * s), int((x + w) * s + .999), int((y + h) * s + .999))
            g.CombineRgn(rgn, rgn, r, 2)                          # RGN_OR
            g.DeleteObject(r)
        if not u.SetWindowRgn(self.hwnd, rgn, True):             # on success Windows owns the region
            g.DeleteObject(rgn)
        self._region_runs = runs

    def _tell_desktop(self, on):
        """The big Juno on the desktop steps away while her music player is up (she's sitting on it instead)."""
        emit = getattr(self.core, "emit", None)
        if emit:
            try:
                emit({"type": "music", "on": bool(on)})
            except Exception:
                pass

    def show(self):
        if self.visible or not self.window or not self._handle():
            return
        self.visible = True
        self._tell_desktop(True)
        self.em({"type": "window", "visible": True})
        try:
            self._place()
        except Exception as e:
            print(f"[music] show failed: {e}")

    def hide(self):
        if not self.visible:
            return
        self.visible = False
        self._tell_desktop(False)
        self.em({"type": "window", "visible": False})
        try:
            self._remember_pos()
            self._park()
        except Exception as e:
            print(f"[music] hide failed: {e}")

    def close(self):
        self._stop.set()
        self.em.close()
        try:
            if self.window:
                self.window.destroy()
        except Exception:
            pass

    # ------------------------------------------------------------------ core events (her voice, for the grin)
    def feed(self, ev):
        t = ev.get("type")
        if t in PASS and (self.visible or t == "fps"):
            self.em(ev)

    # ------------------------------------------------------------------ start
    def settle(self):
        if not IS_WINDOWS:
            return
        time.sleep(0.6)
        for _ in range(100):
            if self._handle():
                break
            time.sleep(0.1)
        else:
            print("[music] player window never appeared; music player off")
            self.window = None
            return
        self._park()
        threading.Thread(target=self._poll, daemon=True, name="music-poll").start()
        threading.Thread(target=self._meter, daemon=True, name="music-meter").start()

    # ------------------------------------------------------------------ what's playing (Windows media controls)
    def _poll(self):
        try:
            from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
        except Exception as e:
            print(f"[music] Windows media controls aren't available ({e}); music player off")
            return
        loop = asyncio.new_event_loop()
        mgr = None
        while not self._stop.is_set():
            try:
                if mgr is None:
                    mgr = loop.run_until_complete(Manager.request_async())
                self._tick(loop, mgr)
            except Exception as e:
                print(f"[music] {e}")
                mgr = None
                self._stop.wait(5)
            try:                                   # a button press wakes it straight away
                cmd = self.cmds.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                self._do(loop, mgr, *cmd)
            except Exception as e:
                print(f"[music] {cmd[0]} failed: {e}")

    def _session(self, mgr):
        """The music app that's playing (or Windows' current one if it's a music app)."""
        best = None
        for s in mgr.get_sessions():
            aumid = s.source_app_user_model_id or ""
            if not _is_music(aumid):
                continue
            try:
                playing = int(s.get_playback_info().playback_status) == 4
            except Exception:
                playing = False
            if playing:
                return s
            best = best or s
        cur = mgr.get_current_session()
        if cur is not None and _is_music(cur.source_app_user_model_id):
            return cur
        return best

    def _tick(self, loop, mgr):
        s = self._session(mgr)
        now = time.time()
        if s is None:
            self.app = ""
            if self.visible:
                self.hide()
            self.track = {}
            return
        props = loop.run_until_complete(s.try_get_media_properties_async())
        title, artist = (props.title or "").strip(), (props.artist or props.album_artist or "").strip()
        try:
            playing = int(s.get_playback_info().playback_status) == 4
        except Exception:
            playing = False
        pos = dur = 0.0
        try:
            tl = s.get_timeline_properties()
            dur = _secs(tl.end_time) - _secs(tl.start_time)
            pos = _secs(tl.position) - _secs(tl.start_time)
            if playing:                            # apps only update this now and then: add the time since
                try:
                    upd = tl.last_updated_time
                    if upd.tzinfo is None:
                        upd = upd.replace(tzinfo=timezone.utc)
                    gap = (datetime.now(timezone.utc) - upd).total_seconds()
                    if 0 < gap < 3600:
                        pos += gap
                except Exception:
                    pass
            if dur > 0:
                pos = min(pos, dur)
        except Exception:
            pass
        self.app = s.source_app_user_model_id or ""
        key = (title, artist)
        new_song = key != (self.track.get("title"), self.track.get("artist"))
        ev = {"type": "track", "title": title, "artist": artist, "playing": playing, "pos": round(pos, 2),
              "dur": round(dur, 2), "app": _app_name(self.app)}
        if new_song or playing != self.track.get("playing") or abs(pos - self._expected(now)) > 1.5:
            self.em(ev)
        self.track = dict(ev, at=now)
        if new_song:
            self.closed_for = None
            if playing and title:
                try:
                    import proactive
                    proactive.maybe_song(self.core, {"title": title, "artist": artist, "app": _app_name(self.app)})
                except Exception as e:
                    print(f"[music] song chat: {e}")
        # show or hide
        if playing:
            self.paused_since = None
        elif self.paused_since is None:
            self.paused_since = now
        want = bool(config.MUSIC_PLAYER and title and self.closed_for != key and
                    (playing or (self.visible and now - (self.paused_since or now) < PAUSE_HIDE)))
        if want and self._fullscreen():
            want = False
        if want and not self.visible:
            self.show()
        elif not want and self.visible:
            self.hide()

    def _expected(self, now):
        t = self.track
        if not t:
            return -99
        return t.get("pos", 0) + ((now - t.get("at", now)) if t.get("playing") else 0)

    def _fullscreen(self):
        try:
            import tools
            return bool(tools.fullscreen_app())
        except Exception:
            return False

    def _do(self, loop, mgr, what, arg=None):
        s = self._session(mgr) if mgr else None
        if s is None:
            return
        if what == "toggle":
            loop.run_until_complete(s.try_toggle_play_pause_async())
        elif what == "next":
            loop.run_until_complete(s.try_skip_next_async())
        elif what == "prev":
            loop.run_until_complete(s.try_skip_previous_async())
        elif what == "seek":
            tl = s.get_timeline_properties()
            ticks = int((_secs(tl.start_time) + float(arg)) * 1e7)
            loop.run_until_complete(s.try_change_playback_position_async(ticks))
        time.sleep(0.25)
        self._tick(loop, mgr)

    # ------------------------------------------------------------------ loudness, for the waves and her head bob
    def _meter(self):
        try:
            import comtypes
            comtypes.CoInitialize()
            from ctypes import POINTER, cast
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
        except Exception as e:
            print(f"[music] no audio meter ({e}); the waves will just idle")
            return
        meter, found_for, found_at = None, None, 0.0
        while not self._stop.is_set():
            if not self.visible:
                meter = None
                self._stop.wait(0.5)
                continue
            now = time.time()
            if meter is None or found_for != self.app or now - found_at > 4:
                meter, found_for, found_at = self._find_meter(AudioUtilities, IAudioMeterInformation, cast, POINTER,
                                                              CLSCTX_ALL), self.app, now
            try:
                v = float(meter.GetPeakValue()) if meter else 0.0
            except Exception:
                v, meter = 0.0, None
            self.em({"type": "level", "v": round(v, 3)})
            self._stop.wait(1 / 30)

    def _find_meter(self, AudioUtilities, IMeter, cast, POINTER, CLSCTX_ALL):
        """That app's own sound (so her talking doesn't move the bars); the whole speaker output if it can't be found."""
        app = (self.app or "").lower()
        stem = app.split("!")[0].split("_")[0].split(".")[-1] if "!" in app else app.replace(".exe", "")
        try:
            for sess in AudioUtilities.GetAllSessions():
                p = getattr(sess, "Process", None)
                name = (p.name() if p else "").lower().replace(".exe", "")
                if name and stem and (name in app or stem in name or name in stem):
                    return sess._ctl.QueryInterface(IMeter)
        except Exception:
            pass
        try:
            dev = AudioUtilities.GetSpeakers()
            dev = getattr(dev, "_dev", dev)
            iface = dev.Activate(IMeter._iid_, CLSCTX_ALL, None)
            return cast(iface, POINTER(IMeter))
        except Exception:
            return None


def _app_name(aumid):
    a = (aumid or "").lower()
    for key, name in (("spotify", "Spotify"), ("applemusic", "Apple Music"), ("zunemusic", "Media Player"),
                      ("itunes", "iTunes"), ("tidal", "Tidal"), ("deezer", "Deezer"), ("amazon", "Amazon Music"),
                      ("musicbee", "MusicBee"), ("foobar", "foobar2000"), ("soundcloud", "SoundCloud")):
        if key in a:
            return name
    return ""


class MusicBridge:
    """window.pywebview.api.* for the music player."""

    def __init__(self, player):
        self._p = player

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
        self._p.em.mark_ready()
        print("[music] player loaded")
        return True

    def fps(self):
        return config.ANIM_FPS

    def toggle(self):
        self._p.cmds.put(("toggle",))

    def next(self):
        self._p.cmds.put(("next",))

    def prev(self):
        self._p.cmds.put(("prev",))

    def seek(self, seconds):
        self._p.cmds.put(("seek", float(seconds)))

    def close(self):
        p = self._p
        p.closed_for = (p.track.get("title"), p.track.get("artist"))
        p.hide()

    def shape(self, runs, dpr=None):
        if dpr:
            self._p.layout(dpr)
        threading.Thread(target=self._p.shape, args=(runs,), daemon=True).start()

    def size(self):
        return SIZE

    def drag_start(self):
        self._p._remember_pos()
        self._p._drag0 = self._p.pos

    def drag_to(self, dx, dy):
        p = self._p
        if not (p.hwnd and p._drag0):
            return
        from mini import _u
        x0, y0 = p._drag0
        _u().SetWindowPos(p.hwnd, None, int(x0 + dx), int(y0 + dy), 0, 0, 0x0001 | 0x0004 | 0x0010 | 0x4000)

    def drag_end(self):
        self._p._remember_pos()
        self._p._drag0 = None
