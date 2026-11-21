"""Living worlds (1.0.42): every scene is wired everywhere, the moving layer, the screensaver, matching lights."""
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import config

ROOT = Path(__file__).resolve().parent.parent


def _scenes():
    s = (ROOT / "ui" / "scenes" / "scenes.js").read_text(encoding="utf-8")
    return json.loads(s[s.index("{"):s.rstrip().rstrip(";").rindex("}") + 1])


def test_every_scene_is_wired_everywhere():
    import core
    import personas
    import settings
    import tools
    import worlds
    keys = set(_scenes())
    assert "greenhouse" in keys
    for k in keys:
        assert (ROOT / "ui" / "scenes" / f"{k}.svg").exists(), k
    choice = next(r for r in settings.FIELDS if r[1] == "JUNO_DESK_SCENE")
    assert {v for v, _ in choice[5]} == keys
    spec = next(t for t in tools.TOOL_SPECS if t["name"] == "desktop_scene")
    assert set(spec["input_schema"]["properties"]["scene"]["enum"]) == keys
    assert {k for k, _, _ in core.Core.ONBOARD_SCENES} == keys
    assert set(personas.LORE) == keys
    assert set(worlds.WORLDS) == keys


def test_world_light_colours_are_the_scene_accents():
    import worlds
    sc = _scenes()
    for k, (_, col) in worlds.WORLDS.items():
        assert col.lower() == sc[k]["accent"].lower(), k


def test_ambient_draws_every_scene():
    js = (ROOT / "ui" / "ambient.js").read_text(encoding="utf-8")
    for k in _scenes():
        assert f'"{k}"' in js, f"ambient.js has nothing for {k}"
    html = (ROOT / "ui" / "desktop.html").read_text(encoding="utf-8")
    assert html.index("ambient.js") < html.index("desktop.js")
    saver = (ROOT / "ui" / "saver.html").read_text(encoding="utf-8")
    assert "ambient.js" in saver and "scenes/scenes.js" in saver


@pytest.mark.parametrize("code,kind", [(0, ""), (3, ""), (61, "rain"), (81, "rain"), (95, "rain"), (73, "snow"),
                                       (85, "snow"), (None, ""), ("x", "")])
def test_weather_codes(code, kind):
    import deskfacts
    assert deskfacts.wx_kind(code) == kind


def test_world_light_has_todays_sun(monkeypatch):
    import deskfacts
    now = datetime.now()
    monkeypatch.setattr(deskfacts, "_SUN", {"rise": [now.replace(hour=7, minute=0), now.replace(hour=7) + timedelta(days=1)],
                                            "set": [now.replace(hour=18, minute=0)], "code": 63})
    out = deskfacts.world_light()
    assert out["wx"] == "rain"
    assert datetime.fromtimestamp(out["rise"] / 1000).hour == 7
    assert datetime.fromtimestamp(out["set"] / 1000).hour == 18


def test_world_settings_reload(monkeypatch):
    monkeypatch.setenv("JARVIS_PRESENCE", "orb")
    monkeypatch.setenv("JARVIS_SAVER", "15")
    monkeypatch.setenv("JARVIS_WORLD_LIGHTS", "true")
    config.reload_live()
    assert config.PRESENCE == "orb" and config.SAVER_MIN == 15 and config.WORLD_LIGHTS
    for k in ("JARVIS_WORLD_MOTION", "JARVIS_PRESENCE", "JARVIS_SAVER", "JARVIS_WORLD_LIGHTS"):
        assert k in config.LIVE_KEYS
    monkeypatch.setenv("JARVIS_SAVER", "nope")
    config.reload_live()
    assert config.SAVER_MIN == 0


def test_desktop_scene_tool_world_options(monkeypatch):
    import tools

    class FakeCore:
        desk = object()

        def __init__(self):
            self.ch = {}

        def set_widgets(self, ch, record_undo=True):
            self.ch.update(ch)
    fc = FakeCore()
    monkeypatch.setattr(tools, "_VOICE_CORE", fc)
    out = tools.desktop_scene_tool(scene="greenhouse", presence="orb", screensaver="10", lights=True, motion=False)
    assert fc.ch == {"JUNO_DESK_SCENE": "greenhouse", "JARVIS_PRESENCE": "orb", "JARVIS_SAVER": "10",
                     "JARVIS_WORLD_LIGHTS": "true", "JARVIS_WORLD_MOTION": "false"}
    assert "greenhouse" in out and "orb" in out and "10 minutes" in out
    assert "dial or orb" in tools.desktop_scene_tool(presence="cube")
    assert "idle minutes" in tools.desktop_scene_tool(screensaver="soon")
    assert "Screensaver off" in tools.desktop_scene_tool(screensaver="off")


def test_world_lights_do_nothing_when_off(monkeypatch):
    import worlds
    monkeypatch.setattr(config, "WORLD_LIGHTS", False)
    assert worlds.match_lights("greenhouse", wait=True) is None
    monkeypatch.setattr(config, "WORLD_LIGHTS", True)
    assert worlds.match_lights("not-a-world", wait=True) is None


def test_saver_is_safe_off_windows():
    import saver
    assert saver.ok_to_show() is (not saver._windows_busy()) or saver.IS_WINDOWS
    assert "Windows" in saver.tool("show") or saver.SAVER is not None
    page = (ROOT / "ui" / "saver.html").read_text(encoding="utf-8")
    assert re.search(r'addEventListener\("keydown", wake\)', page)        # any key puts it away


def test_screensaver_intent():
    import intents
    t = intents.normalize("start your screensaver")
    assert any(p.match(t) and fn.__name__ == "_saver" for p, fn in intents.RULES)
    t = intents.normalize("turn on the screensaver")             # a setting change, not "show it now": goes to Claude
    assert not any(p.match(t) and fn.__name__ == "_saver" for p, fn in intents.RULES)
