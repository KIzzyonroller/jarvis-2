"""
Instant file finder: "find that PDF from my landlord last month", "where's the excel I made for the budget".

Uses Windows Search's index (the same one the Start menu uses), so it answers in well under a second across your
whole user folder and can match words INSIDE documents, not just names. Falls back to a quick folder walk when the
index isn't available. Results go up as a panel he can open from ("open the second one").

Only searches inside your user folder, and never in hidden or secret places (.ssh, browser profiles, .env...).
"""
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import config

KINDS = {"pdf": ["pdf"], "word": ["doc", "docx"], "doc": ["doc", "docx", "pdf", "txt", "rtf", "odt"],
         "excel": ["xls", "xlsx", "csv"], "spreadsheet": ["xls", "xlsx", "csv", "ods"],
         "powerpoint": ["ppt", "pptx"], "slides": ["ppt", "pptx", "key"],
         "image": ["png", "jpg", "jpeg", "gif", "webp", "heic", "bmp"], "photo": ["png", "jpg", "jpeg", "heic", "webp"],
         "video": ["mp4", "mov", "mkv", "avi", "webm"], "audio": ["mp3", "wav", "flac", "m4a", "ogg"],
         "zip": ["zip", "rar", "7z"], "code": ["py", "js", "ts", "cpp", "c", "cs", "java", "html", "css", "json"],
         "text": ["txt", "md", "log"]}
BLOCK = re.compile(r"[\\/](\.ssh|\.gnupg|appdata[\\/](local|roaming)[\\/](google|microsoft[\\/]edge|mozilla|bravesoftware)"
                   r"|\.aws|\.azure|\.kube)([\\/]|$)|\.(env|kdbx|pem|key|pfx|p12)$", re.I)
LAST = {"results": []}


def _since(when):
    w = (when or "").lower().strip()
    now = datetime.now()
    if not w or w in ("any", "anytime", "ever"):
        return None
    table = {"today": 1, "yesterday": 2, "this week": 7, "last week": 14, "this month": 31, "last month": 62,
             "recent": 14, "recently": 14, "this year": 366, "last year": 731}
    if w in table:
        return now - timedelta(days=table[w])
    m = re.match(r"(?:last|past)?\s*(\d+)\s*(day|week|month|year)s?", w)
    if m:
        n, u = int(m.group(1)), m.group(2)
        return now - timedelta(days=n * {"day": 1, "week": 7, "month": 31, "year": 366}[u])
    return None


def _esc(s):
    return s.replace("'", "''")


def _index(words, exts, since, inside, limit):
    """Windows Search over the user folder. Raises if the index isn't reachable."""
    import comtypes
    import comtypes.client
    try:
        comtypes.CoInitialize()
    except OSError:
        pass
    scope = "file:" + str(config.HOME).replace("\\", "/")
    conds = [f"SCOPE='{_esc(scope)}'"]
    for w in words:
        w = _esc(w.replace('"', ""))
        if inside:
            conds.append(f"(System.FileName LIKE '%{w}%' OR CONTAINS(*, '\"{w}*\"'))")
        else:
            conds.append(f"System.FileName LIKE '%{w}%'")
    if exts:
        conds.append("(" + " OR ".join(f"System.FileExtension = '.{e}'" for e in exts) + ")")
    if since:
        conds.append(f"System.DateModified >= '{since:%Y-%m-%d %H:%M:%S}'")
    conds.append("System.ItemType <> 'Directory'")
    sql = (f"SELECT TOP {int(limit)} System.ItemPathDisplay, System.DateModified, System.Size FROM SystemIndex "
           f"WHERE {' AND '.join(conds)} ORDER BY System.DateModified DESC")
    rs = comtypes.client.CreateObject("ADODB.Recordset", dynamic=True)
    rs.Open(sql, "Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
    out = []
    try:
        while not rs.EOF:
            p = rs.Fields.Item("System.ItemPathDisplay").Value
            if p and not BLOCK.search(p):
                out.append(p)
            rs.MoveNext()
    finally:
        try:
            rs.Close()
        except Exception:
            pass
    return out


def _walk(words, exts, since, limit):
    roots = [config.HOME / d for d in ("Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music", "OneDrive")]
    hits, deadline = [], time.time() + 6
    cut = since.timestamp() if since else 0
    for root in roots:
        if not root.exists():
            continue
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if not d.startswith(".") and d.lower() not in ("node_modules", "appdata", "__pycache__")]
            for f in fns:
                fl = f.lower()
                if exts and fl.rsplit(".", 1)[-1] not in exts:
                    continue
                if not all(w in fl for w in words):
                    continue
                p = os.path.join(dp, f)
                try:
                    if cut and os.path.getmtime(p) < cut:
                        continue
                except OSError:
                    continue
                if not BLOCK.search(p):
                    hits.append(p)
            if time.time() > deadline or len(hits) >= limit * 3:
                break
    hits.sort(key=lambda p: -os.path.getmtime(p) if os.path.exists(p) else 0)
    return hits[:limit]


def find(query="", kind=None, when=None, inside=True, limit=12, show=True):
    stop = {"the", "a", "an", "my", "file", "files", "that", "from", "for", "of", "i", "made", "with", "called", "named"}
    words = [w for w in re.findall(r"[\w\-']+", (query or "").lower()) if w not in stop][:5]
    exts = []
    for w in list(words):
        if w in KINDS and (kind is None or kind == w):
            exts += KINDS[w]
            words.remove(w)
    if kind:
        exts = KINDS.get(kind.lower(), [kind.lower().lstrip(".")])
    since = _since(when)
    via = "index"
    try:
        hits = _index(words, exts, since, inside, limit)
    except Exception as e:
        print(f"[finder] Windows Search unavailable ({e}); walking folders instead")
        via = "walk"
        hits = _walk(words, exts, since, limit)
    LAST["results"] = hits
    if not hits:
        return (f"Nothing found for '{query}'" + (f" ({kind})" if kind else "") + (f" from {when}" if since else "") +
                (". Windows Search wasn't available, so I only looked through Desktop, Documents, Downloads and media "
                 "folders by name." if via == "walk" else ". Try fewer or different words, or a wider time."))
    rows = []
    for i, p in enumerate(hits, 1):
        try:
            st = os.stat(p)
            when_s = datetime.fromtimestamp(st.st_mtime).strftime("%b %d")
            size = f"{st.st_size / 1e6:.1f} MB" if st.st_size > 1e6 else f"{max(1, st.st_size // 1000)} KB"
        except OSError:
            when_s, size = "", ""
        rows.append({"n": i, "name": Path(p).name, "folder": str(Path(p).parent).replace(str(config.HOME), "~"),
                     "when": when_s, "size": size, "path": p})
    if show:
        try:
            import pulls
            pulls.pull("files", {"query": query, "rows": rows, "via": via}, id="finder", title="Found", ttl=180, auto=False)
        except Exception as e:
            print(f"[finder] panel: {e}")
    return (f"Found {len(rows)} (newest first, numbered on screen):\n" +
            "\n".join(f"{r['n']}. {r['name']} - {r['folder']} ({r['when']}, {r['size']})" for r in rows) +
            "\nTo open one, use files open with its full path: " + "; ".join(f"{r['n']}={r['path']}" for r in rows[:6]))


def pick(n):
    try:
        return LAST["results"][int(n) - 1]
    except (IndexError, ValueError, TypeError):
        return None
