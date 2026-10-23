"""
J.A.R.V.I.S. for Windows, powered by Claude.

    python jarvis.py              the HUD app (default)
    python jarvis.py --console    no window, just the terminal
    python jarvis.py --no-voice   don't use the microphone (type only)
"""
import argparse
import json
import os
import queue
import sys
import threading
import time
from pathlib import Path

import config
from core import Core


# =================================================================== HUD app
class Emitter:
    """Pushes events into the web UI from ONE worker thread.

    Why: pywebview's evaluate_js blocks and isn't happy being hammered from
    several threads, and calling it after the window closes throws
    ObjectDisposedException. So everything is queued here and the worker stops
    the moment the window starts closing.

    Speed: every call into the page interrupts its animation, so whatever is
    waiting goes over in ONE call (a reply streams in dozens of pieces a second).
    High-frequency readings (mic level, voice level, telemetry) only keep their
    latest value and are rate-limited without ever holding up anything else.
    """

    COALESCE = {"level": 1 / 15, "voice": 1 / 15, "telemetry": 0.0}   # min seconds between sends

    def __init__(self):
        self.window = None
        self.ready = threading.Event()
        self.closed = threading.Event()
        self.q = queue.Queue(maxsize=2000)
        self._latest = {}
        self._sent = {}
        self._wake_pending = False
        self._lock = threading.Lock()
        threading.Thread(target=self._worker, daemon=True, name="ui-emitter").start()

    def __call__(self, ev):
        if self.closed.is_set():
            return
        t = ev.get("type")
        if t in self.COALESCE:
            if not self.ready.is_set():
                return
            with self._lock:
                self._latest[t] = ev
                if self._wake_pending:
                    return
                self._wake_pending = True
            item = ("wake", None)
        else:
            item = ("event", ev)
        try:
            self.q.put_nowait(item)
        except queue.Full:
            pass

    def _next_due(self):
        with self._lock:
            if not self._latest:
                return None
            now = time.time()
            return min(max(0.0, self._sent.get(t, 0) + self.COALESCE[t] - now) for t in self._latest)

    def _worker(self):
        self.ready.wait()
        while not self.closed.is_set():
            due = self._next_due()
            batch = []
            try:
                kind, x = self.q.get(timeout=0.5 if due is None else max(0.005, due))
                if kind == "stop":
                    return
                if kind == "event":
                    batch.append(x)
            except queue.Empty:
                pass
            while len(batch) < 300:                       # everything else already waiting goes in the same call
                try:
                    kind, x = self.q.get_nowait()
                except queue.Empty:
                    break
                if kind == "stop":
                    return
                if kind == "event":
                    batch.append(x)
            now = time.time()
            with self._lock:
                self._wake_pending = False
                for t in list(self._latest):
                    if now - self._sent.get(t, 0) >= self.COALESCE[t]:
                        batch.append(self._latest.pop(t))
                        self._sent[t] = now
            if not batch or self.closed.is_set():
                continue
            data = json.dumps(batch, default=str)
            js = f"window.J && (window.J.batch ? window.J.batch({data}) : {data}.forEach(function (e) {{ window.J.on(e); }}))"
            try:
                self.window.evaluate_js(js)
            except Exception:
                if self.closed.is_set():
                    return

    def mark_ready(self):
        self.ready.set()

    def close(self):
        self.closed.set()
        try:
            self.q.put_nowait(("stop", None))
        except queue.Full:
            pass


class Bridge:
    """Methods the web UI can call (window.pywebview.api.*).
    Attributes start with _ so pywebview doesn't try to expose them."""

    def __init__(self, core, emitter):
        self._core = core
        self._em = emitter
        self._win = None
        self._max = False

    def ready(self):
        self._em.mark_ready()
        return {"model": config.MODEL, "address": config.ADDRESS_AS}

    def send(self, text):
        self._core.submit(text, "typed")

    def ptt(self):
        self._core.push_to_talk()

    def action(self, name, value=None):
        threading.Thread(target=self._core.quick_action, args=(name, value), daemon=True).start()

    def stop(self):
        self._core.stop_speaking()

    def switch(self, key=None):
        self._core.switch_persona(key)

    def stop_dictation(self):
        self._core.events.put(("dictate_stop", None))

    def toggle_mute(self):
        threading.Thread(target=self._core.toggle_mute, daemon=True).start()

    def set_autostart(self, on):
        threading.Thread(target=self._core.set_autostart, args=(bool(on),), daemon=True).start()

    def key_status(self):
        self._core.emit_key_status()

    def save_keys(self, anthropic="", groq=""):
        threading.Thread(target=self._core.save_keys, args=(str(anthropic or ""), str(groq or "")), daemon=True).start()

    def set_discord_send(self, on):
        threading.Thread(target=self._core.set_discord_send, args=(bool(on),), daemon=True).start()

    def confirm(self, cid, approved, always=False):
        self._core.resolve_confirm(cid, bool(approved), always=bool(always))

    def set_permission(self, key, on):
        threading.Thread(target=self._core.set_permission, args=(str(key), bool(on)), daemon=True).start()

    def minimize(self):
        self._win.minimize()

    def toggle_max(self):
        if self._max:
            self._win.restore()
        else:
            self._win.maximize()
        self._max = not self._max

    def close(self):
        self._em.close()
        self._win.destroy()


def run_gui(voice, start_hidden=False, show_hook=None):
    # The HUD's sound effects are made in the page; let them play without waiting for a click first.
    flag = "--autoplay-policy=no-user-gesture-required"
    extra = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
    if flag not in extra:
        os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (extra + " " + flag).strip()
    import webview
    from mini import Mini
    emitter = Emitter()
    mini = Mini(Emitter) if config.MINI_HUD and sys.platform == "win32" else None

    phone = []

    def emit(ev):
        emitter(ev)
        if mini:
            mini.feed(ev)
        if phone:
            phone[0].feed(ev)

    core = Core(emit, voice=voice)
    _start_phone(core, phone, emitter)
    bridge = Bridge(core, emitter)
    window = webview.create_window(
        "J.A.R.V.I.S.",
        url=str(config.RES_DIR / "ui" / "index.html"),
        js_api=bridge,
        width=1360, height=840, min_size=(1100, 700),
        background_color="#02060b",
        frameless=True, easy_drag=False,
    )
    emitter.window = window
    bridge._win = window
    if mini:
        try:
            mini.create(webview)
        except Exception as e:
            print(f"[mini] couldn't create the mini HUD: {e}")
            mini = None

    def on_closing():
        emitter.close()     # stop talking to the window before it's torn down
        if mini:
            mini.close()    # otherwise the hidden widget keeps the app alive
        core.shutdown()

    window.events.closing += on_closing

    def went_away():
        # Stop all HUD animation while minimized and show the corner widget instead
        emitter({"type": "window", "visible": False})
        if mini:
            mini.show()

    def came_back():
        emitter({"type": "window", "visible": True})
        if mini:
            mini.hide()

    try:
        window.events.minimized += went_away
        window.events.restored += came_back
        window.events.maximized += came_back
    except Exception:
        pass

    def quit_app():
        emitter.close()
        if mini:
            mini.hide()
        threading.Timer(2.0, window.destroy).start()

    core.on_quit = quit_app

    def minimize():
        try:
            window.minimize()
            went_away()
            return True
        except Exception as e:
            print(f"[window] minimize failed: {e}")
            return False

    def restore():
        try:
            window.restore()
            try:
                window.show()
            except Exception:
                pass
            came_back()
            return True
        except Exception as e:
            print(f"[window] restore failed: {e}")
            return False

    core.on_minimize = minimize
    core.on_restore = restore
    if show_hook is not None:
        show_hook["fn"] = restore              # someone launched Jarvis again: bring this copy forward
    if start_hidden:
        def tuck_away():                       # started with Windows: straight to the corner widget
            if emitter.ready.wait(60):
                time.sleep(0.8)
                minimize()
        threading.Thread(target=tuck_away, daemon=True, name="start-hidden").start()
    if mini:
        mini.on_expand = restore
        mini.bridge._core = core
        threading.Thread(target=mini.settle, args=("J.A.R.V.I.S.",), daemon=True, name="mini-settle").start()
    core.start()
    webview.start()
    emitter.close()
    if mini:
        mini.close()
    core.shutdown()


def _start_phone(core, holder, emit):
    if not config.PHONE:
        return
    from phone import PhoneHub
    hub = PhoneHub(core)
    err = hub.start()
    if err:
        print(err)
        emit({"type": "msg", "role": "system", "text": err})
        return
    holder.append(hub)
    print(f"Phone remote: open {hub.url} on your phone (same Wi-Fi).")
    emit({"type": "msg", "role": "system", "text": f"Phone remote is on. On your phone (same Wi-Fi) open: {hub.url}"})


# =================================================================== console
def run_console(voice):
    done = threading.Event()
    phone = []

    def emit(ev):
        if phone:
            phone[0].feed(ev)
        t = ev.get("type")
        if t == "msg":
            who = {"user": "You", "jarvis": "Jarvis", "system": "**"}[ev["role"]]
            if ev["role"] != "user" or ev.get("source") == "voice":
                print(f"{who}: {ev['text']}")
        elif t == "dictation":
            print("** dictation " + (f"ON -> {ev.get('window')}" if ev["on"] else "off"))
        elif t == "mic":
            print("** mic " + ("MUTED (type 'unmute' or press " + ev["hotkey"] + ")" if ev["muted"] else "live"))
        elif t == "persona":
            print(f"\n== {ev['wordmark']} ==")
        elif t == "activity" and ev["kind"] == "tool_start":
            print(f"   ...{ev['data']['name']}")
        elif t == "turn_start":
            print(f"{ev.get('who') or 'Jarvis'}: ", end="", flush=True)
        elif t == "duo":
            print("** both of them are listening" if ev["on"] else "** one at a time")
        elif t == "reply_delta":
            print(ev["text"], end="", flush=True)
        elif t == "turn_end":
            print(f"   ({ev['secs']}s)\n")
        elif t == "confirm":
            print(f"\n!! AUTHORIZATION REQUIRED: {ev['title']}\n   {ev['detail']}\n   Type yes or no.")
        elif t == "alert":
            print(f"\n** {ev['text']}")
        elif t == "quit":
            done.set()

    core = Core(emit, voice=voice)
    core.on_quit = done.set
    _start_phone(core, phone, lambda ev: None)
    core.start()

    def read_input():
        while True:
            try:
                line = input()
            except (EOFError, KeyboardInterrupt):
                done.set()
                return
            core.submit(line, "typed")

    threading.Thread(target=read_input, daemon=True).start()
    try:
        while not done.wait(0.5):
            pass
        time.sleep(1)
    except KeyboardInterrupt:
        pass
    core.shutdown()
    print("JARVIS offline.")


def _dpi_aware():
    """Use real pixels on scaled displays (125%, 150%...). Without this, window
    positions and screenshots disagree and window-focused vision crops the wrong area."""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # per-monitor
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _log_to_file():
    """Started by Windows (no console window): keep the log in Documents/Jarvis/logs/jarvis.log."""
    try:
        d = config.JARVIS_DIR / "logs"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "jarvis.log"
        if f.exists() and f.stat().st_size > 5 * 2**20:
            f.replace(d / "jarvis.old.log")
        out = open(f, "a", encoding="utf-8", buffering=1)
        out.write(f"\n===== started {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
        sys.stdout = sys.stderr = out
    except Exception:
        pass


def main():
    _dpi_aware()
    ap = argparse.ArgumentParser(description="J.A.R.V.I.S.")
    ap.add_argument("--console", action="store_true", help="run in the terminal without the app window")
    ap.add_argument("--no-voice", action="store_true", help="don't use the microphone")
    ap.add_argument("--startup", action="store_true", help="started by Windows at login (no console, starts tucked away)")
    ap.add_argument("--after-update", action="store_true", help="restarted by the updater")
    args, _unknown = ap.parse_known_args()      # the installer may pass its own arguments; ignore them
    if (args.startup or config.FROZEN or sys.stdout is None
            or (args.after_update and Path(sys.executable).name.lower() == "pythonw.exe")):
        _log_to_file()                         # no console window: keep a log file instead
    import autostart
    show_hook = {"fn": None}
    if not autostart.claim(lambda: show_hook["fn"] and show_hook["fn"](), wait=45 if args.after_update else 0):
        print("Jarvis is already running; brought him to the front.")
        return
    if args.startup and config.STARTUP_DELAY > 0:
        time.sleep(config.STARTUP_DELAY)       # let Windows finish logging in before loading models
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if args.console:
        run_console(not args.no_voice)
    else:
        try:
            run_gui(not args.no_voice, start_hidden=args.startup, show_hook=show_hook)
            import updater
            if getattr(updater, "RESTARTING", False):
                sys.exit(updater.RESTART_CODE)        # tells run_jarvis.bat to close this window quietly
        except ImportError:
            print("pywebview isn't installed (run setup.bat). Falling back to console mode.")
            run_console(not args.no_voice)


if __name__ == "__main__":
    main()
