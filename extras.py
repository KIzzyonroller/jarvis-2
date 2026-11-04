"""
The newer parts, wired together in one place so core.py only has to start this and feed it events:

  * the Options section (prefs.py): sends the list to the window, applies changes as they happen
  * the graphics card (gpu.py): download for hearing, the voice test, switching the voice live
  * the desktop characters (buddies.py), screen comments (comments.py), the small local brain (localbrain.py),
    safety presets (permissions.py), other languages, his own pointer and his voice into the mic
"""
import threading
import time

import config
import gpu
import prefs


class Extras:
    def __init__(self, core):
        self.core = core
        self.parts = {}
        self._stop = threading.Event()
        prefs.on_change("*", self._changed)

    # ------------------------------------------------------------ lifecycle
    def start(self):
        self.send_prefs()
        # The voice test runs once (per onnxruntime version), a minute after start so it doesn't slow the boot
        if gpu.needs_voice_test():
            threading.Thread(target=self._voice_test_later, args=(60,), daemon=True, name="voice-gpu-test").start()
        for name, starter in self._starters():
            try:
                part = starter()
                if part is not None:
                    self.parts[name] = part
            except Exception as e:
                print(f"[extras] {name} didn't start: {e}")

    def _starters(self):
        """(name, function that returns the started part or None). Each is optional and fails alone."""
        out = []
        try:
            import buddies
            out.append(("buddies", lambda: buddies.Host(self.core).start()))
        except ImportError:
            pass
        try:
            import comments
            out.append(("comments", lambda: comments.Commenter(self.core).start()))
        except ImportError:
            pass
        try:
            import localbrain
            out.append(("localbrain", lambda: localbrain.Lane(self.core).start()))
        except ImportError:
            pass
        try:
            import permissions
            out.append(("safety", lambda: permissions.apply_preset(prefs.get("safety")) or None))
        except (ImportError, AttributeError):
            pass
        try:
            import mic_voice
            out.append(("mic_voice", lambda: mic_voice.Router(self.core).start()))
        except ImportError:
            pass
        return out

    def stop(self):
        self._stop.set()
        for part in self.parts.values():
            try:
                part.stop()
            except Exception:
                pass

    def feed(self, ev):
        """Every event the app shows: the characters react to them, comments stay quiet while he's busy..."""
        for part in self.parts.values():
            fn = getattr(part, "feed", None)
            if fn:
                try:
                    fn(ev)
                except Exception as e:
                    print(f"[extras] feed: {e}")

    def part(self, name):
        return self.parts.get(name)

    # ------------------------------------------------------------ options
    def send_prefs(self):
        lane = self.parts.get("localbrain")
        local = {"on": bool(prefs.get("local_brain")), "ok": bool(lane and lane.ok), "note": lane.note if lane else "",
                 "gaming": bool(lane and lane.gaming)}
        try:
            import buddies
            desk = {"available": buddies.available()}
        except Exception:
            desk = {"available": False}
        self.core.emit({"type": "prefs", "items": prefs.view(), "gpu": gpu.status(), "local": local, "desk": desk})

    # ------------------------------------------------------------ the small local brain
    def setup_local(self):
        lane = self.parts.get("localbrain")
        if lane is None:
            return "The local brain part didn't start (see the log)."
        if not prefs.get("local_brain"):
            prefs.set("local_brain", True)

        def run():
            last = [0.0]

            def progress(step, pct):
                if time.time() - last[0] > 0.5:
                    last[0] = time.time()
                    self.core.emit({"type": "local_progress", "step": step, "pct": pct})

            ok, msg = lane.download(progress)
            self.core.emit({"type": "local_progress", "step": msg, "pct": 100 if ok else -1, "done": True})
            self.core.emit({"type": "toast", "text": msg})
            self.send_prefs()

        threading.Thread(target=run, daemon=True, name="local-download").start()
        return f"Downloading {prefs.get('local_model')} through Ollama (about 1.5 GB for the default). Progress is in Options > Brain."

    def local_text(self):
        lane = self.parts.get("localbrain")
        return lane.status_text() if lane else "The local brain part isn't running."

    def _changed(self, key, value):
        if key == "voice_device":
            config.VOICE_DEVICE = str(value)
            if gpu.needs_voice_test():
                threading.Thread(target=self._voice_test_later, args=(0,), daemon=True, name="voice-gpu-test").start()
            else:
                self._rebuild_voice()
        elif key == "hearing_device":
            self.core.emit({"type": "toast", "text": "Hearing switches over the next time he starts."})
        elif key in ("languages", "language"):
            self.core.emit({"type": "toast", "text": "His replies follow straight away; hearing switches to the "
                                                     "new language the next time he starts."})
        elif key == "safety":
            try:
                import permissions
                permissions.apply_preset(value)
            except Exception as e:
                print(f"[extras] safety: {e}")
        self.send_prefs()

    def set_option(self, key, value):
        """From the Options section or from him. Returns a sentence."""
        try:
            v = prefs.set(key, value)
        except KeyError:
            return f"There's no option called {key}."
        except ValueError as e:
            return str(e)
        label = next((it["label"] for it in prefs.view() if it["key"] == key), key)
        if isinstance(v, bool):
            return f"{label}: {'on' if v else 'off'}."
        opt = next((o["label"] for it in prefs.view() if it["key"] == key for o in (it["options"] or []) if o["v"] == v), v)
        return f"{label}: {opt}."

    # ------------------------------------------------------------ graphics card
    def setup_hearing(self):
        """Download NVIDIA's libraries in the background, with progress in the Options section."""
        if gpu.cuda_libs_downloaded():
            return "The graphics card libraries are already here. If hearing still runs on the processor, the card failed its test (the log says why)."
        card = gpu.nvidia_card()
        if not card:
            return "There's no NVIDIA graphics card (or its driver isn't installed), so hearing stays on the processor."

        def run():
            last = [0.0]

            def progress(step, pct):
                if time.time() - last[0] > 0.5 or pct >= 100:
                    last[0] = time.time()
                    self.core.emit({"type": "gpu_progress", "step": step, "pct": pct})

            ok, msg = gpu.download_cuda(progress)
            self.core.emit({"type": "gpu_progress", "step": msg, "pct": 100 if ok else -1, "done": True})
            self.core.emit({"type": "toast", "text": msg})
            if ok and prefs.get("hearing_device") == "cpu":
                prefs.set("hearing_device", "auto")
            self.send_prefs()

        threading.Thread(target=run, daemon=True, name="gpu-download").start()
        return (f"Downloading NVIDIA's libraries for your {card} (about 1.2 GB, once). Progress is in the System "
                f"panel under Options. When it's done, restart me and I'll test the card.")

    def remove_hearing_libs(self):
        gpu.remove_cuda()
        self.send_prefs()
        return "Removed the graphics card libraries. Hearing goes back to the processor next start."

    def retest_voice(self):
        gpu.forget_voice_test()
        if not gpu.dml_available():
            return "This build can't run the voice on a graphics card (DirectML is missing)."
        threading.Thread(target=self._voice_test_later, args=(0,), daemon=True, name="voice-gpu-test").start()
        return "Testing my voice on the graphics card. Takes about half a minute."

    def _voice_test_later(self, delay):
        if delay and self._stop.wait(delay):
            return
        # wait for a quiet moment: the test makes the processor busy for a few seconds
        for _ in range(60):
            if self.core.state in ("idle", "standby", "sleeping"):
                break
            if self._stop.wait(5):
                return
        res = gpu.run_voice_test(log=print)
        self._rebuild_voice()
        self.core.emit({"type": "toast", "text": "Voice on the graphics card: " + res.get("note", "")})
        self.send_prefs()

    def _rebuild_voice(self):
        try:
            where = self.core.speaker.rebuild_voice()
            print(f"[voice] voice now runs on the {'graphics card' if where == 'gpu' else 'processor'}")
        except Exception as e:
            print(f"[voice] couldn't switch: {e}")
        self.send_prefs()

    def gpu_text(self):
        s = gpu.status()
        hear = {"cuda": "the graphics card", "cpu": "the processor"}.get(s["hearing_on"], "nothing yet (hearing hasn't started)")
        voice = {"gpu": "graphics card", "cpu": "processor"}.get(s["voice_on"], "processor")
        bits = [f"Graphics card: {s['card'] or 'no NVIDIA card found'}.",
                f"Hearing runs on {hear} (setting: {s['hearing_setting']}).",
                f"NVIDIA libraries for hearing: {'downloaded' if s['cuda_libs'] else 'not downloaded'}.",
                f"My voice runs on the {voice} (setting: {s['voice_setting']})."]
        if s["voice_gpu_note"]:
            bits.append(f"Voice test: {s['voice_gpu_note']}")
        if s["download"]["busy"]:
            bits.append(f"Downloading: {s['download']['step']} {s['download']['pct']}%.")
        return " ".join(bits)
