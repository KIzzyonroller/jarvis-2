"""
Ears: always listening.

The mic is cut into utterances (you talk, then pause). Each utterance is
transcribed locally with Whisper, and the app decides what to do with it:
commands that start or end with "Jarvis"/"Ultron" are acted on, everything
else is ignored unless Jarvis just asked you something.

Nothing is sent anywhere until you address him by name.
"""
import os
import queue
import sys
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np

import config

# Whisper loves to "hear" these in pure noise.
HALLUCINATIONS = {"", "you", "thank you", "thanks for watching", "thank you for watching", ".",
                  "bye", "thanks", "so", "okay", "uh", "um", "hmm", "mm"}
# what Whisper makes up from noise, but also real answers: only thrown away when he isn't waiting for you
ANSWER_WORDS = {"okay", "thanks", "thank you", "bye", "so"}

from voice import Speaker, clean_for_speech  # noqa: E402,F401


def _rms(chunk):
    return float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))


def _add_cuda_dlls():
    """If the NVIDIA cuBLAS/cuDNN pip packages are installed, let Windows find their DLLs."""
    if sys.platform != "win32":
        return
    import importlib.util
    import os
    for pkg in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_runtime"):
        try:
            spec = importlib.util.find_spec(pkg)
        except Exception:
            spec = None
        for loc in (spec.submodule_search_locations if spec and spec.submodule_search_locations else []):
            b = os.path.join(loc, "bin")
            if os.path.isdir(b):
                try:
                    os.add_dll_directory(b)
                    os.environ["PATH"] = b + os.pathsep + os.environ.get("PATH", "")
                except Exception:
                    pass


def _load_model(name, device):
    from faster_whisper import WhisperModel
    # half the logical cores (i.e. roughly the real cores), so the voice and the app aren't starved
    kw = {} if device == "cuda" else {"cpu_threads": max(1, min(config.WHISPER_THREADS, max(2, (os.cpu_count() or 4) // 2)))}
    m = WhisperModel(name, device=device, compute_type="float16" if device == "cuda" else "int8", **kw)
    if device == "cuda":   # CUDA can "load" fine and then fail on first use if a DLL is missing
        list(m.transcribe(np.zeros(16000, dtype=np.float32), language="en")[0])
    return m


_CUDA_TEST = r"""
import sys, numpy as np
sys.path.insert(0, sys.argv[1])
import speech
speech._add_cuda_dlls()
from faster_whisper import WhisperModel
m = WhisperModel("tiny.en", device="cuda", compute_type="float16")
segs, _ = m.transcribe(np.zeros(16000, dtype=np.float32), language="en")
list(segs)
print("CUDA_OK")
"""


CUDA_DLLS = ("cublas64_12.dll", "cudnn_ops64_9.dll")


def _cuda_libs_present():
    """GPU speech needs NVIDIA's CUDA 12 libraries (cuBLAS, cuDNN). The installed app doesn't ship them (they're
    over a gigabyte), so on most PCs they simply aren't there: then don't even try."""
    if sys.platform != "win32":
        return True
    import ctypes
    for dll in CUDA_DLLS:
        try:
            ctypes.WinDLL(dll)
        except OSError:
            return False
    return True


def _cuda_works():
    """Try the GPU in a SEPARATE process first. A missing or mismatched NVIDIA DLL can crash Python
    outright (no error to catch), and that must not take Jarvis down with it. The answer is cached
    until the installed versions change."""
    import json
    import subprocess
    try:
        import ctranslate2
        key = f"{ctranslate2.__version__}|{ctranslate2.get_cuda_device_count()}"
    except Exception:
        return False
    cache = config.CACHE_DIR / "cuda_check.json"
    try:
        c = json.loads(cache.read_text(encoding="utf-8"))
        if c.get("key") == key and (c.get("ok") or time.time() - c.get("t", 0) < 86400):
            return bool(c.get("ok"))            # a failure is re-tested once a day, in case it was a fluke
    except Exception:
        pass
    _add_cuda_dlls()                       # so the child process inherits the PATH to the NVIDIA DLLs
    if config.FROZEN and not _cuda_libs_present():
        print("[voice] NVIDIA's CUDA 12 libraries aren't installed; speech recognition runs on the CPU")
        ok = False
    else:
        ok = _run_cuda_test()
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"key": key, "ok": ok, "t": time.time()}), encoding="utf-8")
    except Exception:
        pass
    return ok


def _run_cuda_test():
    import subprocess
    import tempfile
    result = Path(tempfile.gettempdir()) / f"jarvis-cuda-{os.getpid()}.txt"
    try:
        # The installed app has no console, so the child reports through a file, never a pop-up
        cmd = ([sys.executable, "--cuda-test", str(result)] if config.FROZEN
               else [sys.executable, "-c", _CUDA_TEST, str(config.BASE_DIR)])
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=180, creationflags=0x08000000 if sys.platform == "win32" else 0)
        out = (r.stdout or "") + (result.read_text(encoding="utf-8", errors="replace") if result.exists() else "")
        ok = "CUDA_OK" in out
        if not ok:
            tail = (out or r.stderr or "").strip().splitlines()[-1:] or [f"exit code {r.returncode}"]
            print(f"[voice] GPU speech recognition failed its test ({tail[0][:200]}); using the CPU")
    except Exception as e:
        ok = False
        print(f"[voice] GPU test couldn't run ({e}); using the CPU")
    finally:
        try:
            result.unlink()
        except OSError:
            pass
    return ok


def _pick_device():
    want = config.WHISPER_DEVICE
    if want == "cpu":
        return "cpu"
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0 and _cuda_works():
            _add_cuda_dlls()
            return "cuda"
    except Exception:
        pass
    if want == "cuda":
        print("[voice] JARVIS_WHISPER_DEVICE=cuda but the GPU isn't usable; using CPU")
    return "cpu"


def _normalize(audio):
    """Quiet mic? Bring speech up to a healthy level before Whisper sees it."""
    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if 0.003 < peak < 0.5:
        audio = audio * min(0.9 / peak, 12.0)
    return np.clip(audio, -1.0, 1.0).astype(np.float32)


class _Live:
    """Transcription that runs WHILE you talk: finished stretches of the sentence get their careful
    transcription during your natural pauses, so when you stop only the last bit is left to do."""

    def __init__(self, gate_only=False):
        self.enabled = None        # None = still deciding whether this is aimed at him
        self.commit = 0            # frames already sent off
        self.parts = []            # careful text per stretch (None while still working)
        self.cv = threading.Condition()
        # gate_only (cloud recognition on): don't transcribe pieces, just find out early whether this is
        # for him, so the "are you done?" check can go to the fast cloud model the moment you pause.
        self.gate_only = gate_only
        self.addressed = None      # gate_only: True once the quick check heard his name (or he's expecting you)
        self.gates = 0
        self.gating = False
        self.gate_done = threading.Event()

    def done_waiting(self, timeout=1.5):
        """Returns the finished pieces, or None if they aren't done in time (then the CPU is too
        slow for this and the caller uses the quick transcript instead of waiting)."""
        end = time.time() + timeout
        with self.cv:
            while any(p is None for p in self.parts) and time.time() < end:
                self.cv.wait(timeout=0.1)
            if any(p is None for p in self.parts):
                return None
        return [p for p in self.parts if p]


class Listener:
    """
    on_utterance(text, ended_at, audio)  every transcribed thing you say (fast pass);
                                         call refine(audio) for a careful second pass
    on_speech(active)             you started / stopped talking
    on_level(v)                   mic level 0..1, about 12x a second
    """

    def __init__(self, on_utterance, on_speech=None, on_level=None, log=print,
                 on_peek=None, stream_gate=None, needs_careful=None):
        import sounddevice as sd
        self.sd = sd
        # Smart end-of-sentence: after a short pause, on_peek(text, audio) gets a quick look at what you've
        # said so far. If it returns the finished text, the sentence ends right there instead of after
        # the full pause.
        self.on_peek = on_peek
        # stream_gate(fast_text) -> True if this sentence looks aimed at him (then transcribe it as you talk)
        self.stream_gate = stream_gate
        self.needs_careful = needs_careful or (lambda text: True)   # False for "pause", "volume 30"...
        self.expecting = lambda: False   # set by the core: True when he's waiting for you to say something
        self.cloud = None
        try:
            from cloud_stt import CloudSTT
            c = CloudSTT(log=log)
            if c.configured:
                self.cloud = c
                log(f"CLOUD SPEECH RECOGNITION ON  [GROQ {c.model}]")
        except Exception as e:
            log(f"CLOUD SPEECH UNAVAILABLE: {e}")
        self._live = None
        self._live_q = queue.Queue()
        self._pause_id = 0
        self._peeked = -1
        self._peek_busy = False
        self._early = None
        self._peek_jobs = {}             # pause id -> the quick look's transcript (reused if the pause wins)
        import vad as _vad
        self.vad = _vad.load(log)
        self.aec = None
        if config.ECHO_CANCEL:
            import aec as _aec
            self.aec = _aec.EchoCanceller()
            self.ref = _aec.REF
        if self.vad:
            log("SPEECH DETECTION  [NEURAL]" + ("  ECHO CANCELLING ON" if self.aec else ""))

        self.on_utterance = on_utterance
        self.on_speech = on_speech or (lambda a: None)
        self.on_level = on_level or (lambda v: None)
        self.audio_q = queue.Queue()
        self.utt_q = queue.Queue(maxsize=4)
        self._stop = threading.Event()
        self.ambient = 150.0
        self.chunk_s = config.CHUNK / config.SAMPLE_RATE
        self.prompt = ", ".join(config.LISTEN_NAMES) + "."   # nudges Whisper to spell the names right
        # Priming the accurate pass with names you actually say makes Whisper spell them right
        self._base_vocab = ", ".join(config.LISTEN_NAMES) + ". " + config.WHISPER_VOCAB
        self.muted = False
        self._mute_lock = threading.Lock()

        # Pass 1 (every utterance): small and fast, just to catch the name.
        self.device = _pick_device()
        log(f"LOADING SPEECH RECOGNITION  [{config.WHISPER_FAST} on {self.device.upper()}]")
        try:
            self.fast = _load_model(config.WHISPER_FAST, self.device)
        except Exception as e:
            if self.device != "cuda":
                raise
            log(f"GPU SPEECH FAILED ({type(e).__name__}), USING CPU")
            self.device = "cpu"
            self.fast = _load_model(config.WHISPER_FAST, "cpu")
        # Pass 2 (only when you're talking to him): bigger and careful. Loads in the background.
        self.accurate = None
        self.accurate_name = (config.WHISPER_ACCURATE if config.WHISPER_ACCURATE != "auto"
                              else ("large-v3-turbo" if self.device == "cuda" else "distil-small.en"))
        self._log = log
        threading.Thread(target=self._load_accurate, daemon=True, name="whisper-load").start()
        self.stream = sd.InputStream(samplerate=config.SAMPLE_RATE, channels=1, dtype="int16",
                                     blocksize=config.CHUNK, callback=self._callback)

    def _watch_speed(self, model, secs, audio_secs):
        """Measure how fast the local careful model really is on this PC. Too slow: swap to a lighter
        model (auto mode) if that one would be fast enough. Otherwise careful_too_slow() makes him
        skip it and use the quick transcript, so you never wait 10+ seconds."""
        if self.device == "cuda" or model is not self.accurate:
            return
        self._careful_secs = secs if not hasattr(self, "_careful_secs") else 0.6 * self._careful_secs + 0.4 * secs
        self._maybe_downgrade()

    def _maybe_downgrade(self):
        est = self.careful_estimate()
        lighter = {"distil-small.en": "base.en", "small.en": "base.en", "medium.en": "base.en"}.get(self.accurate_name)
        fast = getattr(self, "_fast_secs", None)
        lighter_ok = fast is not None and fast * self.COST_VS_TINY["base.en"] <= config.CAREFUL_BUDGET * 1.2
        if (config.WHISPER_ACCURATE == "auto" and lighter and est is not None and est > config.CAREFUL_BUDGET
                and lighter_ok and not self.cloud_on and not getattr(self, "_downgrading", False)):
            self._downgrading = True
            self._log(f"CAREFUL LISTENING TOO SLOW ON THIS CPU (~{est:.1f}s A SENTENCE), SWITCHING TO {lighter}")

            def swap():
                try:
                    m = _load_model(lighter, self.device)
                    self.accurate, self.accurate_name = m, lighter
                    if hasattr(self, "_careful_secs"):
                        del self._careful_secs          # measure the new one fresh
                    self._log(f"ACCURATE RECOGNITION READY  [{lighter}]")
                except Exception as e:
                    print(f"[voice] couldn't load {lighter}: {e}")
            threading.Thread(target=swap, daemon=True, name="whisper-swap").start()

    def _load_accurate(self):
        if self.accurate_name == config.WHISPER_FAST:
            self.accurate = self.fast
            return
        try:
            self.accurate = _load_model(self.accurate_name, self.device)
            self._log(f"ACCURATE RECOGNITION READY  [{self.accurate_name}]")
        except Exception as e:
            if self.accurate_name == "distil-small.en":          # older faster-whisper without distil models
                try:
                    self.accurate_name = "small.en"
                    self.accurate = _load_model("small.en", self.device)
                    self._log("ACCURATE RECOGNITION READY  [small.en]")
                    return
                except Exception as e2:
                    e = e2
            self._log(f"ACCURATE MODEL FAILED ({type(e).__name__}: {e}); USING THE FAST ONE")
            self.accurate = self.fast

    # ---- mute: actually closes the mic, so Windows' "mic in use" light goes off too
    def set_muted(self, muted):
        with self._mute_lock:
            if muted == self.muted:
                return
            self.muted = muted
            try:
                if muted:
                    self.stream.stop()
                else:
                    self.stream.start()
            except Exception as e:
                print(f"[voice] mic {'stop' if muted else 'start'} failed: {e}")
        if muted:
            while not self.audio_q.empty():
                try:
                    self.audio_q.get_nowait()
                except queue.Empty:
                    break
            self._reset = True
            self.on_level(0.0)

    # ---- second, careful pass
    @property
    def vocab_prompt(self):
        """Names + your JARVIS_VOCAB + words he's learned when you corrected him."""
        try:
            import tools
            learned = tools.learned_words()[-40:]
        except Exception:
            learned = []
        return self._base_vocab + ((" " + ", ".join(learned) + ".") if learned else "")

    @property
    def cloud_on(self):
        return self.cloud is not None and self.cloud.available

    # Whisper always works on a fixed 30-second window, so each pass costs about the same whatever
    # the clip length. Relative cost of each model vs tiny.en on a CPU (int8), roughly:
    COST_VS_TINY = {"tiny.en": 1.0, "base.en": 2.0, "distil-small.en": 3.5, "small.en": 6.0,
                    "distil-medium.en": 7.0, "medium.en": 15.0}

    def _fast_pass(self, audio):
        t0 = time.time()
        out = self._transcribe(self.fast, audio, beam_size=1, prompt=self.prompt)
        dt = time.time() - t0
        self._fast_secs = dt if not hasattr(self, "_fast_secs") else 0.7 * self._fast_secs + 0.3 * dt
        if self.accurate is not None:
            self._maybe_downgrade()                 # decide from the very first sentence, not after slow ones
        return out

    def careful_estimate(self):
        """Seconds one local careful pass takes on this PC: measured if we've run it, else predicted
        from the quick model's measured speed. None until we know anything."""
        if hasattr(self, "_careful_secs"):
            return self._careful_secs
        if hasattr(self, "_fast_secs"):
            return self._fast_secs * self.COST_VS_TINY.get(self.accurate_name, 4.0)
        return None

    def careful_too_slow(self, audio_secs=None):
        """Would the LOCAL careful pass take longer than it's worth on this PC?"""
        if self.cloud_on or self.device == "cuda":
            return False
        est = self.careful_estimate()
        return est is not None and est > config.CAREFUL_BUDGET

    def _junk(self, text):
        """Noise Whisper turned into words ("you", "thank you"). "Okay" or "thanks" right after he asked
        you something is a real answer, so those only count as noise when he isn't waiting for one."""
        t = (text or "").lower().strip(" .!?,")
        if t not in HALLUCINATIONS:
            return False
        if t in ANSWER_WORDS:
            try:
                return not self.expecting()
            except Exception:
                return True
        return True

    def refine(self, audio, context=""):
        """Re-transcribe carefully. Called only for speech aimed at Jarvis. Cloud (Groq) if set up,
        otherwise the local accurate model. context: what came just before (sentence in pieces)."""
        prompt = self.vocab_prompt + ((" " + context[-200:]) if context else "")
        if self.cloud_on:
            text = self.cloud.transcribe(audio, prompt)
            if text is not None:
                return text
        model = self.accurate or self.fast
        try:
            t0 = time.time()
            segs, _ = self._transcribe(model, audio, beam_size=config.WHISPER_BEAM or (5 if self.device == "cuda" else 3),
                                       prompt=prompt)
            self._watch_speed(model, time.time() - t0, len(audio) / 16000)
            return " ".join(s.text.strip() for s in segs).strip()
        except Exception as e:
            print(f"[voice] accurate pass failed: {e}")
            return None

    _vad_filter = True

    def _hotwords(self):
        try:
            import tools
            extra = tools.learned_words()[-20:]
        except Exception:
            extra = []
        return " ".join(list(config.LISTEN_NAMES) + extra)

    def _transcribe(self, model, audio, beam_size, prompt):
        """Returns (list of segments, info). Never lets a broken optional piece stop him hearing you."""
        kw = dict(language="en", beam_size=beam_size, vad_filter=Listener._vad_filter, initial_prompt=prompt,
                  condition_on_previous_text=False, without_timestamps=True)
        a = _normalize(audio)
        try:
            try:
                segs, info = model.transcribe(a, hotwords=self._hotwords(), **kw)
            except TypeError:          # older faster-whisper without hotwords
                segs, info = model.transcribe(a, **kw)
            return list(segs), info
        except Exception as e:
            onnx_trouble = isinstance(e, (ImportError, OSError)) or "onnx" in str(e).lower()
            if not Listener._vad_filter or not onnx_trouble:
                raise
            # Whisper's built-in silence trimming needs ONNX Runtime. If that install is broken (e.g. two
            # versions on top of each other), skip the trimming rather than going deaf.
            Listener._vad_filter = False
            print(f"[voice] Whisper's silence trimming failed ({type(e).__name__}: {e}); continuing without it. "
                  "Run fix_gpu.bat to repair ONNX Runtime.")
            return self._transcribe(model, audio, beam_size, prompt)

    def start(self):
        self.stream.start()
        threading.Thread(target=self._capture, daemon=True, name="mic").start()
        threading.Thread(target=self._transcriber, daemon=True, name="whisper").start()
        threading.Thread(target=self._live_worker, daemon=True, name="whisper-live").start()

    def stop(self):
        self._stop.set()
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass

    def _callback(self, indata, frames, t, status):
        adc = t.inputBufferAdcTime or (t.currentTime - self.stream.latency - frames / config.SAMPLE_RATE)
        self.audio_q.put((indata[:, 0].copy(), adc))

    # ---- cut the mic stream into utterances
    def _clean(self, chunk, adc):
        """int16 mic chunk -> float32, with his own voice cancelled out if we know what he played."""
        x = chunk.astype(np.float32) / 32768.0
        if self.aec is not None:
            want = adc + 0.06 + len(x) / config.SAMPLE_RATE
            for _ in range(8):                          # wait (briefly) until the speaker side has caught up
                cov = self.ref.covered_until()
                if cov is None or cov >= want:
                    break
                time.sleep(0.02)
            ref = self.ref.read(adc + 0.06, len(x))      # read a little ahead: timestamps are never perfect
            x = self.aec.process(x, ref)
        return x

    def _is_speech(self, x, r, thr):
        """Neural speech detector when available, loudness otherwise. Returns (start-worthy, keep-going)."""
        if self.vad is not None:
            probs = self.vad(x)
            p = max(probs) if probs else 0.0
            loud_enough = r > 60                         # ignore faint far-away voices
            return (p >= config.VAD_THRESHOLD and loud_enough), (p >= config.VAD_THRESHOLD * 0.6 and loud_enough)
        return r > thr, r > thr * 0.6

    def _capture(self):
        pre = deque(maxlen=max(1, int(0.5 / self.chunk_s)))   # keep the half second BEFORE you start talking
        frames, in_speech, loud_run, silent, voiced = [], False, 0, 0.0, 0.0
        self._reset = False
        print("[voice] listening")
        while not self._stop.is_set():
            try:
                chunk, adc = self.audio_q.get(timeout=0.5)
            except queue.Empty:
                continue
            if self.muted:
                continue
            if self._reset:     # just unmuted: start clean, don't finish a half-heard sentence
                self._reset = False
                pre.clear()
                if self.vad is not None:
                    self.vad.reset()
                if in_speech:
                    self.on_speech(False)
                frames, in_speech, loud_run = [], False, 0
            x = self._clean(chunk, adc)
            r = float(np.sqrt(np.mean(x ** 2))) * 32768.0
            self.on_level(min(1.0, r / 3000.0))
            thr = max(self.ambient * 3.0, config.MIN_SPEECH_RMS)
            start_ok, keep_ok = self._is_speech(x, r, thr)
            if not in_speech:
                pre.append(x)
                loud_run = loud_run + 1 if start_ok else 0
                if loud_run == 0:
                    self.ambient = 0.97 * self.ambient + 0.03 * r
                if loud_run >= 2:                       # ~160 ms of speech = someone's talking
                    in_speech, frames, silent, voiced = True, list(pre), 0.0, 0.0
                    # (with cloud recognition the whole sentence goes in one quick request instead)
                    if (self.stream_gate and config.LIVE_TRANSCRIBE and not self.cloud_on
                            and not self.careful_too_slow(3.0) and time.time() - getattr(self, "_live_slow", 0) > 600):
                        self._live = _Live()
                    elif self.stream_gate and self.cloud_on and config.SMART_ENDPOINT:
                        self._live = _Live(gate_only=True)
                    else:
                        self._live = None
                    self._cloud_peeks = 0
                    self.on_speech(True)
                continue
            frames.append(x)
            if keep_ok:
                if silent > 0:
                    self._pause_id += 1                 # you kept talking: any quick look at the pause is stale
                silent, voiced = 0.0, voiced + self.chunk_s
            else:
                silent += self.chunk_s
            total = len(frames) * self.chunk_s
            self._live_step(frames, voiced, silent)
            early = self._early
            if early and early[0] == self._pause_id and silent > 0:
                self._early = None                      # the quick look says you're done: go now
                frames, in_speech, loud_run = self._finish(frames, voiced, pre, early[1], silent,
                                                           careful=len(early) > 2 and early[2]), False, 0
                continue
            live = self._live
            not_for_him = live is not None and live.enabled is False and not self.expecting()
            if (self.on_peek and config.SMART_ENDPOINT and not not_for_him and silent >= config.EARLY_SILENCE and voiced >= 0.3
                    and self._peeked != self._pause_id and not self._peek_busy and total < config.MAX_RECORD_SECONDS):
                self._peeked = self._pause_id
                self._peek_busy = True
                job = {"done": threading.Event(), "raw": None}
                self._peek_jobs = {self._pause_id: job}
                threading.Thread(target=self._peek_run, args=(np.concatenate(frames), self._pause_id, voiced, job),
                                 daemon=True, name="peek").start()
            if silent >= config.SILENCE_SECONDS or total >= config.MAX_RECORD_SECONDS:
                frames, in_speech, loud_run = self._finish(frames, voiced, pre, None, silent), False, 0

    # ---- transcribe as you talk
    def _live_step(self, frames, voiced, silent):
        live = self._live
        if live is not None and live.gate_only:
            # one quick name check early on, and one more later if the name hadn't shown up yet
            if (not live.gating and live.addressed is not True
                    and ((live.gates == 0 and voiced >= 0.7) or (live.gates == 1 and voiced >= 2.4))):
                live.gating = True
                live.gates += 1
                live.gate_done.clear()
                self._live_q.put(("gate", live, np.concatenate(frames).astype(np.float32), None))
            return
        if live is None or live.enabled is False:
            return
        if live.enabled is None:
            if voiced >= 0.7 and not getattr(live, "gating", False):
                live.gating = True                      # first: is this even for him? (cheap fast pass)
                self._live_q.put(("gate", live, np.concatenate(frames).astype(np.float32), None))
            return
        # a natural pause after a decent stretch of speech: send that stretch off now
        if silent >= 0.24 and (len(frames) - live.commit) * self.chunk_s >= 1.4:
            audio = np.concatenate(frames[live.commit:]).astype(np.float32)
            with live.cv:
                idx = len(live.parts)
                live.parts.append(None)
            live.commit = len(frames)
            self._live_q.put(("part", live, audio, idx))

    def _live_worker(self):
        while not self._stop.is_set():
            try:
                kind, live, audio, idx = self._live_q.get(timeout=0.5)
            except queue.Empty:
                continue
            if getattr(live, "abandoned", False):
                if idx is not None:
                    with live.cv:
                        live.parts[idx] = ""
                        live.cv.notify_all()
                continue                                  # that sentence is long gone: don't spend CPU on it
            try:
                if kind == "gate":
                    segs, _ = self._fast_pass(audio)
                    text = " ".join(x.text.strip() for x in segs).strip()
                    ok = bool(text) and bool(self.stream_gate(text))
                    if live.gate_only:
                        live.addressed = ok
                        live.gating = False
                        live.gate_done.set()
                    else:
                        live.enabled = ok
                    continue
                prev = ""
                with live.cv:
                    done = [p for p in live.parts[:idx] if p]
                    prev = done[-1] if done else ""
                text = self.refine(audio, context=prev) or ""
                if self._junk(text):
                    text = ""
            except Exception as e:
                print(f"[voice] live transcription failed: {e}")
                text = ""
                if kind == "gate":
                    live.enabled = False
                    continue
            with live.cv:
                live.parts[idx] = text
                live.cv.notify_all()

    def _finish(self, frames, voiced, pre, text, silent=0.0, careful=False):
        """End the current sentence and hand it to the transcriber. text: already transcribed by a quick look."""
        pre.clear()
        job = self._peek_jobs.pop(self._pause_id, None) if text is None else None   # quick look still running?
        self._peek_jobs = {}
        self._pause_id += 1
        self.on_speech(False)
        live, self._live = self._live, None
        if voiced >= 0.3:
            audio = np.concatenate(frames).astype(np.float32)
            if live is not None and live.enabled and live.commit > 0:
                live_info = (live, sum(len(f) for f in frames[:live.commit]))
            else:
                live_info = None
            now = time.time()
            timing = {"speech_end": now - silent, "endpoint": silent, "how": "quick finish" if text else "pause"}
            timing["peek_job"] = job
            timing["pre_careful"] = bool(text and careful)     # the quick look's text came from the careful (cloud) model
            if text and careful and not isinstance(careful, bool):
                timing["cloud"] = float(careful)
            try:
                self.utt_q.put_nowait((audio, now, voiced, text, live_info, timing))
            except queue.Full:
                print("[voice] transcription backlog, dropped an utterance")
        return []

    def _peek_run(self, audio, pid, voiced, job=None):
        job = job if job is not None else {"done": threading.Event(), "raw": None}
        try:
            live = self._live
            addressed = bool(live is not None and live.enabled)
            look = audio
            if addressed and len(audio) > 16000 * 3.5:
                look = audio[-int(16000 * 2.5):]          # already know it's for him: only the ending matters
            careful = False
            if live is not None and live.gate_only and self.cloud_on and getattr(self, "_cloud_peeks", 0) < 3:
                # Cloud recognition is on and your PC's quick model is the slow part. If the name check already
                # says this is for him (or he's waiting on your answer), ask the cloud: same privacy rule as the
                # careful pass (only speech aimed at him leaves the PC), and back in a few hundred ms.
                if live.addressed is None and live.gating:
                    live.gate_done.wait(1.2)
                expecting = False
                try:
                    expecting = bool(self.expecting())
                except Exception:
                    pass
                if (live.addressed or expecting) and pid == self._pause_id:
                    self._cloud_peeks = getattr(self, "_cloud_peeks", 0) + 1
                    t0 = time.time()
                    cloud_text = self.cloud.transcribe(audio, self.vocab_prompt)
                    if cloud_text is not None:
                        job["raw"] = cloud_text
                        job["careful"] = True
                        job["secs"] = time.time() - t0
                        text = cloud_text.strip()
                        if not text or self._junk(text) or pid != self._pause_id:
                            return
                        try:
                            final = self.on_peek(text, audio, addressed=True)
                        except TypeError:
                            final = self.on_peek(text, audio)
                        if final and pid == self._pause_id:
                            self._early = (pid, final, job["secs"] or 0.001)
                        return
            segs, _ = self._fast_pass(look)
            text = " ".join(s.text.strip() for s in segs).strip()
            if look is audio:
                job["raw"] = text                       # the whole sentence so far: reusable as the quick transcript
            if not text or self._junk(text) or pid != self._pause_id:
                return
            try:
                final = self.on_peek(text, audio, addressed=addressed and look is not audio)
            except TypeError:
                final = self.on_peek(text, audio)
            if final and pid == self._pause_id:
                self._early = (pid, final)
        except Exception as e:
            print(f"[voice] quick look failed: {e}")
        finally:
            self._peek_busy = False
            job["done"].set()

    # ---- transcribe utterances (separate thread so the mic never stops)
    def _transcriber(self):
        while not self._stop.is_set():
            try:
                audio, ended, voiced, pre_text, live_info, timing = self.utt_q.get(timeout=0.5)
                timing["queue"] = time.time() - ended
            except queue.Empty:
                continue
            if self.muted:
                continue
            if (not self.utt_q.empty() and time.time() - ended > 6 and not pre_text and live_info is None
                    and not self.expecting()):
                # the CPU is behind (usually a video or call being picked up by the mic): skip old chatter
                print(f"[voice] falling behind; skipped a {time.time() - ended:.0f}s-old sentence")
                continue
            if pre_text and not self.needs_careful(pre_text):
                self.on_utterance(pre_text, ended, audio, refined=True, timing=timing)   # quick command: fast text is plenty
                continue
            skip_careful = False
            if live_info is not None:
                # most of it was already carefully transcribed while you talked: just finish the last bit
                live, start = live_info
                t0 = time.time()
                parts = live.done_waiting()
                timing["live_wait"] = time.time() - t0
                if parts is None:
                    # this CPU couldn't keep up: don't make you wait for it, go with the quick transcript
                    live.abandoned = True
                    print("[voice] live transcription couldn't keep up; using the quick transcript")
                    self._live_slow = time.time()
                    skip_careful = True
                else:
                    t0 = time.time()
                    tail = audio[start:]
                    tail_text = ""
                    if len(tail) > 16000 * 0.3:
                        tail_text = self.refine(tail, context=parts[-1] if parts else "") or ""
                        if self._junk(tail_text):
                            tail_text = ""
                    timing["careful"] = time.time() - t0
                    text = " ".join(p for p in parts + [tail_text] if p).strip()
                    if text:
                        self.on_utterance(text, ended, audio, refined=True, timing=timing)
                        continue
            if pre_text:                                   # the quick look already transcribed it
                pre_careful = timing.pop("pre_careful", False)
                self.on_utterance(pre_text, ended, audio, refined=skip_careful or pre_careful, timing=timing)
                continue
            job = timing.pop("peek_job", None)
            if job is not None:
                # the pause ended while the quick look was still working: use its transcript, don't start over
                t0 = time.time()
                job["done"].wait(4)
                timing["fast"] = time.time() - t0
                if job["raw"] is not None:
                    text = job["raw"]
                    if text and not self._junk(text) and text.strip() != self.prompt:
                        self.on_utterance(text, ended, audio, refined=skip_careful or job.get("careful", False), timing=timing)
                    continue
            try:
                t0 = time.time()
                segments, _ = self._fast_pass(audio)
                text = " ".join(s.text.strip() for s in segments).strip()
                timing["fast"] = time.time() - t0
            except Exception as e:
                print(f"[voice] transcription failed: {e}")
                continue
            if self._junk(text) or text.strip() == self.prompt:
                continue
            self.on_utterance(text, ended, audio, refined=skip_careful, timing=timing)
