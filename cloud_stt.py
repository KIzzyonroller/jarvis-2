"""
Cloud speech recognition (Groq). Optional; used when GROQ_API_KEY is in .env.

Only the careful "what exactly did you say to him" pass goes to the cloud, and only
for sentences already aimed at Jarvis/Ultron. Catching his name and
everything else still happens on your PC, so background talk, videos and calls never
leave it. If the cloud is slow, down, out of free quota or the key is wrong, he falls
back to local recognition automatically.

Groq runs Whisper large-v3-turbo on fast hardware: typically a few hundred milliseconds
per sentence, and more accurate than the models that fit on a normal CPU.
Pricing (Oct 2026): $0.04 per hour of audio, each request billed as at least 10 seconds,
so roughly a cent per hundred requests. There has been a free tier with rate limits.
"""
import io
import threading
import time
import wave

import numpy as np

import config

URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODELS_URL = "https://api.groq.com/openai/v1/models"


def _wav_bytes(audio):
    pcm = (np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0) * 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm.tobytes())
    return buf.getvalue()


class CloudSTT:
    def __init__(self, key=None, model=None, log=print):
        self.key = (key if key is not None else config.GROQ_API_KEY).strip()
        self.model = model or config.CLOUD_STT_MODEL
        self.log = log
        self.off_until = 0.0
        self.dead = False                 # bad key: don't keep trying this session
        self.fails = 0
        self.last_net = 0.0
        self.last_secs = None
        self._session = None
        self._lock = threading.Lock()

    @property
    def configured(self):
        return bool(self.key) and "paste" not in self.key.lower()

    @property
    def available(self):
        return self.configured and not self.dead and time.time() >= self.off_until

    def _s(self):
        with self._lock:
            if self._session is None:
                import requests
                s = requests.Session()
                s.headers["Authorization"] = f"Bearer {self.key}"
                self._session = s
            return self._session

    def warm(self):
        """Open the connection while you're still talking (free, no audio sent)."""
        if not self.available or time.time() - self.last_net < 25:
            return
        self.last_net = time.time()

        def go():
            try:
                self._s().get(MODELS_URL, timeout=5)
            except Exception:
                pass
        threading.Thread(target=go, daemon=True, name="stt-warm").start()

    def _pause(self, secs, why):
        self.off_until = time.time() + secs
        self.log(f"[cloud speech] {why}; using local recognition for {int(secs)}s")

    def transcribe(self, audio, prompt=""):
        """Returns the text, or None if the cloud couldn't do it (caller falls back to local)."""
        if not self.available:
            return None
        t0 = time.time()
        try:
            r = self._s().post(URL, timeout=(2.5, 4),       # Groq normally answers in well under a second
                               files={"file": ("speech.wav", _wav_bytes(audio), "audio/wav")},
                               data={"model": self.model, "language": "en", "temperature": "0",
                                     "response_format": "json", "prompt": (prompt or "")[-600:]})
        except Exception as e:
            self.fails += 1
            self._pause(30, f"no answer ({type(e).__name__})")   # don't make you wait on it twice
            return None
        self.last_net = time.time()
        if r.status_code == 200:
            self.fails = 0
            self.last_secs = time.time() - t0
            try:
                import usage
                usage.record_groq(len(audio) / 16000)
            except Exception:
                pass
            try:
                return (r.json().get("text") or "").strip()
            except ValueError:
                return r.text.strip()
        if r.status_code in (401, 403):
            self.dead = True
            self.log("[cloud speech] Groq rejected the key (check GROQ_API_KEY in .env); using local recognition")
            return None
        if r.status_code == 429:
            try:
                wait = float(r.headers.get("retry-after", "60"))
            except ValueError:
                wait = 60
            self._pause(max(10, min(wait, 3600)), "hit Groq's rate limit")
            return None
        self.fails += 1
        if self.fails >= 2 or r.status_code >= 500:
            self._pause(30, f"Groq error {r.status_code}")
        return None
