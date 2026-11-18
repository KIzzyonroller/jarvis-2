"""
Voice ID: he only takes orders from your voice. Friends in the room can say "Jarvis" all they like.

How: a small speaker-recognition network (WeSpeaker ResNet34, ~26 MB, runs locally with onnxruntime, about 50 ms per
sentence on a normal CPU) turns a stretch of speech into a "voiceprint" (256 numbers). "Learn my voice" records you
for about 30 seconds and averages those into your print; after that every sentence that would make him act is
compared with it, and a sentence that doesn't sound like you is ignored (and logged with its score, so the threshold
can be tuned). It keeps adapting slowly to how you sound on your mic. Nothing is uploaded: the print and the model
live in his folder.

Short bits (under ~1.2 s, like just "Jarvis") are too short to judge reliably, so they're let through; the request
that follows is checked.
"""
import json
import threading
import time
from pathlib import Path

import numpy as np

import config

MODEL_NAME = "voxceleb_resnet34_LM.onnx"
MODEL_URLS = [
    "https://huggingface.co/Wespeaker/wespeaker-voxceleb-resnet34-LM/resolve/main/voxceleb_resnet34_LM.onnx",
    "https://huggingface.co/openspeech/wespeaker-models/resolve/main/voxceleb_resnet34_LM.onnx",
    "https://huggingface.co/chengdongliang/wespeaker/resolve/main/voxceleb_resnet34_LM.onnx",
]
PRINT = "voiceprint.json"
STRICT = {"relaxed": 0.30, "normal": 0.40, "strict": 0.52}
MIN_SECS = 1.2

_sess = None
_lock = threading.Lock()
_print = None
ENROLL = {"on": False, "until": 0.0, "embs": [], "secs": 0.0, "done": None}


def _model_path():
    return Path(config.MODELS_DIR) / MODEL_NAME


def ensure_model():
    p = _model_path()
    if p.exists() and p.stat().st_size > 5_000_000:
        return True
    try:
        import download_models
        return bool(download_models.fetch(MODEL_NAME, urls=MODEL_URLS))
    except Exception as e:
        print(f"[voice id] model download failed: {e}")
        return False


def _session():
    global _sess
    with _lock:
        if _sess is None:
            import onnxruntime as ort
            if not ensure_model():
                raise RuntimeError("voice model not downloaded")
            so = ort.SessionOptions()
            so.intra_op_num_threads = 2
            _sess = ort.InferenceSession(str(_model_path()), so, providers=["CPUExecutionProvider"])
        return _sess


# ------------------------------------------------------------------ features: 80 log-mel filterbanks, Kaldi style
_MEL = None


def _mel_bank(n_fft=512, sr=16000, n_mels=80, lo=20.0, hi=8000.0):
    def mel(f):
        return 1127.0 * np.log(1.0 + f / 700.0)
    m_lo, m_hi = mel(lo), mel(hi)
    pts = np.linspace(m_lo, m_hi, n_mels + 2)
    freqs = np.arange(n_fft // 2 + 1) * sr / n_fft
    mf = mel(freqs)
    bank = np.zeros((n_mels, len(freqs)), dtype=np.float32)
    for i in range(n_mels):
        l, c, r = pts[i], pts[i + 1], pts[i + 2]
        up = (mf - l) / (c - l)
        down = (r - mf) / (r - c)
        bank[i] = np.maximum(0, np.minimum(up, down))
    return bank


def fbank(audio, sr=16000):
    global _MEL
    if _MEL is None:
        _MEL = _mel_bank()
    x = np.asarray(audio, dtype=np.float32).reshape(-1)
    if np.abs(x).max() <= 1.5:                    # float audio: scale to int16 range like Kaldi expects
        x = x * 32768.0
    flen, shift, n_fft = 400, 160, 512
    if len(x) < flen:
        x = np.pad(x, (0, flen - len(x)))
    n = 1 + (len(x) - flen) // shift
    idx = np.arange(flen)[None, :] + shift * np.arange(n)[:, None]
    frames = x[idx].astype(np.float32)
    frames -= frames.mean(axis=1, keepdims=True)                         # remove DC
    frames = np.concatenate([frames[:, :1], frames[:, 1:] - 0.97 * frames[:, :-1]], axis=1)   # pre-emphasis
    win = (0.5 - 0.5 * np.cos(2 * np.pi * np.arange(flen) / (flen - 1))) ** 0.85              # Povey window
    frames *= win
    spec = np.abs(np.fft.rfft(frames, n=n_fft)) ** 2
    feats = np.log(np.maximum(spec @ _MEL.T, 1.1920929e-07))
    return feats - feats.mean(axis=0, keepdims=True)                     # per-utterance mean normalisation


def embed(audio):
    """A unit-length voiceprint for a stretch of 16 kHz speech."""
    s = _session()
    f = fbank(audio)[None, :, :].astype(np.float32)
    name = s.get_inputs()[0].name
    e = s.run(None, {name: f})[0].reshape(-1)
    return e / (np.linalg.norm(e) + 1e-9)


# ------------------------------------------------------------------ the print
def _load():
    global _print
    if _print is None:
        try:
            d = json.loads((config.JARVIS_DIR / PRINT).read_text(encoding="utf-8"))
            _print = np.array(d["v"], dtype=np.float32)
        except Exception:
            _print = None
    return _print


def _save(v, n):
    global _print
    _print = v / (np.linalg.norm(v) + 1e-9)
    (config.JARVIS_DIR / PRINT).write_text(json.dumps({"v": _print.round(6).tolist(), "n": n,
                                                       "at": time.strftime("%Y-%m-%d %H:%M")}), encoding="utf-8")


def forget():
    global _print
    _print = None
    try:
        (config.JARVIS_DIR / PRINT).unlink()
    except OSError:
        pass


def on():
    import os
    return os.environ.get("JARVIS_VOICE_ID", "true").lower() != "false" and _load() is not None


def threshold():
    import os
    return STRICT.get(os.environ.get("JARVIS_VOICE_ID_STRICT", "normal").lower(), STRICT["normal"])


def status():
    p = _load()
    m = _model_path().exists()
    return {"enrolled": p is not None, "model": m, "on": on(),
            "detail": ("on, " if on() else "off, ") + ("voice learned" if p is not None else "voice not learned") +
                      ("" if m else "; model not downloaded") + f"; strictness {threshold():.2f}"}


# ------------------------------------------------------------------ learning your voice
def start_enroll(seconds=40, done=None):
    ENROLL.update(on=True, until=time.time() + seconds, embs=[], secs=0.0, done=done)
    threading.Thread(target=_session, daemon=True).start()           # load / download the model meanwhile
    t = threading.Timer(seconds + 1, finish_enroll)                  # stopped talking early: finish with what we have
    t.daemon = True
    t.start()


def feed_enroll(audio):
    """Called with each sentence heard while learning. Returns True when it has enough."""
    secs = len(audio) / 16000
    if secs >= MIN_SECS:
        step = 4 * 16000                                 # long speech: one sample per ~4 seconds
        chunks = [audio[i:i + step] for i in range(0, len(audio), step)] if secs > 6 else [audio]
        for c in chunks:
            if len(c) / 16000 < MIN_SECS:
                continue
            try:
                ENROLL["embs"].append(embed(c))
                ENROLL["secs"] += len(c) / 16000
            except Exception as e:
                print(f"[voice id] {e}")
    if ENROLL["secs"] >= 20 or time.time() > ENROLL["until"]:
        return finish_enroll()
    return False


def finish_enroll():
    if not ENROLL["on"]:
        return False
    ENROLL["on"] = False
    embs = ENROLL["embs"]
    cb = ENROLL.get("done")
    if len(embs) >= 3:
        _save(np.mean(np.stack(embs), axis=0), len(embs))
        ok, msg = True, f"Got it: learned your voice from {ENROLL['secs']:.0f} seconds of speech."
    else:
        ok, msg = False, "I didn't hear enough of you to learn your voice. Try again and keep talking for about 20 seconds."
    if cb:
        try:
            cb(ok, msg)
        except Exception:
            pass
    return True


# ------------------------------------------------------------------ checking
def score(audio):
    p = _load()
    if p is None:
        return None
    return float(np.dot(embed(audio), p))


def is_owner(audio):
    """(ok, score). Too short to judge, model missing, or voice ID off: ok."""
    if not on() or audio is None or len(audio) / 16000 < MIN_SECS:
        return True, None
    try:
        e = embed(audio)
    except Exception as ex:
        print(f"[voice id] can't check ({ex}); letting it through")
        return True, None
    p = _load()
    s = float(np.dot(e, p))
    ok = s >= threshold()
    if ok and s >= threshold() + 0.12 and len(audio) / 16000 >= 2.0:
        _save(0.97 * p + 0.03 * e, -1)                 # drift slowly with your mic and your voice
    return ok, s
