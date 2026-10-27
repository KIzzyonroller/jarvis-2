"""
Jarvis's voice.

Engines (first one that works wins, the rest are fallbacks):
  kokoro      free, local, natural-sounding neural voice (default)
  elevenlabs  the most human-sounding; paid, needs ELEVENLABS_API_KEY
  edge        Microsoft neural voice over the internet, free
  sapi        the built-in Windows voice; robotic but always there

SpeechStream speaks text AS IT ARRIVES: text is cut into sentences, the
next sentence is synthesized while the current one plays, so Jarvis starts
talking about a second after Claude writes his first sentence.
"""
import asyncio
import os
import queue
import re
import sys
import tempfile
import threading
import time
import wave

import numpy as np

import config

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


# =================================================================== text prep
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F2FF]")
_REPLACE = [
    (r"°\s?C\b", " degrees Celsius"), (r"°\s?F\b", " degrees Fahrenheit"), (r"°", " degrees"),
    (r"(\d)\s?%", r"\1 percent"), (r"\s&\s", " and "), (r"\be\.g\.", "for example"),
    (r"\bi\.e\.", "that is"), (r"\betc\.", "and so on"), (r"(\d)\s?km/h\b", r"\1 kilometres per hour"),
    (r"(\d)\s?mph\b", r"\1 miles per hour"), (r"\s?(->|→)\s?", " to "), (r"~\s?(\d)", r"about \1"),
    (r"\bvs\.?\s", "versus "), (r"(\d)\s?GB\b", r"\1 gigabytes"), (r"(\d)\s?MB\b", r"\1 megabytes"),
]


def _money(m):
    d, c = m.group(1), m.group(2)
    out = f"{d} dollar" + ("" if d == "1" else "s")
    if c and int(c):
        out += f" {int(c)} cent" + ("" if int(c) == 1 else "s")
    return out


def _decimal(m):
    whole, frac = m.group(1), m.group(2)
    return f"{whole} point {' '.join(frac)}"      # 4.5 -> four point five, 3.14 -> three point one four


def speak_numbers(text):
    """Say numbers the way people do. Some voices read "4.5" as "four five"."""
    text = re.sub(r"\$(\d[\d,]*)(?:\.(\d\d))?\b", _money, text)
    text = re.sub(r"\b(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})\b", lambda m: " dot ".join(m.groups()), text)   # IP addresses
    text = re.sub(r"(?<![\w.])-(?=\d)", "minus ", text)                                   # -4.5 degrees
    while True:                                                                        # also 2.3.1 versions
        new = re.sub(r"(?<![\d.])(\d[\d,]*)\.(\d+)", _decimal, text)
        new = re.sub(r"(\d) point ([\d ]+?)\.(\d+)", lambda m: f"{m.group(1)} point {m.group(2)} point {' '.join(m.group(3))}", new)
        if new == text:
            return re.sub(r"(\d point [\d ]*\d)\s?/\s?(\d+)\b", r"\1 out of \2", text)     # rated 4.5/5
        text = new


def clean_for_speech(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "the link", text)
    text = re.sub(r"^\s*([-*•]|\d+\.)\s+", "", text, flags=re.M)
    text = re.sub(r"[*_#`>|]", "", text)
    text = _EMOJI.sub("", text)
    for pat, rep in _REPLACE:
        text = re.sub(pat, rep, text, flags=re.I)
    text = speak_numbers(text)
    return re.sub(r"\s+", " ", text).strip()


# =================================================================== audio container
class Audio:
    """Either PCM samples in memory, or an audio file on disk."""

    def __init__(self, pcm=None, sr=None, path=None, temp=False):
        self.pcm, self.sr, self.path, self.temp = pcm, sr, path, temp

    def discard(self):
        if self.temp and self.path:
            try:
                os.remove(self.path)
            except OSError:
                pass


def _com_init():
    if sys.platform == "win32":
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass


# =================================================================== effects
def ultron_fx(x, sr, pitch=0.84):
    """Lower, metallic, slightly synthetic. Pitch-down by resampling (which also
    slows speech, so Ultron is synthesized a bit faster to compensate)."""
    x = np.asarray(x, dtype=np.float32)
    n = int(len(x) / pitch)
    x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    y = x.copy()
    for ms, g in ((7.0, .42), (12.5, .28)):          # short comb delays = metallic ring
        d = int(sr * ms / 1000)
        y[d:] += g * x[:-d]
    t = np.arange(len(y)) / sr
    y = 0.82 * y + 0.18 * y * np.sin(2 * np.pi * 42 * t)   # a touch of ring modulation
    y = np.tanh(1.8 * y) / np.tanh(1.8)
    peak = float(np.max(np.abs(y))) if len(y) else 0
    return (y * (0.9 / peak) if peak > 0 else y).astype(np.float32)


EFFECTS = {"ultron": ultron_fx}


def pitch_shift(x, pitch):
    """Deeper (< 1) or higher (> 1) by resampling. That also changes the pace, so the voice is generated at
    a matching speed first (see synth) and comes out at its normal speed."""
    if not pitch or abs(pitch - 1.0) < 0.01 or not len(x):
        return x
    n = int(len(x) / pitch)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


DEFAULT_PERSONA = {"voice": config.KOKORO_VOICE, "lang": config.KOKORO_LANG, "speed": config.KOKORO_SPEED,
                   "effect": None, "edge_voice": config.TTS_VOICE, "eleven_voice": config.ELEVENLABS_VOICE_ID,
                   "pitch": 1.0}


# =================================================================== engines
def make_kokoro(model, voices):
    """Kokoro pinned to the CPU. Left alone, kokoro-onnx grabs any GPU provider it finds, and on many
    graphics cards (DirectML) one of its layers fails ("ConvTranspose ... The parameter is incorrect"),
    which leaves him with no voice. The CPU is plenty fast for it."""
    os.environ.setdefault("ONNX_PROVIDER", "CPUExecutionProvider")      # older kokoro-onnx versions read this
    from kokoro_onnx import Kokoro
    try:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        # Less spiky: a few cores instead of all of them, and the worker threads sleep between sentences
        # instead of spinning (spinning keeps cores busy doing nothing and is most of the spike you see).
        n = voice_threads()
        if n > 0:
            opts.intra_op_num_threads = n
        opts.inter_op_num_threads = 1
        opts.add_session_config_entry("session.intra_op.allow_spinning", "0")
        opts.add_session_config_entry("session.inter_op.allow_spinning", "0")
        sess = ort.InferenceSession(str(model), sess_options=opts, providers=["CPUExecutionProvider"])
        if hasattr(Kokoro, "from_session"):
            return Kokoro.from_session(sess, str(voices))
    except Exception as e:
        print(f"[tts] couldn't pin the voice to the CPU ({e}); using the library default")
    return Kokoro(str(model), str(voices))


def voice_threads():
    n = getattr(config, "KOKORO_THREADS", -1)
    if n >= 0:
        return n
    return max(2, min(4, (os.cpu_count() or 4) // 2))


_SYNTH_LOCK = threading.Lock()     # one voice at a time (both AIs at once would double the spike)


def _kokoro_model_name():
    """Full or compressed (int8) Kokoro. Which is faster depends on the CPU, so setup.bat times both on
    YOUR PC and writes the winner to models/kokoro_pick.txt. JARVIS_KOKORO=full/lite overrides."""
    full, lite = "kokoro-v1.0.onnx", "kokoro-v1.0.int8.onnx"
    want = config.KOKORO_MODEL
    if want == "auto":
        try:
            want = (config.MODELS_DIR / "kokoro_pick.txt").read_text(encoding="utf-8").strip()
        except Exception:
            want = "full"
    if want == "lite" and (config.MODELS_DIR / lite).exists():
        return lite
    return full


def _lang_for(voice, lang):
    """American voices (a*_) read with American pronunciation, British (b*_) with British."""
    return {"a": "en-us", "b": "en-gb"}.get((voice or "x")[0], lang)


class KokoroEngine:
    name = "kokoro"

    def __init__(self):
        from kokoro_onnx import Kokoro
        model = config.MODELS_DIR / _kokoro_model_name()
        voices = config.MODELS_DIR / "voices-v1.0.bin"
        if not model.exists() or not voices.exists():
            raise FileNotFoundError("Kokoro voice model not downloaded yet" + (" (it downloads on first start)" if config.FROZEN else " (run setup.bat)"))
        self.k = make_kokoro(model, voices)
        self.available = set(self.k.get_voices())
        self._warned = set()

    def synth(self, text, p):
        voice = p["voice"]
        if voice not in self.available:
            if voice not in self._warned:
                self._warned.add(voice)
                print(f"[tts] voice {voice} not found. Options: {', '.join(sorted(self.available))}")
            voice = "bm_george"
        pitch = float(p.get("pitch") or 1.0)
        speed = min(max(float(p["speed"]) / pitch, 0.5), 2.0)
        with _SYNTH_LOCK:
            samples, sr = self.k.create(text, voice=voice, speed=speed, lang=_lang_for(voice, p["lang"]))
        pcm = np.asarray(samples, dtype=np.float32)
        peak = float(np.max(np.abs(pcm))) if len(pcm) else 0.0
        if peak > 0.95:                      # some voices overshoot full scale and would crackle
            pcm *= 0.95 / peak
        pcm = pitch_shift(pcm, pitch)
        fx = EFFECTS.get(p.get("effect") or "")
        return Audio(pcm=fx(pcm, sr) if fx else pcm, sr=sr)


class ElevenLabsEngine:
    name = "elevenlabs"
    URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"

    def __init__(self):
        if not config.ELEVENLABS_API_KEY:
            raise RuntimeError("no ELEVENLABS_API_KEY in .env")
        import requests
        self.session = requests.Session()
        self.session.headers.update({"xi-api-key": config.ELEVENLABS_API_KEY, "Content-Type": "application/json"})
        self.pcm_ok = True

    def synth(self, text, p):
        body = {"text": text, "model_id": config.ELEVENLABS_MODEL}
        url = self.URL.format(voice=p.get("eleven_voice") or config.ELEVENLABS_VOICE_ID)
        if self.pcm_ok:
            r = self.session.post(url, params={"output_format": "pcm_24000"}, json=body, timeout=30)
            if r.status_code == 200:
                pcm = np.frombuffer(r.content, dtype="<i2").astype(np.float32) / 32768.0
                fx = EFFECTS.get(p.get("effect") or "")
                return Audio(pcm=fx(pcm, 24000) if fx else pcm, sr=24000)
            if r.status_code in (400, 403, 422) and "format" in r.text.lower():
                self.pcm_ok = False   # plan doesn't allow PCM; use the default mp3
            else:
                raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:200]}")
        r = self.session.post(url, json=body, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:200]}")
        fd, path = tempfile.mkstemp(suffix=".mp3")
        with os.fdopen(fd, "wb") as f:
            f.write(r.content)
        return Audio(path=path, temp=True)


class EdgeEngine:
    name = "edge"

    def __init__(self):
        import edge_tts  # noqa: F401  (just checking it's installed)

    def synth(self, text, p, path=None):
        import edge_tts
        temp = path is None
        if temp:
            fd, path = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
        hz = (-12 if p.get("effect") == "ultron" else 0) + round((float(p.get("pitch") or 1.0) - 1.0) * 120)
        rate = round((float(p.get("speed") or 1.05) - 1.0) * 100) + 3      # his normal 1.05 ~ Edge's +8%
        asyncio.run(edge_tts.Communicate(text, p.get("edge_voice") or config.TTS_VOICE,
                                         rate=f"{rate:+d}%", pitch=f"{hz:+d}Hz").save(str(path)))
        return Audio(path=str(path), temp=temp)


class SapiEngine:
    name = "sapi"

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("Windows only")
        import pyttsx3  # noqa: F401

    def synth(self, text, p):
        _com_init()
        import pyttsx3
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        engine = pyttsx3.init()
        engine.save_to_file(text, path)
        engine.runAndWait()
        engine.stop()
        with wave.open(path, "rb") as w:
            sr, n, width = w.getframerate(), w.getnframes(), w.getsampwidth()
            raw = w.readframes(n)
            ch = w.getnchannels()
        os.remove(path)
        pcm = np.frombuffer(raw, dtype="<i2" if width == 2 else np.uint8).astype(np.float32)
        pcm = pcm / 32768.0 if width == 2 else (pcm - 128) / 128.0
        if ch > 1:
            pcm = pcm.reshape(-1, ch).mean(axis=1)
        return Audio(pcm=pcm, sr=sr)


ENGINES = {"kokoro": KokoroEngine, "elevenlabs": ElevenLabsEngine, "edge": EdgeEngine, "sapi": SapiEngine}


# =================================================================== speaker
class Speaker:
    """
    on_state(s): 'speaking' when audio starts, 'waiting' when the queue runs dry
                 mid-answer, 'done' when a stream is finished
    on_level(v): real loudness of the voice 0..1 while speaking
    on_sentence(text): the sentence currently being spoken
    """

    def __init__(self, enabled=True, on_state=None, on_level=None, on_sentence=None):
        self.enabled = enabled
        self.on_state = on_state or (lambda s: None)
        self.on_level = on_level or (lambda v: None)
        # on_envelope(levels, step_secs, delay_secs): the whole sentence's loudness, sent once as it starts
        # playing, so the HUD can animate in perfect sync at full frame rate. Empty list = stopped early.
        self.on_envelope = lambda env, step, delay: None
        self.on_sentence = on_sentence or (lambda t: None)
        self.engines = []
        self.play_lock = threading.Lock()
        self._pygame = None
        self._stop_now = threading.Event()
        self.active = None
        self.streams = set()          # every stream still talking (two at once in a duo turn)
        self.wait_user = lambda: False  # set by the core: True while you're talking
        self._out = None              # one output stream kept open, so the echo canceller knows what was played
        self._out_failed = not config.ECHO_CANCEL
        self.persona = dict(DEFAULT_PERSONA)
        self.who = None               # name of whoever the next stream speaks as (for the HUD)

    def set_persona(self, p):
        """p: a dict from personas.PERSONAS (voice, lang, speed, effect, edge_voice, eleven_voice)."""
        self.persona = {**DEFAULT_PERSONA, **{k: p[k] for k in DEFAULT_PERSONA if k in p}}
        self.who = p.get("name")

    # ---- setup
    def prepare(self, log=print):
        """Load the voice engines. Slow-ish (Kokoro takes a second or two), so call off the UI thread."""
        if not self.enabled:
            return
        order = [config.TTS_ENGINE] + [e for e in ("kokoro", "edge", "sapi") if e != config.TTS_ENGINE]
        for name in order:
            cls = ENGINES.get(name)
            if not cls:
                continue
            try:
                self.engines.append(cls())
            except Exception as e:
                if name == config.TTS_ENGINE:
                    log(f"VOICE ENGINE '{name.upper()}' UNAVAILABLE: {e}")
        try:
            import pygame
            pygame.mixer.init()
            self._pygame = pygame
        except Exception as e:
            print(f"[tts] pygame unavailable ({e}); mp3 voices disabled")
            self.engines = [e for e in self.engines if e.name not in ("edge",)]

    def add_kokoro(self):
        """The voice model just finished downloading: start using it without a restart."""
        if any(e.name == "kokoro" for e in self.engines):
            return True
        try:
            eng = KokoroEngine()
        except Exception as e:
            print(f"[tts] Kokoro still unavailable: {e}")
            return False
        if config.TTS_ENGINE == "kokoro":
            self.engines.insert(0, eng)
        else:
            self.engines.append(eng)
        return True

    @property
    def engine_name(self):
        return self.engines[0].name if self.engines else "none"

    # ---- synthesis with fallback
    SYNTH_TIMEOUT = 25

    def _synth_timed(self, eng, text, p):
        """A voice engine that hangs (driver trouble, network stall) must not freeze him mid-answer."""
        box = {}

        def run():
            try:
                box["out"] = eng.synth(text, p)
            except Exception as e:
                box["err"] = e
        t = threading.Thread(target=run, daemon=True, name="tts-call")
        t.start()
        t.join(self.SYNTH_TIMEOUT)
        if t.is_alive():
            raise TimeoutError(f"took longer than {self.SYNTH_TIMEOUT}s")
        if "err" in box:
            raise box["err"]
        return box.get("out")

    # ---- phrase cache: short lines he says a lot ("Done.", "Opening Spotify.", "Volume 30.") are
    # generated once and replayed, from memory or from disk, with zero synthesis delay.
    PHRASE_MAX_WORDS = 8

    def _phrase_key(self, text, p):
        import hashlib
        eng = self.engines[0].name if self.engines else "none"
        raw = "|".join(str(x) for x in (eng, p.get("voice"), p.get("speed"), p.get("lang"), p.get("effect"), p.get("pitch"),
                                        p.get("edge_voice"), p.get("eleven_voice"), text.strip()))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]

    def _phrase_get(self, key):
        mem = self.__dict__.setdefault("_phrases", {})
        if key in mem:
            return mem[key]
        try:
            f = config.CACHE_DIR / "phrases" / f"{key}.npz"
            if f.exists():
                z = np.load(f)
                a = Audio(pcm=z["pcm"].astype(np.float32), sr=int(z["sr"]))
                mem[key] = a
                return a
        except Exception:
            pass
        return None

    def _phrase_put(self, key, audio):
        if audio is None or getattr(audio, "pcm", None) is None or getattr(audio, "temp", False):
            return                                  # only in-memory PCM is reusable (not temp mp3 files)
        mem = self.__dict__.setdefault("_phrases", {})
        if len(mem) > 400:
            mem.pop(next(iter(mem)))
        mem[key] = audio
        try:
            d = config.CACHE_DIR / "phrases"
            d.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(d / f"{key}.npz", pcm=audio.pcm.astype(np.float32), sr=np.int32(audio.sr))
        except Exception:
            pass

    def warm_phrases(self, items, stop=None, busy=None):
        """Pre-generate (text, persona) pairs in the background so they're instant later. Only while
        nothing else is happening: this must never slow down him hearing or answering you."""
        busy = busy or (lambda: False)
        for text, p in items:
            if stop is not None and stop.is_set():
                return
            full = {**DEFAULT_PERSONA, **{k: p[k] for k in DEFAULT_PERSONA if k in p}}
            if self._phrase_get(self._phrase_key(text, full)) is not None:
                continue
            quiet_since = time.time()
            while time.time() - quiet_since < 1.5:      # wait for 1.5 s of nothing going on
                if stop is not None and stop.is_set():
                    return
                if busy() or self.streams:
                    quiet_since = time.time()
                time.sleep(0.1)
            self.synth(text, full)

    def synth(self, text, persona=None):
        p = persona or self.persona
        short = len(text.split()) <= self.PHRASE_MAX_WORDS
        key = self._phrase_key(text, p) if short and self.engines else None
        if key:
            hit = self._phrase_get(key)
            if hit is not None:
                return hit
        for eng in list(self.engines):
            try:
                out = self._synth_timed(eng, text, p)
            except Exception as e:
                print(f"[tts] {eng.name} failed: {e}")
                if len(self.engines) > 1:
                    self.engines.remove(eng)   # stop retrying a broken engine every sentence
                    print(f"[tts] switching to {self.engines[0].name}")
                continue
            if key and self.engines and eng is self.engines[0]:
                try:
                    self._phrase_put(key, out)
                except Exception as e:      # a caching hiccup must never cost him his voice
                    print(f"[tts] couldn't cache '{text}': {e}")
            return out
        return None

    def cache(self, text, path=None):
        """Synthesize once and keep (used for the instant 'Yes?')."""
        if not self.engines:
            return None
        eng = self.engines[0]
        try:
            if eng.name == "edge" and path:
                if not os.path.exists(path):
                    eng.synth(text, self.persona, path=path)
                return Audio(path=str(path))
            return eng.synth(text, self.persona)
        except Exception as e:
            print(f"[tts] couldn't cache '{text}': {e}")
            return None

    # ---- playback
    def play(self, audio):
        if audio is None:
            return
        with self.play_lock:
            self._stop_now.clear()
            try:
                if audio.pcm is not None:
                    self._play_pcm(audio.pcm, audio.sr)
                elif audio.path and self._pygame:
                    self._play_file(audio.path)
            except Exception as e:
                print(f"[tts] playback failed: {e}")
            finally:
                if audio.temp:
                    audio.discard()
                self.on_level(0.0)

    def _envelope(self, pcm, sr, delay):
        try:
            step = 0.02
            n = max(1, int(sr * step))
            x = np.asarray(pcm, dtype=np.float32).reshape(-1)
            k = len(x) // n
            if k == 0:
                return
            rms = np.sqrt(np.mean(x[:k * n].reshape(k, n) ** 2, axis=1)) * 5.0
            self.on_envelope([round(float(min(1.0, r)), 3) for r in rms], step, float(delay))
        except Exception as e:
            print(f"[tts] envelope failed: {e}")

    def _play_pcm(self, pcm, sr):
        if self._out is None and not self._out_failed:
            try:
                self._out = _Output()
            except Exception as e:
                self._out_failed = True
                print(f"[tts] steady output stream unavailable ({e}); echo cancelling is off")
        if self._out is not None:
            self._envelope(pcm, sr, min(0.25, getattr(self._out.stream, "latency", 0.05) or 0.05))
            self._out.play(pcm, sr, self._stop_now, self.on_level)
            if self._stop_now.is_set():
                self.on_envelope([], 0.02, 0.0)
            return
        import sounddevice as sd
        self._envelope(pcm, sr, 0.08)
        sd.play(pcm, sr)
        dur = len(pcm) / sr
        start = time.time()
        win = int(sr * 0.05)
        while True:
            t = time.time() - start
            if t >= dur or self._stop_now.is_set():
                break
            i = int(t * sr)
            seg = pcm[i:i + win]
            if len(seg):
                self.on_level(min(1.0, float(np.sqrt(np.mean(seg ** 2))) * 5.0))
            time.sleep(0.05)
        if self._stop_now.is_set():
            sd.stop()
            self.on_envelope([], 0.02, 0.0)
        else:
            sd.wait()

    def _play_file(self, path):
        m = self._pygame.mixer.music
        m.load(str(path))
        m.play()
        while m.get_busy() and not self._stop_now.is_set():
            self.on_level(0.35 + 0.3 * abs(np.sin(time.time() * 9)))
            time.sleep(0.05)
        m.stop()
        m.unload()

    def stop(self):
        """Shut up immediately (Esc in the app)."""
        for s in list(self.streams) + ([self.active] if self.active else []):
            s.cancel()
        self._stop_now.set()

    # ---- convenience
    def stream(self, max_words=None, after=None):
        """after: another stream that has to finish talking first. This one still
        synthesizes ahead in the meantime, so the hand-off has no gap."""
        s = SpeechStream(self, max_words=max_words, after=after)
        self.active = s
        if not s._dead:
            self.streams.add(s)
        return s

    def say(self, text):
        if not self.enabled or not clean_for_speech(text):
            return
        s = self.stream()
        s.feed(text)
        s.finish()
        s.wait()


# =================================================================== steady output (for echo cancelling)
class _Output:
    """One speaker stream that stays open for the whole session. Everything he says
    goes through it, and every block is also handed to the echo canceller with the
    exact moment it reaches the speakers. (A new stream per sentence would shift the
    timing every sentence and the canceller would have to start learning again.)"""
    SR = 24000

    def __init__(self):
        import sounddevice as sd
        import aec
        self.ref = aec.REF
        self.lock = threading.Lock()
        self.buf = None
        self.pos = 0
        self.stream = sd.OutputStream(samplerate=self.SR, channels=1, dtype="float32", blocksize=480,
                                      callback=self._cb)
        self.stream.start()

    def _cb(self, outdata, frames, t, status):
        out = np.zeros(frames, dtype=np.float32)
        with self.lock:
            if self.buf is not None:
                chunk = self.buf[self.pos:self.pos + frames]
                out[:len(chunk)] = chunk
                self.pos += len(chunk)
                if self.pos >= len(self.buf):
                    self.buf = None
        outdata[:, 0] = out
        dac = t.outputBufferDacTime or (t.currentTime + self.stream.latency)
        self.ref.write(dac, out, self.SR)

    def play(self, pcm, sr, stop, on_level):
        pcm = np.asarray(pcm, dtype=np.float32).reshape(-1)
        if sr != self.SR:
            n = int(len(pcm) * self.SR / sr)
            pcm = np.interp(np.arange(n) * (sr / self.SR), np.arange(len(pcm)), pcm).astype(np.float32)
        with self.lock:
            self.buf, self.pos = pcm, 0
        win = int(self.SR * 0.05)
        while True:
            with self.lock:
                if self.buf is not pcm:
                    break
                i = self.pos
            if stop.is_set():
                with self.lock:
                    if self.buf is pcm:
                        self.buf = None
                break
            seg = pcm[i:i + win]
            if len(seg):
                on_level(min(1.0, float(np.sqrt(np.mean(seg ** 2))) * 5.0))
            time.sleep(0.03)
        time.sleep(min(0.25, self.stream.latency))       # let the last block actually leave the speaker


# =================================================================== streaming
_SENT_END = re.compile(r"[.!?…]+[\"')\]]*\s+|\n+")
_NO_SPLIT_BEFORE = re.compile(r"(\b(mr|mrs|ms|dr|st|vs|no|approx|jr|sr|etc)|\be\.g|\bi\.e)\.\s+$", re.I)


class SpeechStream:
    AHEAD = 2           # sentences made ahead of the one playing
    def __init__(self, speaker, max_words=None, after=None):
        self.sp = speaker
        self.after = after
        self.persona = dict(speaker.persona)   # voice can't change mid-sentence if the persona switches
        self.who = speaker.who                 # ...and neither does who the HUD says is talking
        self.max_words = max_words
        self.words = 0
        self.truncated = False
        self.over = False                       # past the word budget: finishing the paragraph he's on
        self.spoken = []                        # sentences actually queued for speech (for echo filtering)
        self.buf = ""
        self.first = True
        self.sentences = queue.Queue()
        self.audio = queue.Queue(maxsize=4)
        self.finished = False
        self.cancelled = threading.Event()
        self.done = threading.Event()
        self._cv = threading.Condition()
        self._queued = 0
        self._played = 0
        if not speaker.enabled or not speaker.engines:
            self.done.set()
            self._dead = True
            return
        self._dead = False
        threading.Thread(target=self._synth_worker, daemon=True, name="tts-synth").start()
        threading.Thread(target=self._play_worker, daemon=True, name="tts-play").start()

    # ---- input
    def feed(self, text):
        if self._dead or self.cancelled.is_set() or self.finished:
            return
        self.buf += text
        self._split()

    def _split(self):
        while True:
            cut = None
            for m in _SENT_END.finditer(self.buf):
                if not _NO_SPLIT_BEFORE.search(self.buf[:m.end()]):
                    cut = m.end()
                    break
            if cut is None and self.first and len(self.buf) > 48:
                # get the first words out fast: break at a comma if there is one
                c = self.buf.rfind(", ", 18)
                cut = c + 2 if c > 0 else None
            if cut is None and len(self.buf) > 240:
                c = max(self.buf.rfind(", ", 0, 240), self.buf.rfind(" ", 0, 240))
                cut = c + 1 if c > 0 else 240
            if cut is None:
                return
            piece, self.buf = self.buf[:cut], self.buf[cut:]
            self._push(piece)

    def _push(self, piece):
        s = clean_for_speech(piece)
        if not re.search(r"\w", s):
            return
        # Word budget, not a sentence count: lots of short sentences (Ultron's style) shouldn't get cut.
        # Past the budget he keeps going to the end of the paragraph he's on (so he never stops mid-idea),
        # up to a hard ceiling; anything after that still shows in the app, it just isn't read out.
        if self.truncated:
            return
        if self.max_words is not None and self.words >= self.max_words:
            self.over = True
            if re.match(r"[ \t]*\n", piece) or self.words >= self.max_words * 1.6:
                self.truncated = True    # a new paragraph is a new idea: stop here
                return
        self.words += len(s.split())
        self.spoken.append(s)
        self.first = False
        with self._cv:
            self._queued += 1
        self.sentences.put(s)

    def _push_line(self, s):
        self.spoken.append(s)
        with self._cv:
            self._queued += 1
        self.sentences.put(s)

    def flush(self):
        """Speak whatever partial sentence is buffered."""
        if self.buf.strip():
            piece, self.buf = self.buf, ""
            self._push(piece)

    def finish(self):
        if self._dead or self.finished:
            return
        self.flush()
        if self.truncated and self.max_words and self.max_words >= 40 and not self.cancelled.is_set():
            self.truncated = False
            self._push_line("The rest is on screen.")
        self.finished = True
        self.sentences.put(None)

    def drain(self, timeout=60):
        """Block until everything queued so far has been spoken (stream stays open)."""
        self.flush()
        end = time.time() + timeout
        with self._cv:
            while self._played < self._queued and not self.cancelled.is_set() and not self.done.is_set():
                if not self._cv.wait(timeout=max(0.05, end - time.time())) and time.time() > end:
                    break

    def wait(self, timeout=None):
        self.done.wait(timeout)

    def cancel(self):
        self.cancelled.set()
        self.sp._stop_now.set()
        if not self.finished:
            self.finished = True
            self.sentences.put(None)

    # ---- workers
    def _synth_worker(self):
        _com_init()
        while True:
            s = self.sentences.get()
            if s is None or self.cancelled.is_set():
                self.audio.put(None)
                return
            # stay just ahead of what he's saying instead of making the whole reply at once: same work,
            # spread out, so it's not one long burst at full CPU
            while self.audio.qsize() >= self.AHEAD and not self.cancelled.is_set():
                time.sleep(0.05)
            audio = self.sp.synth(s, self.persona)
            self.audio.put((s, audio))

    def _play_worker(self):
        _com_init()
        started = False
        try:
            while True:
                item = self.audio.get()
                if item is None:
                    return
                s, audio = item
                if self.after is not None and not started:
                    while not self.after.done.wait(0.05) and not self.cancelled.is_set():
                        pass
                if not started and self.after is None:
                    t_wait = time.time()          # you're mid-sentence: give you up to 4 s to finish first
                    while self.sp.wait_user() and time.time() - t_wait < 4 and not self.cancelled.is_set():
                        time.sleep(0.05)
                if self.cancelled.is_set():
                    if audio:
                        audio.discard()
                else:
                    if not started:
                        started = True
                    self.sp.on_state("speaking")
                    try:
                        self.sp.on_sentence(s, self.who)
                    except TypeError:
                        self.sp.on_sentence(s)
                    self.sp.play(audio)
                with self._cv:
                    self._played += 1
                    self._cv.notify_all()
                    caught_up = self._played >= self._queued
                if caught_up and not self.finished:
                    self.sp.on_state("waiting")   # said everything so far; Claude is still working
        finally:
            with self._cv:
                self._played = self._queued
                self._cv.notify_all()
            self.done.set()
            self.sp.streams.discard(self)
            if self.sp.active is self:
                self.sp.active = None
            self.sp.on_state("done")
