"""
His voice into your mic (the "Speak into my mic" option), so Discord, games and calls hear him.

Windows has no built-in way to play sound into a microphone, so this uses VB-CABLE (free, vb-audio.com/Cable):
it adds a playback device called "CABLE Input" and a microphone called "CABLE Output". He plays his voice into
CABLE Input, and in Discord (or the game) you pick CABLE Output as the microphone. That mic carries only him: to be
heard as well, mix your real mic and the cable into one with VB-Audio's free Voicemeeter.

Every block his normal voice output plays is copied here (voice._Output.TAP), resampled to 48 kHz and played into
the cable, so the timing matches what you hear. Nothing else of yours goes into it.
"""
import queue
import threading

import numpy as np

import prefs

OUT_SR = 48000


class Router:
    def __init__(self, core):
        self.core = core
        self.stream = None
        self.q = queue.Queue(maxsize=200)
        self.lock = threading.Lock()
        self.device = None
        self.carry = np.zeros(0, dtype=np.float32)

    def start(self):
        for k in ("mic_voice", "mic_device", "mic_also_speakers"):
            prefs.on_change(k, lambda key, v: threading.Thread(target=self.apply, daemon=True).start())
        self.apply(quiet=True)
        return self

    def stop(self):
        self._close()

    # ------------------------------------------------------------ device
    def find(self, name):
        import sounddevice as sd
        want = (name or "CABLE Input").lower()
        apis = {i: a["name"] for i, a in enumerate(sd.query_hostapis())}
        best = None
        for i, d in enumerate(sd.query_devices()):
            if d["max_output_channels"] < 1 or want not in d["name"].lower():
                continue
            api = apis.get(d["hostapi"], "")
            rank = 0 if "MME" in api else 1 if "DirectSound" in api else 2      # MME resamples for us; WASAPI is picky
            if best is None or rank < best[0]:
                best = (rank, i, d["name"])
        return best

    def apply(self, quiet=False):
        import voice
        with self.lock:
            self._close()
            if not prefs.get("mic_voice"):
                return
            try:
                hit = self.find(prefs.get("mic_device"))
            except Exception as e:
                hit = None
                print(f"[mic voice] {e}")
            if not hit:
                if not quiet:
                    self.core.emit({"type": "toast", "text": f"No playback device called \"{prefs.get('mic_device')}\". "
                                    "Install VB-CABLE (free, vb-audio.com/Cable) and restart the PC, then switch this on again."})
                return
            import sounddevice as sd
            try:
                self.stream = sd.OutputStream(device=hit[1], samplerate=OUT_SR, channels=1, dtype="float32",
                                              blocksize=960, callback=self._cb)
                self.stream.start()
            except Exception as e:
                self.stream = None
                self.core.emit({"type": "toast", "text": f"Couldn't open {hit[2]}: {e}"})
                return
            self.device = hit[2]
            voice._Output.TAP = self._tap
            voice._Output.MUTE_SPEAKERS = not prefs.get("mic_also_speakers")
            print(f"[mic voice] playing his voice into {hit[2]}")
            if not quiet:
                self.core.emit({"type": "toast", "text": f"His voice now also goes into {hit[2]}. Pick \"CABLE Output\" "
                                                         "as the microphone in Discord or the game."})

    def _close(self):
        import voice
        voice._Output.TAP = None
        voice._Output.MUTE_SPEAKERS = False
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
        self.stream = None
        while not self.q.empty():
            try:
                self.q.get_nowait()
            except queue.Empty:
                break

    # ------------------------------------------------------------ audio
    def _tap(self, block24):
        """Called from his speaker stream's callback: 24 kHz in, 48 kHz out (simple doubling with averaging)."""
        if not np.any(block24):
            return
        up = np.repeat(block24, 2)
        up[1:-1:2] = (block24[:-1] + block24[1:]) / 2         # linear in-between samples
        try:
            self.q.put_nowait(up.astype(np.float32))
        except queue.Full:
            pass

    def _cb(self, outdata, frames, t, status):
        out = self.carry
        while len(out) < frames:
            try:
                out = np.concatenate([out, self.q.get_nowait()])
            except queue.Empty:
                break
        if len(out) >= frames:
            outdata[:, 0] = out[:frames]
            self.carry = out[frames:]
        else:
            outdata[:, 0] = 0
            outdata[:len(out), 0] = out
            self.carry = np.zeros(0, dtype=np.float32)
