"""
"Jarvis, run diagnostics": every part of him, tested in about ten seconds, with a pass / warn / fail list on the
desktop, a report file, and a fix for anything he knows how to fix ("Jarvis, fix it" or "fix the stock stream").

Each check is quick and read-only. A fix only runs when you say so, and anything that changes settings or files goes
through the usual approval card.
"""
import importlib
import json
import os
import shutil
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait as _wait
from datetime import datetime

import config

LAST = {"at": 0, "results": []}      # the most recent run, for "fix it"


def _r(name, status, detail, fix=None, fix_label=None):
    return {"name": name, "status": status, "detail": detail, "fix": fix, "fix_label": fix_label}


def _get(url, timeout=6, **kw):
    import requests
    return requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 Jarvis-diagnostics"}, **kw)


# ------------------------------------------------------------------ the checks (each returns one result)
def c_mic(core):
    L = getattr(core, "listener", None)
    if L is None:
        return _r("Microphone", "fail", "voice is off or the mic didn't open", "restart_voice", "Restart listening")
    name = getattr(L, "mic_name", "?")
    if getattr(core, "muted", False):
        return _r("Microphone", "warn", f"{name}: muted", "unmute", "Unmute")
    peak = getattr(L, "_peak", 0)
    time.sleep(2.5)                                      # listen for a moment
    peak = max(peak, getattr(L, "_peak", 0))
    if peak < 20:
        return _r("Microphone", "fail", f"{name}: sending silence (muted in Windows, taken by another app, or the wrong mic)",
                  "pick_mic", "List your mics")
    return _r("Microphone", "pass", f"{name}: hearing sound")


def c_speech(core):
    L = getattr(core, "listener", None)
    if L is None:
        return _r("Speech recognition", "fail", "not running", "restart_voice", "Restart listening")
    local = f"local {config.WHISPER_FAST} on {getattr(L, 'device', 'cpu')}"
    cloud = getattr(L, "cloud", None)
    if getattr(config, "PRIVATE", False):
        return _r("Speech recognition", "pass", local + " (private mode: nothing leaves the PC)")
    if cloud is None or not cloud.configured:
        return _r("Speech recognition", "pass", local + ", no cloud")
    if cloud.dead:
        return _r("Speech recognition", "fail", local + "; Groq key rejected", "open_keys", "Open the key settings")
    try:
        r = cloud._s().get("https://api.groq.com/openai/v1/models", timeout=6)
        if r.status_code == 401:
            return _r("Speech recognition", "fail", "Groq key rejected", "open_keys", "Open the key settings")
        return _r("Speech recognition", "pass" if r.ok else "warn", local + f" + Groq ({r.status_code})")
    except Exception as e:
        return _r("Speech recognition", "warn", local + f"; Groq unreachable ({type(e).__name__})")


def c_claude(core):
    brain = getattr(core, "brain", None)
    client = getattr(brain, "client", None)
    if client is None:
        return _r("Claude (his brain)", "fail", "no API client: is the key set?", "open_keys", "Open the key settings")
    try:
        client.models.list(limit=1)
        return _r("Claude (his brain)", "pass", f"key works; main model {config.MODEL}")
    except Exception as e:
        msg = str(e)[:120]
        if "401" in msg or "authentication" in msg.lower():
            return _r("Claude (his brain)", "fail", "key rejected", "open_keys", "Open the key settings")
        return _r("Claude (his brain)", "fail", f"{type(e).__name__}: {msg}")


def c_voice_out(core):
    sp = getattr(core, "speaker", None)
    if sp is None:
        return _r("His voice", "fail", "speaker not running")
    try:
        import sounddevice as sd
        out = sd.query_devices(kind="output")["name"]
    except Exception as e:
        return _r("His voice", "warn", f"can't read the output device ({type(e).__name__})")
    return _r("His voice", "pass", f"playing on {out}")


def c_internet(core):
    t = time.perf_counter()
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=3):
            ms = round((time.perf_counter() - t) * 1000)
        return _r("Internet", "pass" if ms < 150 else "warn", f"{ms} ms to Cloudflare")
    except OSError:
        return _r("Internet", "fail", "can't reach the internet")


def c_stocks(core):
    try:
        import stocks
        q = stocks.quote("AAPL")
        return _r("Stock prices", "pass", f"Yahoo answering (AAPL {q['price']:.2f})")
    except Exception as e:
        return _r("Stock prices", "fail", f"Yahoo not answering ({type(e).__name__})")


def c_stream(core):
    import livefeed
    S = livefeed.STREAM
    if S is None:
        return _r("Live price stream", "fail", "not started", "restart_stream", "Start the stream")
    if S.ok:
        return _r("Live price stream", "pass", "streaming")
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        return _r("Live price stream", "fail", "aiohttp missing (prices fall back to every 15 s)", "pip:aiohttp", "Install aiohttp")
    S.watch(["BTC-USD"], secs=20)                         # crypto ticks 24/7: a fair test
    for _ in range(24):
        time.sleep(0.5)
        if S.ok:
            return _r("Live price stream", "pass", "connected and ticking")
    return _r("Live price stream", "warn", "can't connect; prices update every 15 s instead", "restart_stream", "Reconnect")


def c_scores(core):
    try:
        r = _get("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard")
        return _r("Live scores", "pass" if r.ok else "fail", f"ESPN {r.status_code}")
    except Exception as e:
        return _r("Live scores", "fail", f"ESPN unreachable ({type(e).__name__})")


def c_flights(core):
    try:
        r = _get("https://api.adsb.lol/v2/callsign/UAL1")
        return _r("Flight tracking", "pass" if r.ok else "warn", f"adsb.lol {r.status_code}")
    except Exception as e:
        return _r("Flight tracking", "warn", f"adsb.lol unreachable ({type(e).__name__})")


def c_weather(core):
    try:
        r = _get("https://api.rainviewer.com/public/weather-maps.json")
        r2 = _get("https://api.open-meteo.com/v1/forecast?latitude=14.6&longitude=-90.5&current=temperature_2m")
        ok = r.ok and r2.ok
        return _r("Weather + radar", "pass" if ok else "warn", f"Open-Meteo {r2.status_code}, RainViewer {r.status_code}")
    except Exception as e:
        return _r("Weather + radar", "fail", f"unreachable ({type(e).__name__})")


def c_steam(core):
    import steam
    if not steam.ready():
        return _r("Steam", "warn", "no Steam key / account set (friends, sales, patch notes are off)", "open_apps", "Open Connected apps")
    try:
        steam.steamid()
        return _r("Steam", "pass", "account found")
    except Exception as e:
        return _r("Steam", "fail", f"{type(e).__name__}: {str(e)[:80]}", "open_apps", "Open Connected apps")


def c_lights(core):
    import smarthome
    av = smarthome.available()
    if not av["hue"] and not av["ha"]:
        return _r("Smart lights", "skip", "not set up")
    try:
        if av["hue"]:
            smarthome._hue("GET", "/lights")
        return _r("Smart lights", "pass", "Hue answering" if av["hue"] else "Home Assistant set")
    except Exception as e:
        return _r("Smart lights", "fail", f"bridge not answering ({type(e).__name__})", "rediscover_hue", "Find the Hue bridge again")


def c_discord(core):
    b = getattr(core, "discord_bot", None)
    if b is None:
        return _r("Discord bot", "skip", "not set up")
    st = b.view()
    if st.get("status") == "online":
        return _r("Discord bot", "pass", f"online as {st.get('name') or 'the bot'}")
    return _r("Discord bot", "fail", f"{st.get('status')}: {st.get('error') or 'not connected'}", "restart_discord", "Reconnect the bot")


def c_desktop(core):
    if not config.LIVING_DESKTOP:
        return _r("Living desktop", "skip", "off in Settings")
    d = getattr(core, "desk", None)
    if d is None:
        return _r("Living desktop", "warn", "not running (off, or it couldn't attach to the wallpaper)")
    return _r("Living desktop", "pass", f"scene: {config.DESK_SCENE}")


def c_ocr(core):
    try:
        import ocr  # noqa: F401
        importlib.import_module("winrt.windows.media.ocr")
        return _r("Reading text on screen", "pass", "Windows OCR available")
    except Exception as e:
        return _r("Reading text on screen", "warn", f"Windows OCR missing ({type(e).__name__})")


def c_finder(core):
    if os.name != "nt":
        return _r("File finder", "skip", "Windows only")
    try:
        import finder
        t = time.time()
        finder._index(["jarvis"], [], None, False, 3)
        return _r("File finder", "pass", f"Windows Search index answers ({(time.time() - t) * 1000:.0f} ms)")
    except Exception as e:
        return _r("File finder", "warn", f"Windows Search index unavailable ({type(e).__name__}); using a slower folder scan")


def c_triggers(core):
    try:
        import triggers
        rules = triggers.load()
        off = os.environ.get("JARVIS_TRIGGERS", "true").lower() == "false"
        return _r("Triggers", "warn" if off and rules else "pass",
                  (f"{len(rules)} set" if rules else "none set") + (", but switched off in Settings" if off else ""))
    except Exception as e:
        return _r("Triggers", "fail", f"triggers.json unreadable: {e}")


def c_documents(core):
    missing = []
    for mod in ("docx", "openpyxl", "pptx", "pypdf", "fpdf"):
        try:
            importlib.import_module(mod)
        except Exception:
            missing.append(mod)
    if missing:
        return _r("Making documents", "fail", "missing: " + ", ".join(missing), "pip:" + ",".join(missing), "Install them")
    return _r("Making documents", "pass", "Word, Excel, PowerPoint, PDF ready")


def c_disk(core):
    try:
        u = shutil.disk_usage(str(config.JARVIS_DIR))
        gb = u.free / 2**30
        return _r("Disk space", "pass" if gb > 10 else "warn" if gb > 3 else "fail", f"{gb:.0f} GB free where he keeps his files",
                  None if gb > 10 else "butler", None if gb > 10 else "Find what's taking space")
    except Exception as e:
        return _r("Disk space", "warn", str(e)[:80])


def c_settings(core):
    try:
        import settings
        settings.view()
        return _r("Settings file", "pass", "reads fine")
    except Exception as e:
        return _r("Settings file", "fail", f"can't read it ({type(e).__name__})", "repair_settings", "Back it up and repair it")


def c_voiceid(core):
    try:
        import voiceid
        st = voiceid.status()
    except Exception as e:
        return _r("Voice ID", "warn", f"unavailable ({type(e).__name__})")
    if not st["enrolled"]:
        return _r("Voice ID", "skip", "not set up (say \"learn my voice\")")
    return _r("Voice ID", "pass" if st["model"] else "fail", st["detail"], None if st["model"] else "voiceid_model", "Download the voice model")


CHECKS = [c_mic, c_speech, c_claude, c_voice_out, c_internet, c_stocks, c_stream, c_scores, c_flights, c_weather,
          c_steam, c_lights, c_discord, c_desktop, c_ocr, c_documents, c_disk, c_settings, c_voiceid, c_finder, c_triggers]


def run(core, show=True):
    out = []
    with ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(fn, core): fn for fn in CHECKS}
        done, pending = _wait(futs, timeout=20)
        for f, fn in futs.items():
            if f in done:
                try:
                    out.append(f.result())
                except Exception as e:
                    out.append(_r(fn.__name__[2:].replace("_", " ").title(), "fail", f"check crashed: {type(e).__name__}: {e}"))
            else:
                out.append(_r(fn.__name__[2:].replace("_", " ").title(), "warn", "check timed out"))
    order = {"fail": 0, "warn": 1, "pass": 2, "skip": 3}
    names = [fn.__name__ for fn in CHECKS]
    out.sort(key=lambda r: (order.get(r["status"], 9)))
    LAST.update(at=time.time(), results=out)
    try:
        lines = [f"Jarvis diagnostics, {datetime.now():%Y-%m-%d %H:%M}", ""]
        lines += [f"[{r['status'].upper():4}] {r['name']}: {r['detail']}" + (f"  (fix: {r['fix_label']})" if r["fix"] else "") for r in out]
        (config.JARVIS_DIR / "diagnostics.txt").write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        pass
    if show:
        try:
            import pulls
            pulls.pull("checklist", {"items": out, "at": datetime.now().strftime("%H:%M")}, id="diagnostics",
                       title="Diagnostics", ttl=300, focus=True, auto=False)
        except Exception:
            pass
    return out


def summary(out):
    bad = [r for r in out if r["status"] == "fail"]
    warn = [r for r in out if r["status"] == "warn"]
    ok = [r for r in out if r["status"] == "pass"]
    s = f"{len(ok)} passed, {len(warn)} warnings, {len(bad)} failed."
    if bad or warn:
        s += " " + " ".join(f"{r['status'].upper()} {r['name']}: {r['detail']}." + (f" [fix id: {r['fix']}: {r['fix_label']}]" if r["fix"] else "")
                            for r in bad + warn)
    return s + " (Full list is up on their desktop and in diagnostics.txt.)"


# ------------------------------------------------------------------ self-repair
def fix(core, fid=None):
    """Apply one fix (by id), or every fix from the last run when fid is None/'all'."""
    if not LAST["results"] or time.time() - LAST["at"] > 3600:
        run(core, show=False)
    todo = [r for r in LAST["results"] if r["fix"] and r["status"] in ("fail", "warn")]
    if fid and fid != "all":
        todo = [r for r in todo if r["fix"] == fid or fid.lower() in r["name"].lower()]
    if not todo:
        return "Nothing to fix" + (f" for {fid}." if fid and fid != "all" else ": everything I can fix is fine.")
    done = []
    for r in todo:
        try:
            done.append(f"{r['name']}: {_apply(core, r['fix'])}")
        except Exception as e:
            done.append(f"{r['name']}: the fix failed ({type(e).__name__}: {e})")
    return " ".join(done)


def _apply(core, fid):
    import tools
    if fid == "unmute":
        core.set_muted(False)
        return "unmuted."
    if fid == "restart_voice":
        threading.Timer(2.0, core._restart).start()
        return "restarting me in a couple of seconds (that restarts listening too)."
    if fid == "pick_mic":
        import speech
        mics = [m[1] for m in speech.mic_devices() if m[0] != "default"]
        return ("Your mics: " + "; ".join(mics[:8]) + ". Tell me which one, or pick it in Settings > Microphone. Also "
                "check Windows Settings > Privacy > Microphone lets desktop apps use it.")
    if fid in ("open_keys", "open_apps"):
        core.emit({"type": "open_settings", "page": "general" if fid == "open_keys" else "apps"})
        return "opened Settings on the right page."
    if fid == "restart_stream":
        import livefeed
        if livefeed.STREAM is None:
            livefeed.start(core.emit)
        livefeed.STREAM.wake.set()
        return "reconnecting the stream."
    if fid == "restart_discord":
        b = getattr(core, "discord_bot", None)
        if b is not None and hasattr(b, "stop"):
            try:
                b.stop()
            except Exception:
                pass
        core._start_discord_bot()
        return "reconnecting the bot."
    if fid == "rediscover_hue":
        import smarthome
        ip = smarthome.hue_bridge()
        return f"found the bridge at {ip}." if ip else "couldn't find it on the network (is it on and plugged into the router?)."
    if fid == "butler":
        return tools.butler_tool("report")
    if fid == "repair_settings":
        if not tools._confirm("Repair the settings file", "A backup is kept next to it; broken lines are dropped."):
            return "left it alone."
        p = config.ENV_FILE
        if p.exists():
            shutil.copy2(p, p.with_suffix(".env.bak"))
            good = [l for l in p.read_text(encoding="utf-8", errors="replace").splitlines()
                    if not l.strip() or l.lstrip().startswith("#") or "=" in l]
            p.write_text("\n".join(good) + "\n", encoding="utf-8")
        return "repaired (backup saved as .env.bak)."
    if fid.startswith("pip:"):
        import sys
        if getattr(sys, "frozen", False):
            return "that's part of the installed app: the next update brings it back (or reinstall from GitHub Releases)."
        pkgs = fid[4:].split(",")
        if not tools._confirm("Install Python packages", "pip install " + " ".join(pkgs)):
            return "skipped."
        import subprocess
        r = subprocess.run([sys.executable, "-m", "pip", "install", *pkgs], capture_output=True, text=True, timeout=600)
        return "installed; restart me to use them." if r.returncode == 0 else f"pip failed: {r.stderr[-200:]}"
    if fid == "voiceid_model":
        import voiceid
        return "downloaded." if voiceid.ensure_model() else "couldn't download it (check the internet check above)."
    return "I don't know how to fix that one yet."
