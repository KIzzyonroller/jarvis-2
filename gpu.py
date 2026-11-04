"""
The graphics card, for hearing and for his voice.

Hearing (speech recognition) on an NVIDIA card needs NVIDIA's CUDA 12 libraries (cuBLAS and cuDNN). They're
over a gigabyte, so the installer doesn't ship them: "set up graphics card hearing" downloads them once, straight
from NVIDIA's packages on PyPI, keeps only the DLLs (in JarvisData\\gpu), and speech.py picks them up on the next
start. If the card then fails its test, he quietly stays on the processor.

His voice (Kokoro) can run through DirectML, which works on any DirectX 12 card (NVIDIA, AMD, Intel). Some cards
can't run one of Kokoro's layers, so the graphics card has to pass a real test sentence first; until it does, and
whenever it fails, the voice runs on the processor. The result of the test is remembered.
"""
import json
import os
import shutil
import sys
import threading
import time
import zipfile
from pathlib import Path

import config

GPU_DIR = config.DATA_DIR / "gpu"
BIN_DIR = GPU_DIR / "bin"
VOICE_TEST = config.CACHE_DIR / "voice_gpu_check.json"

# (package, versions to accept) -- what ctranslate2 4.5+ (faster-whisper) needs on Windows
CUDA_PACKAGES = [("nvidia-cuda-runtime-cu12", "12."), ("nvidia-cublas-cu12", "12."), ("nvidia-cudnn-cu12", "9.")]
NEEDED_MB = 2600                  # downloads plus the unpacked DLLs, with room to spare

_lock = threading.Lock()
_state = {"busy": False, "step": "", "pct": 0, "error": ""}


# ------------------------------------------------------------------ what's there
def nvidia_card():
    """Name of the NVIDIA card, or '' if there isn't one (or its driver isn't installed)."""
    if sys.platform != "win32":
        return ""
    import subprocess
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=8, creationflags=0x08000000)
        line = (r.stdout or "").strip().splitlines()
        return line[0].strip() if r.returncode == 0 and line else ""
    except Exception:
        return ""


def cuda_libs_downloaded():
    return BIN_DIR.is_dir() and any(BIN_DIR.glob("cublas64_12*.dll")) and any(BIN_DIR.glob("cudnn*64_9*.dll"))


def add_dll_dir():
    """Let Windows find the downloaded DLLs (this process and any it starts)."""
    if sys.platform != "win32" or not BIN_DIR.is_dir():
        return False
    try:
        os.add_dll_directory(str(BIN_DIR))
    except Exception:
        pass
    p = os.environ.get("PATH", "")
    if str(BIN_DIR) not in p:
        os.environ["PATH"] = str(BIN_DIR) + os.pathsep + p
    return True


def status():
    """For the System panel and 'what's my graphics card doing?'."""
    hearing_dev = getattr(config, "HEARING_ON", "") or ""
    v = _voice_cache()
    return {
        "card": nvidia_card() if sys.platform == "win32" else "",
        "cuda_libs": cuda_libs_downloaded(),
        "hearing_setting": config.WHISPER_DEVICE,
        "hearing_on": hearing_dev,
        "voice_setting": config.VOICE_DEVICE,
        "voice_on": getattr(config, "VOICE_ON", "") or "",
        "voice_gpu_test": v.get("ok") if v else None,
        "voice_gpu_note": (v or {}).get("note", ""),
        "download": dict(_state),
    }


# ------------------------------------------------------------------ downloading the CUDA libraries
def _pick_wheel(session, pkg, prefix):
    r = session.get(f"https://pypi.org/pypi/{pkg}/json", timeout=20)
    r.raise_for_status()
    data = r.json()

    def key(v):
        out = []
        for part in v.split("."):
            num = "".join(ch for ch in part if ch.isdigit())
            out.append(int(num) if num else 0)
        return out

    for ver in sorted(data.get("releases", {}), key=key, reverse=True):
        if not ver.startswith(prefix) or any(x in ver for x in ("a", "b", "rc", "dev")):
            continue
        for f in data["releases"][ver]:
            name = f.get("filename", "")
            if name.endswith(".whl") and "win_amd64" in name and not f.get("yanked"):
                return ver, f["url"], int(f.get("size") or 0)
    raise RuntimeError(f"no Windows build of {pkg} {prefix}x on PyPI")


def _set(**kw):
    _state.update(kw)


def download_cuda(progress=None, cancel=None):
    """Downloads and unpacks NVIDIA's CUDA 12 libraries. progress(step, pct). Returns (ok, message)."""
    if sys.platform != "win32":
        return False, "Only on Windows."
    with _lock:
        if _state["busy"]:
            return False, "Already downloading."
        _set(busy=True, step="Checking", pct=0, error="")
    progress = progress or (lambda step, pct: None)
    tmp = GPU_DIR / "download"
    try:
        if not nvidia_card():
            raise RuntimeError("No NVIDIA graphics card (or its driver) found. Hearing stays on the processor.")
        GPU_DIR.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(GPU_DIR).free // (1024 * 1024)
        if free < NEEDED_MB:
            raise RuntimeError(f"Needs about {NEEDED_MB // 1000 + 1} GB free on that drive; there's {free // 1024} GB.")
        import requests
        s = requests.Session()
        s.headers["User-Agent"] = "JarvisAssistant (gpu setup)"
        picks = [_pick_wheel(s, pkg, pre) for pkg, pre in CUDA_PACKAGES]
        total = sum(p[2] for p in picks) or 1
        done = 0
        tmp.mkdir(parents=True, exist_ok=True)
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        for (pkg, _), (ver, url, size) in zip(CUDA_PACKAGES, picks):
            whl = tmp / url.rsplit("/", 1)[-1]
            label = f"Downloading {pkg.replace('nvidia-', '').replace('-cu12', '')} {ver}"
            with s.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(whl, "wb") as f:
                    last = 0
                    for chunk in r.iter_content(1 << 20):
                        if cancel and cancel():
                            raise RuntimeError("Cancelled.")
                        f.write(chunk)
                        done += len(chunk)
                        pct = int(done * 95 / total)
                        if pct != last:
                            last = pct
                            _set(step=label, pct=pct)
                            progress(label, pct)
            _set(step=f"Unpacking {pkg}")
            progress(f"Unpacking {pkg}", int(done * 95 / total))
            with zipfile.ZipFile(whl) as z:
                for name in z.namelist():
                    if name.lower().endswith(".dll") and "/bin/" in name.replace("\\", "/"):
                        with z.open(name) as src, open(BIN_DIR / Path(name).name, "wb") as dst:
                            shutil.copyfileobj(src, dst)
            whl.unlink(missing_ok=True)
        try:
            (config.CACHE_DIR / "cuda_check.json").unlink(missing_ok=True)      # test the card again on next start
        except Exception:
            pass
        (GPU_DIR / "installed.json").write_text(json.dumps({"t": time.time(), "versions": [p[0] for p in picks]}),
                                                 encoding="utf-8")
        _set(step="Done", pct=100)
        progress("Done", 100)
        return True, "Downloaded. Restart him and he'll test the graphics card for hearing."
    except Exception as e:
        _set(error=str(e)[:300], step="Failed")
        return False, str(e)[:300]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        _set(busy=False)


def remove_cuda():
    shutil.rmtree(GPU_DIR, ignore_errors=True)
    try:
        (config.CACHE_DIR / "cuda_check.json").unlink(missing_ok=True)
    except Exception:
        pass


# ------------------------------------------------------------------ the voice on the graphics card
def _voice_cache():
    try:
        return json.loads(VOICE_TEST.read_text(encoding="utf-8"))
    except Exception:
        return None


def _ort_key():
    try:
        import onnxruntime as ort
        return f"{ort.__version__}|{','.join(ort.get_available_providers())}|{config.KOKORO_MODEL}"
    except Exception:
        return ""


def dml_available():
    try:
        import onnxruntime as ort
        return "DmlExecutionProvider" in ort.get_available_providers()
    except Exception:
        return False


def voice_providers():
    """Which onnxruntime providers his voice should use, given the setting and what the test found.
    'cpu': always the processor. 'gpu': the graphics card if it passed (else the processor, with a note).
    'auto': the graphics card only if it passed AND was faster."""
    want = config.VOICE_DEVICE
    if want == "cpu" or not dml_available():
        return ["CPUExecutionProvider"]
    c = _voice_cache()
    if not c or c.get("key") != _ort_key():
        return ["CPUExecutionProvider"]          # not tested yet: the test runs in the background after start
    if not c.get("ok"):
        return ["CPUExecutionProvider"]
    if want == "auto" and not c.get("faster"):
        return ["CPUExecutionProvider"]
    return ["DmlExecutionProvider", "CPUExecutionProvider"]


def needs_voice_test():
    if config.VOICE_DEVICE == "cpu" or not dml_available():
        return False
    c = _voice_cache()
    return not c or c.get("key") != _ort_key()


VOICE_TEST_CODE = r"""
import sys, time, json
sys.path.insert(0, sys.argv[1])
import numpy as np
import gpu, voice, config
from kokoro_onnx import Kokoro
model = config.MODELS_DIR / voice._kokoro_model_name()
voices = config.MODELS_DIR / "voices-v1.0.bin"
res = {}
for dev in ("cpu", "gpu"):
    k = voice.make_kokoro(model, voices, providers=["DmlExecutionProvider", "CPUExecutionProvider"] if dev == "gpu" else ["CPUExecutionProvider"])
    k.create("Warming up.", voice="bm_george", speed=1.0, lang="en-gb")
    t = time.time()
    for _ in range(2):
        s, sr = k.create("Good evening. All systems are running normally, and your schedule is clear.", voice="bm_george", speed=1.0, lang="en-gb")
    s = np.asarray(s, dtype=np.float32)
    ok = len(s) > sr and np.isfinite(s).all() and float(np.max(np.abs(s))) > 0.05
    res[dev] = {"t": (time.time() - t) / 2, "ok": bool(ok)}
print("VOICE_TEST " + json.dumps(res))
"""


def run_voice_test(log=print):
    """Tests his voice on the graphics card in a separate process (a bad driver can crash it outright, which
    must not take Jarvis down). Writes the result to the cache. Returns the cached dict."""
    import subprocess
    import tempfile
    out_file = Path(tempfile.gettempdir()) / f"jarvis-voicetest-{os.getpid()}.txt"
    res = {"key": _ort_key(), "t": time.time(), "ok": False, "faster": False, "note": ""}
    try:
        cmd = ([sys.executable, "--voice-gpu-test", str(out_file)] if config.FROZEN
               else [sys.executable, "-c", VOICE_TEST_CODE, str(config.BASE_DIR)])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=240,
                           creationflags=0x08000000 if sys.platform == "win32" else 0)
        text = (r.stdout or "") + (out_file.read_text(encoding="utf-8", errors="replace") if out_file.exists() else "")
        line = next((ln for ln in text.splitlines() if ln.startswith("VOICE_TEST ")), "")
        if not line:
            tail = (text or r.stderr or "").strip().splitlines()[-1:] or [f"exit code {r.returncode}"]
            res["note"] = f"The graphics card couldn't run his voice ({tail[0][:160]})."
        else:
            d = json.loads(line[len("VOICE_TEST "):])
            cpu, g = d.get("cpu", {}), d.get("gpu", {})
            res["ok"] = bool(g.get("ok"))
            res["cpu_s"], res["gpu_s"] = round(cpu.get("t", 0), 3), round(g.get("t", 0), 3)
            res["faster"] = res["ok"] and g.get("t", 99) < cpu.get("t", 0) * 0.9
            res["note"] = (("Works, and it's faster than the processor." if res["faster"] else
                            "Works, but it isn't faster than the processor here.") if res["ok"] else
                           "The graphics card made broken audio, so his voice stays on the processor.")
    except Exception as e:
        res["note"] = f"Test didn't run ({e})."
    finally:
        try:
            out_file.unlink()
        except OSError:
            pass
    try:
        VOICE_TEST.parent.mkdir(parents=True, exist_ok=True)
        VOICE_TEST.write_text(json.dumps(res), encoding="utf-8")
    except Exception:
        pass
    log(f"[voice] graphics card test: {res['note']}")
    return res


def forget_voice_test():
    try:
        VOICE_TEST.unlink()
    except OSError:
        pass
