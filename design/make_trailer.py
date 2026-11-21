"""
The trailer: films his real pages (desktop.html, saver.html) in a headless browser, adds a caption per shot, and
joins the shots into one 1080p, 30 fps video.

    python design/make_trailer.py OUT_DIR        (needs playwright + Chrome, ffmpeg)

Each shot is captured as fast as the browser allows with the real time of every frame, then laid out at those
times, so his ring and the scenes move at true speed. Each shot fades in and out of black inside its own file,
so joining them is a plain copy.
"""
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "trailer_out")
W, H, FPS = 1920, 1080, 30
UI = f"file://{ROOT}/ui"

TEL = [{"type": "widgets", "on": ["stats", "stocks"], "where": "right", "pos": {}},
       {"type": "telemetry", "cpu": 31, "ram": 58, "ram_used": 18.6, "ram_total": 32, "disk": 72, "disk_free": 212,
        "down_kbps": 800, "up_kbps": 90, "uptime": 40000},
       {"type": "w_gpu", "gpu": 44, "gpu_temp": 61, "vram": 6.1, "vram_total": 12},
       {"type": "w_stocks", "rows": [{"sym": "NVDA", "price": 196.42, "pct": 2.4}, {"sym": "AAPL", "price": 231.5, "pct": -0.6},
                                     {"sym": "AMD", "price": 138.02, "pct": -3.1}]}]
CAL = {"type": "pull", "kind": "calendar", "id": "c1", "data": {"day": "Saturday 21", "events": [
    {"start": "09:30", "end": "10:15", "title": "Run"}, {"start": "13:00", "end": "14:00", "title": "Lunch with Ana", "where": "Café Saúl"},
    {"start": "16:00", "end": "18:00", "title": "Blender: rig the knight"}, {"start": "20:30", "end": "22:30", "title": "Valorant with Leo"}]}}
SRC = {"type": "pull", "kind": "sources", "id": "s1", "data": {"query": "why did nvidia go up today", "items": [
    {"domain": "reuters.com", "title": "Chip stocks rise on data-centre demand"}, {"domain": "cnbc.com", "title": "Stocks making the biggest moves midday"},
    {"domain": "bloomberg.com", "title": "AI spending forecasts lifted for 2027"}]}}

CAPTION_CSS = """
#tcap{position:fixed;left:6vw;bottom:9vh;z-index:99;font:600 46px/1.15 'DM Sans',sans-serif;color:#fff;letter-spacing:-.01em;
  text-shadow:0 2px 24px rgba(0,0,0,.7);max-width:60vw;opacity:0;transform:translateY(10px);transition:opacity .6s,transform .6s}
#tcap.in{opacity:1;transform:none}
#tcap small{display:block;font:400 26px/1.4 'DM Sans',sans-serif;color:rgba(255,255,255,.78);margin-top:10px}
#tshade{position:fixed;inset:0;z-index:98;pointer-events:none;background:linear-gradient(to top,rgba(0,0,0,.86) 0%,rgba(0,0,0,.6) 22%,transparent 48%)}
"""

# (name, url, seconds, caption, sub, [(at_seconds, event)])
SHOTS = [
    ("01_title", "title", 4.0, None, None, []),
    ("02_bench", f"{UI}/desktop.html?scene=bench", 5.5, "He lives on your desktop.", "“Jarvis, what's my day look like?”",
     TEL + [(1.4, {"type": "state", "state": "thinking"}), (2.2, CAL), (2.3, {"type": "state", "state": "speaking"})]),
    ("03_station", f"{UI}/desktop.html?scene=station", 4.5, "Six worlds, and they're alive.", "Stars, dust, rain, a ship on the map.", []),
    ("04_archive", f"{UI}/desktop.html?scene=archive", 4.5, "The light follows your real day.", "Sunrise, sunset, and the weather outside.", []),
    ("05_signal", f"{UI}/desktop.html?scene=signal", 5.0, "He shows his work.", "Every answer comes with where it came from.",
     [(0.8, {"type": "state", "state": "speaking"}), (1.0, SRC)]),
    ("06_chart", f"{UI}/desktop.html?scene=chart", 4.5, "Your apps become the map.", "Render Ridge. Mount Inbox. Patchnote Shoals.", []),
    ("07_greenhouse", f"{UI}/desktop.html?scene=greenhouse&presence=orb&state=speaking", 5.0, "Rain when it rains where you are.",
     "And an orb, if you'd rather.", TEL),
    ("08_saver", f"{UI}/saver.html?scene=archive", 4.5, "Walk away, and his world keeps you company.", None, []),
    ("09_end", "end", 5.0, None, None, []),
]


def card_html(kind):
    logo = (ROOT / "assets" / "jarvis.svg").read_text(encoding="utf-8")
    if kind == "title":
        txt = "<h1>Jarvis</h1><p>A voice assistant for Windows that lives on your desktop.</p>"
    else:
        txt = "<h1>Jarvis</h1><p>Free for Windows 10 and 11.</p><p class=u>kizzyonroller.github.io/jarvis-2</p>"
    return f"""<!doctype html><html><body style="margin:0;background:radial-gradient(80% 90% at 50% 40%,#10253a,#050b12 70%);
height:100vh;display:grid;place-items:center;color:#eaf0ee;font-family:'DM Sans',sans-serif;overflow:hidden">
<style>.c{{text-align:center;animation:in 1.4s cubic-bezier(.2,.7,.1,1) both}} @keyframes in{{from{{opacity:0;transform:scale(.96)}}}}
.c svg{{width:220px;height:220px}}
h1{{font:400 120px/1 'Archivo Black',sans-serif;letter-spacing:.04em;margin:28px 0 14px}} p{{font-size:34px;color:#a9c1d4;margin:6px 0}}
.u{{font:500 30px 'DM Sans',sans-serif;color:#ffb347;margin-top:26px}}</style>
<div class=c>{logo}{txt}</div></body></html>"""


async def film(pg, shot, tmp):
    name, url, secs, cap, sub, events = shot
    if url in ("title", "end"):
        f = tmp / f"{name}.html"
        f.write_text(card_html(url), encoding="utf-8")
        await pg.goto(f"file://{f}")
    else:
        await pg.goto(url)
        await pg.wait_for_timeout(1500)                   # scene, labels and ambient settle before we roll
        for e in [e for e in events if not isinstance(e, tuple)]:
            await pg.evaluate("(e)=>window.J&&window.J.on(e)", e)
        if cap:
            await pg.add_style_tag(content=CAPTION_CSS)
            if "saver" in url:                              # the screensaver has its own clock at the bottom
                await pg.add_style_tag(content="#tcap{top:8vh;bottom:auto;left:auto;right:6vw;text-align:right}"
                                               "#tshade{background:linear-gradient(to bottom,rgba(0,0,0,.7),transparent 35%)}")
            await pg.evaluate("([c,s])=>{const sh=document.createElement('div');sh.id='tshade';document.body.append(sh);"
                              "const d=document.createElement('div');d.id='tcap';d.innerHTML=c+(s?'<small>'+s+'</small>':'');"
                              "document.body.append(d);setTimeout(()=>d.classList.add('in'),350)}", [cap, sub])
    timed = sorted([e for e in events if isinstance(e, tuple)], key=lambda x: x[0])
    talking = "speaking" in url or any(e.get("state") == "speaking" for _, e in timed)
    d = tmp / name
    d.mkdir(exist_ok=True)
    frames, t0 = [], time.perf_counter()
    cdp = await pg.context.new_cdp_session(pg)

    def on_frame(ev):                                       # Chrome streams a frame each time the page repaints
        p = d / f"{len(frames):05d}.jpg"
        p.write_bytes(__import__("base64").b64decode(ev["data"]))
        frames.append((p, time.perf_counter() - t0))
        asyncio.ensure_future(cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]}))
    cdp.on("Page.screencastFrame", on_frame)
    await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": W, "maxHeight": H, "everyNthFrame": 1})
    while (t := time.perf_counter() - t0) < secs:
        while timed and timed[0][0] <= t:
            await pg.evaluate("(e)=>window.J&&window.J.on(e)", timed.pop(0)[1])
        if talking:
            await pg.evaluate("()=>window.J&&window.J.on({type:'voice',v:.25+Math.random()*.6})")
        await asyncio.sleep(1 / 30)
    await cdp.send("Page.stopScreencast")
    await cdp.detach()
    return frames


def encode(name, frames, secs, tmp):
    """Lay the frames out at their real times, as constant 30 fps, with a fade in and out."""
    lst = tmp / f"{name}.txt"
    lines = []
    for i, (p, t) in enumerate(frames):
        nxt = frames[i + 1][1] if i + 1 < len(frames) else secs
        lines += [f"file '{p}'", f"duration {max(0.001, nxt - t):.4f}"]
    if frames[0][1] > 0:                                    # the first frame covers the time before it arrived
        lines[1] = f"duration {max(0.001, (frames[1][1] if len(frames) > 1 else secs)):.4f}"
    lines.append(f"file '{frames[-1][0]}'")
    lst.write_text("\n".join(lines))
    out, part = OUT / f"{name}.mp4", OUT / f"{name}.part.mp4"
    vf = (f"fps={FPS},scale={W}:{H},format=yuv420p,trim=duration={secs},"
          f"fade=t=in:st=0:d=0.45,fade=t=out:st={secs - 0.45:.2f}:d=0.45")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-vf", vf,
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", str(FPS), str(part)], check=True)
    os.replace(part, out)
    return out


async def main(only=None):
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "frames"
    tmp.mkdir(exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=os.environ.get("CHROME", "/usr/bin/google-chrome"),
                                    args=["--allow-file-access-from-files"])
        pg = await b.new_page(viewport={"width": W, "height": H})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        for shot in SHOTS:
            if only and shot[0] not in only:
                continue
            frames = await film(pg, shot, tmp)
            encode(shot[0], frames, shot[2], tmp)
            print(f"{shot[0]}: {len(frames)} frames in {shot[2]}s")
        await b.close()
        if errs:
            print("page errors:", errs)
    files = [OUT / f"{s[0]}.mp4" for s in SHOTS]
    if not all(f.exists() for f in files):
        return
    (OUT / "join.txt").write_text("\n".join(f"file '{f}'" for f in files))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(OUT / "join.txt"),
                    "-c", "copy", "-movflags", "+faststart", str(OUT / "jarvis-trailer.part.mp4")], check=True)
    os.replace(OUT / "jarvis-trailer.part.mp4", OUT / "jarvis-trailer.mp4")
    print("trailer:", OUT / "jarvis-trailer.mp4")


if __name__ == "__main__":
    asyncio.run(main(set(sys.argv[2:]) or None))
