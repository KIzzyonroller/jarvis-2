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


@pytest.mark.parametrize("text,want", [
    ("what's 15% of 240", "36"), ("convert 5 miles to km", "8.047"), ("350 fahrenheit in celsius", "176.7"),
    ("what is 2 to the power of 10", "1,024"), ("square root of 144", "12"), ("12 is what percent of 48", "25%"),
    ("200 grams of flour in cups", "1.6"), ("how many cups in a liter", "4.227"),
])
def test_calc(text, want):
    import calc
    r = calc.answer(text, offline=True)
    assert r and want in r[0], r


@pytest.mark.parametrize("text", ["what's the capital of france", "what time is it", "what's up"])
def test_calc_leaves_questions_alone(text):
    import calc
    assert calc.answer(text, offline=True) is None


def test_calc_rejects_code():
    import calc
    assert calc.arithmetic("__import__('os').system('x')") is None
    assert calc.arithmetic("9**9**9") is None


def test_clipboard_history_skips_secrets():
    import cliphist
    cliphist.ITEMS.clear()
    cliphist.add_text("sk-ant-api03-abcdefghijklmnop")
    cliphist.add_text("Tr0ub4dor&3xQ9!zK")
    cliphist.add_text("https://example.com/some/long/link?x=1")
    cliphist.add_text("meet at 5 at the usual place")
    texts = [i["text"] for i in cliphist.ITEMS]
    assert texts == ["https://example.com/some/long/link?x=1", "meet at 5 at the usual place"]


def test_duplicates_found_and_keeper_is_sensible(tmp_path, monkeypatch):
    import dupes
    monkeypatch.setattr(dupes, "MIN_SIZE", 10)
    a = tmp_path / "Pictures" / "cat.jpg"
    b = tmp_path / "Downloads" / "cat (1).jpg"
    c = tmp_path / "Downloads" / "other.bin"
    for p in (a, b, c):
        p.parent.mkdir(parents=True, exist_ok=True)
    a.write_bytes(b"x" * 5000)
    b.write_bytes(b"x" * 5000)
    c.write_bytes(b"y" * 5000)
    groups, wasted = dupes.scan(str(tmp_path), seconds=10)
    assert len(groups) == 1 and groups[0]["keep"] == str(a) and groups[0]["extra"] == [str(b)] and wasted == 5000


def test_bedtime_maths():
    from datetime import datetime
    import winddown
    assert winddown._bed_dt(datetime(2026, 1, 1, 22, 0), (0, 30)) == datetime(2026, 1, 2, 0, 30)
    assert winddown._bed_dt(datetime(2026, 1, 2, 0, 10), (23, 0)) == datetime(2026, 1, 1, 23, 0)
    assert winddown._night_key(datetime(2026, 1, 2, 0, 10)) == winddown._night_key(datetime(2026, 1, 1, 22, 0))


def test_price_from_structured_data(monkeypatch):
    import io
    import pricewatch
    html = b'<html><title>GPU</title><script type="application/ld+json">{"@type":"Product","name":"RTX 5070",' \
           b'"offers":{"@type":"Offer","price":"549.99","priceCurrency":"USD"}}</script></html>'

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(pricewatch.urllib.request, "urlopen", lambda *a, **k: R(html))
    assert pricewatch.page_price("https://shop.example/gpu") == (549.99, "USD", "RTX 5070")


def test_quiet_manual_strings():
    import quiet
    quiet.set_manual("off")
    assert quiet.MANUAL["on"] is False
    quiet.set_manual("auto")
    assert quiet.MANUAL["on"] is None


def test_guest_identify(monkeypatch, tmp_path):
    """A friend's voice is recognised as a guest; a stranger is nobody; the owner is the owner."""
    import voiceid
    monkeypatch.setattr(config, "JARVIS_DIR", tmp_path)
    rng = np.random.default_rng(1)
    me, leo, stranger = (v / np.linalg.norm(v) for v in rng.normal(size=(3, 256)).astype(np.float32))
    monkeypatch.setattr(voiceid, "_print", me)
    monkeypatch.setattr(voiceid, "_guests", {"Leo": leo.tolist()})
    monkeypatch.setenv("JARVIS_VOICE_ID", "true")
    monkeypatch.setenv("JARVIS_GUEST_MODE", "true")
    audio = np.zeros(16000 * 2, dtype=np.float32)
    for vec, want in ((me, "owner"), (leo, "Leo"), (stranger, None)):
        monkeypatch.setattr(voiceid, "embed", lambda a, v=vec: v)
        monkeypatch.setattr(voiceid, "_save", lambda *a, **k: None)
        assert voiceid.identify(audio)[0] == want


def test_guests_cant_use_owner_tools():
    import tools
    tools.GUEST["on"] = True
    try:
        assert "Not for guests" in tools.run_tool("files", {"action": "list"})
        assert tools._confirm("Delete everything") is False
    finally:
        tools.GUEST["on"] = False


@pytest.mark.parametrize("text,ok", [("wait no I meant tomorrow", True), ("actually make it Spotify", True),
                                     ("yeah", False), ("the weather is nice", False)])
def test_barge_in_cues(text, ok, monkeypatch):
    import core
    monkeypatch.setenv("JARVIS_BARGE_IN", "true")
    c = core.Core.__new__(core.Core) if hasattr(core, "Core") else None
    if c is None:
        pytest.skip("no Core class")
    c._guest_next = None
    import voiceid
    monkeypatch.setattr(voiceid, "on", lambda: False)
    assert c._barge_in_ok(text, None) is ok


@pytest.mark.parametrize("text,tone", [("we won the tournament!", "excited"), ("my grandma passed away", "soft"),
                                       ("my bank account got hacked", "serious")])
def test_tone(text, tone, monkeypatch):
    import core
    c = core.Core.__new__(core.Core)
    import quiet
    monkeypatch.setitem(quiet.STATE, "on", False)
    assert c._pick_tone(text) == tone


def test_lingo_roundtrip():
    import extras
    assert "means" in extras.lingo_tool("add", "the squad", "Leo, Ana and Max")
    assert "the squad" in extras.lingo_note()
    assert "Forgot" in extras.lingo_tool("remove", "the squad")


def test_bilingual_prompt_and_rule(monkeypatch):
    import langs
    monkeypatch.setattr(config, "LANGUAGE", "es-en")
    monkeypatch.setattr(config, "LANGUAGES", True)
    assert "Spanish and English" in langs.reply_rule()


@pytest.mark.parametrize("text,want", [
    ("this day last year", "2025-11-21"), ("yesterday", "2026-11-20"), ("last tuesday", "2026-11-17"),
    ("3 weeks ago", "2026-10-31"), ("march 3rd", "2026-03-03"), ("december 25", "2025-12-25"), ("2024-07-04", "2024-07-04"),
])
def test_timeline_dates(text, want):
    from datetime import date
    import timeline
    assert timeline.parse_day(text, today=date(2026, 11, 21)).isoformat() == want


def test_habit_needs_four_days_at_a_similar_time():
    from datetime import datetime
    import patterns
    asks = [(datetime(2026, 11, d, 8, m).timestamp(), "market and weather") for d, m in ((16, 2), (17, 10), (18, 5), (19, 20), (20, 1))]
    asks += [(datetime(2026, 11, 16, 15, 0).timestamp(), "open spotify")]
    hs = patterns.time_habits(asks)
    assert len(hs) == 1 and hs[0]["do"] == "market and weather" and hs[0]["at"] == "08:00" and hs[0]["days"] == "weekdays"
    assert patterns.time_habits(asks[:3]) == []


def test_plugins_need_approval_and_switch_off_when_changed(tmp_path, monkeypatch):
    import plugins
    monkeypatch.setattr(config, "JARVIS_DIR", tmp_path)
    plugins.LOADED.clear()
    d = plugins.folder()
    assert (d / "example_coin_flip.py").exists()
    got = {}
    reg = lambda spec, fn: got.__setitem__(spec["name"], fn)
    assert plugins.load(reg) == 0                                    # off until approved
    assert "Turned on" in plugins.enable("example_coin_flip.py", lambda t, dd: True)
    assert plugins.load(reg) == 2
    assert got["plugin_example_coin_flip_flip"](times=3).count(",") == 2
    (d / "example_coin_flip.py").write_text((d / "example_coin_flip.py").read_text() + "\n# changed\n")
    got.clear()
    assert plugins.load(reg) == 0                                    # changed: off again
    assert "Left it off" in plugins.enable("example_coin_flip.py", lambda t, dd: False)


def test_plugin_crash_is_contained(tmp_path, monkeypatch):
    import plugins
    monkeypatch.setattr(config, "JARVIS_DIR", tmp_path)
    run = plugins._guard("bad.py", lambda **k: 1 / 0)
    assert "failed" in run()


def test_what_he_knows_lists_and_deletes(tmp_path, monkeypatch):
    import knows
    import tools
    monkeypatch.setattr(config, "JARVIS_DIR", tmp_path)
    tools.remember("likes black coffee")
    secs = knows.sections(None)
    mem = next(s for s in secs if s["id"] == "memory")
    assert mem["items"] and "black coffee" in mem["items"][0]["text"]
    knows.act(None, "memory", "delete", mem["items"][0]["id"])
    assert not next(s for s in knows.sections(None) if s["id"] == "memory")["items"]
    assert "Everything I keep" in knows.summary(None)
