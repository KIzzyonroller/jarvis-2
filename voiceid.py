"""
Voice lock: only respond to YOUR voice.

A small speaker-recognition network (NVIDIA TitaNet-small, ~39 MB, runs on the
CPU in a few tens of milliseconds) turns a sentence into a 192-number
"voiceprint". You train it once by talking for about 20 seconds; after that
every sentence is compared against your print and anyone else (the TV, a
Discord call, your friends, Jarvis's own voice coming out of the speakers)
is ignored before it's even transcribed.

Your voiceprint is stored only on this PC (Documents/Jarvis/voiceprint.json).
It's a list of numbers, not a recording; it can't be turned back into audio.
"""
import json
import threading
import time

import numpy as np

import config

MODEL_NAME = "nemo_en_titanet_small.onnx"
ENROLL_SECONDS = 20.0      # of actual speech
DEFAULT_THRESHOLD = 0.45   # cosine similarity; recalibrated from your own enrollment


def _norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


class VoiceID:
    def __init__(self, log=print):
        self.log = log
        self.ex = None
        self.print = None
        self.threshold = DEFAULT_THRESHOLD
        self.enabled = config.VOICE_LOCK
        self.lock = threading.Lock()
        self._enroll = None             # {"embs": [], "secs": float} while learning
        self._last_ok = 0.0
        self.path = config.JARVIS_DIR / "voiceprint.json"
        self._load_model()
        self._load_print()

    # ------------------------------------------------------------------ setup
    def _load_model(self):
        path = config.MODELS_DIR / MODEL_NAME
        if not path.exists():
            self.log("VOICE LOCK UNAVAILABLE: speaker model not downloaded (run setup.bat)")
            return
        try:
            import sherpa_onnx
            cfg = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(path), num_threads=2)
            self.ex = sherpa_onnx.SpeakerEmbeddingExtractor(cfg)
        except Exception as e:
            self.log(f"VOICE LOCK UNAVAILABLE: {type(e).__name__}: {e}")
            self.ex = None

    def _load_print(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            self.print = _norm(d["embedding"])
            self.threshold = float(d.get("threshold", DEFAULT_THRESHOLD))
            if "enabled" in d:
                self.enabled = bool(d["enabled"]) and config.VOICE_LOCK
        except Exception:
            self.print = None

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({
            "embedding": [round(float(x), 6) for x in self.print], "threshold": round(self.threshold, 3),
            "enabled": self.enabled, "updated": time.strftime("%Y-%m-%d %H:%M"),
        }), encoding="utf-8")

    @property
    def available(self):
        return self.ex is not None

    @property
    def enrolled(self):
        return self.print is not None

    @property
    def active(self):
        """Actually filtering right now."""
        return self.available and self.enrolled and self.enabled and self._enroll is None

    # ------------------------------------------------------------------ core
    def embed(self, audio):
        if not self.ex or len(audio) < 16000 * 0.4:
            return None
        s = self.ex.create_stream()
        s.accept_waveform(sample_rate=16000, waveform=np.asarray(audio, dtype=np.float32))
        s.input_finished()
        return _norm(self.ex.compute(s))

    def check(self, audio, voiced_secs=None):
        """Returns (is_you, score). Short clips ("Jarvis.") carry less voice information, so
        right after you've been recognised they get a little more benefit of the doubt."""
        if not self.active:
            return True, None
        emb = self.embed(audio)
        if emb is None:                                 # too short to tell
            return time.time() - self._last_ok < 30, None
        score = float(np.dot(emb, self.print))
        secs = voiced_secs if voiced_secs is not None else len(audio) / 16000
        thr = self.threshold
        if secs < 1.2:
            thr -= 0.10 if time.time() - self._last_ok < 30 else 0.06
        ok = score >= thr
        if ok:
            self._last_ok = time.time()
            if score >= self.threshold + 0.12 and secs >= 1.5:     # confidently you: adapt slowly (new mic, a cold)
                with self.lock:
                    self.print = _norm(0.97 * self.print + 0.03 * emb)
        return ok, score

    # ------------------------------------------------------------------ enrollment
    def start_enroll(self):
        if not self.available:
            return False
        self._enroll = {"embs": [], "secs": 0.0}
        return True

    def cancel_enroll(self):
        self._enroll = None

    @property
    def enrolling(self):
        return self._enroll is not None

    def add_sample(self, audio, voiced_secs):
        """Feed one sentence while learning. Returns progress 0..1 (1 = done and saved)."""
        e = self._enroll
        if e is None:
            return 1.0
        if voiced_secs >= 0.8:
            emb = self.embed(audio)
            if emb is not None:
                e["embs"].append(emb)
                e["secs"] += voiced_secs
        prog = min(1.0, e["secs"] / ENROLL_SECONDS)
        if prog >= 1.0 and len(e["embs"]) >= 4:
            self._finish_enroll()
            return 1.0
        return min(prog, 0.95)

    def _finish_enroll(self):
        embs = np.stack(self._enroll["embs"])
        center = _norm(embs.mean(axis=0))
        sims = embs @ center
        # Threshold from YOUR consistency: well below your typical score, never silly-low or silly-high.
        self.threshold = float(np.clip(np.percentile(sims, 10) - 0.25, 0.40, 0.50))
        self.print = center
        self.enabled = True
        self._enroll = None
        self._last_ok = time.time()
        self._save()
        self.log(f"[voice lock] learned your voice from {len(embs)} sentences; threshold {self.threshold:.2f}")

    def set_enabled(self, on):
        self.enabled = bool(on)
        if self.enrolled:
            self._save()

    def forget(self):
        self.print = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
