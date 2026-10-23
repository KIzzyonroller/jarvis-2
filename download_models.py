"""Downloads the Kokoro voice (about 350 MB), one time. Run by setup.bat, or by the installed app on its
first start (ensure_voice), since the installer itself stays small."""
import sys
import urllib.request
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config
    DEST = config.MODELS_DIR
except Exception:
    DEST = Path(__file__).resolve().parent / "models"
FILES = ["voices-v1.0.bin", "kokoro-v1.0.onnx"]
TAGS = ["model-files-v1.0", "model-files-v1.1"]
BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/{tag}/{name}"


def fetch(name, urls=None, progress=None):
    """progress(name, done_bytes, total_bytes), if given, is called as it downloads."""
    DEST.mkdir(parents=True, exist_ok=True)
    target = DEST / name
    if target.exists() and target.stat().st_size > 1_000_000:
        print(f"  {name}: already downloaded")
        return True
    for url in (urls or [BASE.format(tag=tag, name=name) for tag in TAGS]):
        tag = url.rsplit("/", 2)[-2]
        tmp = target.with_suffix(target.suffix + ".part")
        try:
            with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress is not None:
                        progress(name, done, total)
                    elif total:
                        pct = done * 100 // total
                        bar = "#" * (pct // 4)
                        print(f"\r  {name}: [{bar:<25}] {pct:3d}%  {done / 2**20:.0f}/{total / 2**20:.0f} MB", end="", flush=True)
            print()
            tmp.replace(target)
            return True
        except Exception as e:
            print(f"\n  {name}: {tag} failed ({e})")
            tmp.unlink(missing_ok=True)
    return False


def have_voice():
    return all((DEST / n).exists() and (DEST / n).stat().st_size > 1_000_000 for n in FILES)


def ensure_voice(progress=None, log=print):
    """For the installed app: fetch the voice if it's missing. Returns True when it's there."""
    if have_voice():
        return True
    ok = all(fetch(n, progress=progress) for n in FILES)
    if ok:
        log("[voice] Kokoro voice downloaded")
    return ok


def pick_fastest_voice():
    """Time both Kokoro models on a couple of sentences and remember the faster one. On some CPUs the
    compressed model is quicker, on others (no fast int8 instructions) it's actually slower."""
    import time
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from voice import make_kokoro
    except Exception as e:
        print(f"  couldn't compare voice models ({e}); keeping the full one")
        return
    lines = ["On it.", "Spotify's open behind your game. Want me to put something on?"]
    times = {}
    for tag, name in (("full", "kokoro-v1.0.onnx"), ("lite", "kokoro-v1.0.int8.onnx")):
        try:
            k = make_kokoro(DEST / name, DEST / "voices-v1.0.bin")
            k.create("Warm up.", voice="bm_lewis", speed=1.05, lang="en-gb")
            t = time.time()
            for line in lines:
                k.create(line, voice="bm_lewis", speed=1.05, lang="en-gb")
            times[tag] = time.time() - t
            del k
        except Exception as e:
            print(f"  {tag} voice model failed the test ({e})")
    if not times:
        return
    pick = min(times, key=times.get)
    if "full" in times and times[pick] > times["full"] * 0.85:
        pick = "full"                           # only switch if the compressed one is clearly faster
    (DEST / "kokoro_pick.txt").write_text(pick, encoding="utf-8")
    print("  " + ", ".join(f"{k}: {v:.2f}s" for k, v in times.items()) + f"  -> using the {pick} voice model")


if __name__ == "__main__":
    DEST.mkdir(exist_ok=True)
    print("Downloading the Kokoro voice (one time, about 350 MB)...")
    ok = all(fetch(n) for n in FILES)
    if not ok:
        print("Voice download failed. Jarvis will use the Microsoft online voice instead. Re-run setup.bat to try again.")
        sys.exit(1)
    print("Voice ready.")
    print("Downloading the compressed voice model too (about 90 MB) to see which is faster on this PC...")
    if fetch("kokoro-v1.0.int8.onnx"):
        pick_fastest_voice()

