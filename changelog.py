"""
The "What's new" pop-up. CHANGELOG.md (shipped with him) lists every release, newest first, each starting with
"## <version>". After an update he shows everything added since the version you had before, once.
"""
import re

import config


def _read():
    try:
        return (config.RES_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError:
        return ""


def sections(text=None):
    """[(version, notes)], newest first."""
    out = []
    for m in re.finditer(r"^##\s+(\S+)\s*\n(.*?)(?=^##\s|\Z)", text if text is not None else _read(), re.S | re.M):
        out.append((m.group(1).strip(), m.group(2).strip()))
    return out


def since(seen_version, text=None, cap=20):
    """Notes for every release newer than seen_version (all of the latest few if it isn't listed)."""
    secs = sections(text)
    if seen_version not in [v for v, _ in secs]:
        return secs[:1]                          # can't tell what they've seen: just the newest, not the whole history
    picked = []
    for v, notes in secs:
        if v == seen_version:
            break
        picked.append((v, notes))
    return picked[:cap]


def as_markdown(picked):
    if len(picked) == 1:
        return picked[0][1]
    return "\n\n".join(f"## {v}\n{n}" for v, n in picked)


def latest_version(text=None):
    secs = sections(text)
    return secs[0][0] if secs else None


def short(notes, titles_only=False):
    """The skim version: each bullet's bold title plus its first sentence (or just the titles, for a huge release);
    sub-points only if they have a title."""
    out = []
    for line in notes.splitlines():
        m = re.match(r"^(\s*)- (.*)$", line)
        if not m:
            continue
        indent, body = m.groups()
        t = re.match(r"^(\*\*.+?\*\*)\s*(.*)$", body)
        if indent and not t:
            continue
        if t:
            first = "" if titles_only else (re.split(r"(?<=[.!?])\s+(?=[A-Z\"(])", t.group(2), 1)[0] if t.group(2) else "")
            out.append(f"{indent}- {t.group(1)} {first}".rstrip())
        else:
            out.append(f"- {re.split(r'(?<=[.!?])\s+(?=[A-Z])', body, 1)[0]}")
    return "\n".join(out)


def for_discord(version=None, picked=None, name="Juno", full=False):
    """A release's notes as Discord messages (each under 2000 characters): a header, then the bullets. Discord shows
    **bold**, - bullets and nested bullets fine; headings are turned into bold lines. By default the skim version
    (titles + first sentence); full=True for everything."""
    secs = sections()
    if picked is None:
        if version:
            picked = [s for s in secs if s[0] == version]
            if not picked:
                return []
        else:
            picked = secs[:1]
    msgs = []
    for v, notes in picked:
        body = re.sub(r"^#{1,6}\s*(.+)$", r"**\1**", notes, flags=re.M)
        if not full:
            tail = f"\n-# Ask me \"changelog full {v}\" for all the details."
            text = f"## {name} {v} is out\n" + short(body).strip() + tail
            if len(_split(text)) > 2:                       # a huge release: just the headlines
                text = f"## {name} {v} is out\n" + short(body, titles_only=True).strip() + tail
        else:
            text = f"## {name} {v} is out\n" + body.strip()
        msgs += _split(text)
    return msgs


def _split(text, size=1900):
    """Split at bullet boundaries so no message ends mid-sentence."""
    out, cur = [], ""
    for line in text.splitlines():
        if len(cur) + len(line) + 1 > size and cur:
            out.append(cur.rstrip())
            cur = ""
        while len(line) > size:                       # one enormous line: hard split at a space
            cut = line.rfind(" ", 0, size) or size
            out.append(line[:cut])
            line = line[cut:].lstrip()
        cur += line + "\n"
    if cur.strip():
        out.append(cur.rstrip())
    if len(out) > 1:
        out = [m + f"\n-# ({i + 1}/{len(out)})" for i, m in enumerate(out)]
    return out


def save_for_discord():
    """Write the newest release, ready to paste into Discord, to her data folder. Returns the path."""
    msgs = for_discord(full=True)
    p = config.JARVIS_DIR / "changelog_for_discord.txt"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(("\n\n----- next message -----\n\n").join(msgs) + "\n", encoding="utf-8")
    except OSError:
        return None
    return p
