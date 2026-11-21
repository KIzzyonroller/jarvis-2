"""Small pure pieces of the 1.0.34+ features."""
import time

import numpy as np
import pytest

import config


def test_triggers_roundtrip():
    import triggers
    assert "Trigger set" in triggers.add("app", "turn the lights red", name="Dead by Daylight")
    assert "Trigger set" in triggers.add("time", "market and weather", at="8am", days="weekdays")
    assert "What time" in triggers.add("time", "x", at="25:00")
    assert "Dead by Daylight" in triggers.listing()
    assert "Removed" in triggers.remove("weekdays")


def test_trigger_app_matching_isnt_too_loose(monkeypatch):
    import triggers
    fired = []
    monkeypatch.setattr(triggers, "_fire", lambda r, why: fired.append(r["do"]))
    triggers.add("app", "steam vr stuff", name="SteamVR")
    triggers._app_started("steam.exe")            # "steam" must not fire a SteamVR trigger
    assert not any("steam vr" in f for f in fired)


def test_finder_times():
    import finder
    assert finder._since("last 3 months") is not None
    assert finder._since("whenever") is None


def test_voiceid_features_shape():
    voiceid = pytest.importorskip("voiceid")
    audio = (np.random.randn(16000 * 3) * 0.05).astype(np.float32)
    f = voiceid.fbank(audio)
    assert f.shape[1] == 80 and f.shape[0] > 250


def test_play_log_stats(monkeypatch):
    import gamemode
    w = gamemode.GameWatch.__new__(gamemode.GameWatch) if hasattr(gamemode, "GameWatch") else None
    if w is None:
        pytest.skip("no GameWatch class")


def test_jokes_store():
    import extras
    assert "Saved" in extras.joke_tool("add", "the toaster blamed for a lost match")
    assert "toaster" in extras.joke_tool("list")


def test_desktop_has_a_renderer_for_every_panel_kind():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    js = (root / "ui" / "desk_pulls.js").read_text(encoding="utf-8")
    m = re.search(r"const RENDER\s*=\s*\{(.*?)\}", js, re.S)
    assert m, "RENDER table not found in desk_pulls.js"
    kinds = set(re.findall(r"(\w+)\s*:", m.group(1)))
    used = set()
    for p in root.glob("*.py"):
        used |= set(re.findall(r"pulls\.pull\(\s*\"(\w+)\"", p.read_text(encoding="utf-8")))
    missing = used - kinds
    assert not missing, f"Python pulls these panel kinds but the desktop can't draw them: {missing}"


def test_startup_cleanup_never_deletes_the_learned_voice():
    """1.0.34-1.0.36: the voiceprint was saved to a file the startup cleanup deleted, so it never stuck."""
    import re
    from pathlib import Path
    import voiceid
    core_src = (Path(__file__).resolve().parent.parent / "core.py").read_text(encoding="utf-8")
    m = re.search(r"for old in \((.*?)\):", core_src, re.S)
    assert m and voiceid.PRINT not in m.group(1)


def test_undo_move_new_edit_delete(tmp_path, monkeypatch):
    import undo
    monkeypatch.setattr(config, "JARVIS_DIR", tmp_path / "J")
    a = tmp_path / "a.txt"
    a.write_text("one")
    b = tmp_path / "sub" / "a.txt"
    b.parent.mkdir()
    import shutil
    shutil.move(str(a), str(b))
    undo.record("move", "moved a.txt to sub", src=str(a), dst=str(b))
    assert "back" in undo.undo() and a.exists() and not b.exists()

    backup = undo.keep_copy(a)
    a.write_text("two")
    undo.record("edit", "edited a.txt", path=str(a), backup=backup, vault=backup)
    undo.undo()
    assert a.read_text() == "one"

    vault = undo.keep_copy(a)
    a.unlink()
    undo.record("delete", "deleted a.txt", path=str(a), vault=vault)
    undo.undo()
    assert a.read_text() == "one"

    assert undo.undo() == "Nothing to undo."


def test_undo_never_trashes_a_file_changed_since(tmp_path, monkeypatch):
    import os
    import undo
    monkeypatch.setattr(config, "JARVIS_DIR", tmp_path / "J")
    f = tmp_path / "made.docx"
    f.write_text("x")
    undo.record("new", "made made.docx", path=str(f), mtime=f.stat().st_mtime)
    os.utime(f, (f.stat().st_atime, f.stat().st_mtime + 60))
    assert "left it alone" in undo.undo() and f.exists()


def test_crash_reports_scrub_secrets():
    import crashreport
    txt = crashreport.scrub("key sk-ant-abc123DEF456ghi789 and gsk_ABCDEFGH12345678 api_key=hunter2 me@mail.com")
    assert "abc123" not in txt and "ABCDEFGH" not in txt and "hunter2" not in txt and "me@mail.com" not in txt


def test_crash_report_link_is_prefilled_and_short():
    import crashreport
    try:
        raise KeyError("automation")
    except KeyError as e:
        crashreport.record(e, "answering")
    url = crashreport.issue_url()
    assert url.startswith(crashreport.REPO + "/issues/new?") and "KeyError" in url and len(url) <= 7800
