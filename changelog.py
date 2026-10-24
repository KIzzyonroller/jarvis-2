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


def since(seen_version, text=None, cap=6):
    """Notes for every release newer than seen_version (all of the latest few if it isn't listed)."""
    secs = sections(text)
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
