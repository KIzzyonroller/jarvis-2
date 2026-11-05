"""
Dead by Daylight queue times and region status, from deadbyqueue.com (an unofficial fan site: Behaviour has no
public API for this).

The site fills its numbers in with JavaScript, so a plain download only gets "Loading...". Instead she opens the
page in a hidden, off-screen browser window, waits for the numbers, reads the page's text and closes it. Only when
you ask (and at most once every 10 minutes; the site itself refreshes about every 20). If the site changes or is
down, she says so instead of guessing.
"""
import threading
import time

URL = "https://www.deadbyqueue.com/"
CACHE_SECS = 600
_cache = {"at": 0, "text": ""}
_lock = threading.Lock()


def _read_page(timeout=25):
    import webview
    box = {"text": None}
    done = threading.Event()
    w = webview.create_window("dbd-queue", url=URL, hidden=True, width=1200, height=900, x=-32000, y=-32000)

    def grab():
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(2)
            try:
                txt = w.evaluate_js("document.body ? document.body.innerText : ''") or ""
            except Exception:
                continue
            if txt and "Loading queue data" not in txt and len(txt) > 400:
                box["text"] = txt
                break
        done.set()

    w.events.loaded += lambda: threading.Thread(target=grab, daemon=True).start()
    done.wait(timeout + 8)
    try:
        w.destroy()
    except Exception:
        pass
    return box["text"]


def queue_text():
    with _lock:
        if time.time() - _cache["at"] < CACHE_SECS and _cache["text"]:
            return _cache["text"], True
        try:
            txt = _read_page()
        except Exception as e:
            return f"Couldn't open deadbyqueue.com ({type(e).__name__}).", False
        if not txt:
            return "deadbyqueue.com didn't load its numbers (the site may be down or changed).", False
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        keep = "\n".join(lines)[:6000]
        _cache.update(at=time.time(), text=keep)
        return keep, False


def report(region=None, role=None):
    txt, cached = queue_text()
    if txt.startswith(("Couldn't", "deadbyqueue.com didn't")):
        return txt
    ask = []
    if region:
        ask.append(f"region: {region}")
    if role:
        ask.append(f"role: {role}")
    return ((f"From deadbyqueue.com ({'checked a few minutes ago' if cached else 'just now'}; unofficial, may vary with "
             f"MMR). Answer {'for ' + ', '.join(ask) if ask else 'with the regions most likely relevant'} in a "
             "sentence or two: queue times, and whether any region is down or marked inactive. Page text:\n") + txt)
