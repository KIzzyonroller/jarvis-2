"""
Where her time goes, per question: a measuring tape for the speed pass.

Every answer adds one line to speed.jsonl in her data folder (Documents\\Jarvis): how long each step took between you
stopping talking and her first sound. No words are stored: only timings, which model answered, which tools ran,
how many tokens were sent and whether Claude's saved copy of her instructions was reused (cache).

  hear      you stopped talking -> she knew what you said (noticing the pause + transcription + a beat for more)
  prep      she starts the turn -> the request goes out (local work, screenshots she attaches...)
  claude    request out -> Claude's first word back (for the first round; tool rounds are counted separately)
  tools     time spent running tools (opening apps, searching...) and the extra Claude rounds after them
  voice     first word of text -> first sound (waiting for the end of the first sentence + making the audio)
  total     you stopped talking (or pressed enter) -> first sound

"Speed report" (or the speed_report tool) sums it up: medians and slow cases, split by fast/main model, with or
without tools, and cold (first question after a pause) vs warm.
"""
import json
import statistics
import threading
import time

import config

FILE = "speed.jsonl"
KEEP = 3000
_lock = threading.Lock()


def path():
    return config.JARVIS_DIR / FILE


def record(rec):
    rec["t"] = round(time.time(), 1)
    line = json.dumps(rec, separators=(",", ":"))
    with _lock:
        p = path()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            if p.stat().st_size > 1_500_000:                    # keep the newest few thousand
                lines = p.read_text(encoding="utf-8").splitlines()[-KEEP:]
                p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except OSError as e:
            print(f"[speed] couldn't log: {e}")
    parts = [f"{k} {rec[k]:.2f}s" for k in ("hear", "prep", "claude", "tools", "voice") if rec.get(k) is not None]
    print(f"[speed] total {rec.get('total', 0):.2f}s = " + ", ".join(parts) +
          f"  ({rec.get('model', '?')}, {rec.get('in_tok', 0)} in / {rec.get('cache_read', 0)} cached"
          f"{', ' + '+'.join(rec['tools_used']) if rec.get('tools_used') else ''})")


def load(hours=None):
    p = path()
    if not p.exists():
        return []
    out = []
    since = time.time() - hours * 3600 if hours else 0
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("t", 0) >= since:
            out.append(r)
    return out


def _stats(rows, key):
    v = sorted(r[key] for r in rows if isinstance(r.get(key), (int, float)))
    if not v:
        return None
    p90 = v[min(len(v) - 1, int(len(v) * 0.9))]
    return statistics.median(v), p90, len(v)


def report(hours=None):
    rows = [r for r in load(hours) if not r.get("interrupted") and r.get("total") is not None]
    if not rows:
        return "No timings yet. Use her for a while (a day of normal use is plenty), then ask again."
    lines = [f"{len(rows)} answers" + (f" in the last {hours:g} hours" if hours else "") + ". Median / slowest 10%:"]

    def block(title, rs):
        if not rs:
            return
        cells = []
        for k in ("total", "hear", "prep", "claude", "tools", "voice"):
            s = _stats(rs, k)
            if s:
                cells.append(f"{k} {s[0]:.1f}/{s[1]:.1f}s")
        lines.append(f"- {title} ({len(rs)}): " + ", ".join(cells))

    block("Everything", rows)
    block("Fast model, no tools", [r for r in rows if r.get("quick") and not r.get("tools_used")])
    block("Main model, no tools", [r for r in rows if not r.get("quick") and not r.get("tools_used")])
    block("With tools", [r for r in rows if r.get("tools_used")])
    block("Cold (nothing cached)", [r for r in rows if r.get("cold")])
    block("Warm (cached)", [r for r in rows if not r.get("cold")])
    block("Spoken", [r for r in rows if r.get("source") == "voice"])
    block("Typed", [r for r in rows if r.get("source") == "typed"])
    tok = _stats(rows, "in_tok")
    if tok:
        lines.append(f"- Tokens sent per question: median {tok[0]:.0f}, of which cached "
                     f"{(_stats(rows, 'cache_read') or (0,))[0]:.0f}.")
    from collections import Counter
    c = Counter(t for r in rows for t in (r.get("tools_used") or []))
    if c:
        lines.append("- Tools used most: " + ", ".join(f"{n} x{k}" for n, k in c.most_common(8)) + ".")
    slow = sorted(rows, key=lambda r: -r["total"])[:5]
    lines.append("- Slowest: " + "; ".join(
        f"{r['total']:.1f}s ({max(('hear', 'prep', 'claude', 'tools', 'voice'), key=lambda k: r.get(k) or 0)} was the "
        f"biggest part)" for r in slow) + ".")
    text = "\n".join(lines)
    try:
        (config.JARVIS_DIR / "speed_report.txt").write_text(text + "\n", encoding="utf-8")
    except OSError:
        pass
    return text
