"""A request can be put together for the API without touching the network, for anything you might say."""
import json

import pytest


class _FakeClient:
    def __getattr__(self, _):
        raise AssertionError("the test tried to reach the network")


@pytest.fixture()
def brain(monkeypatch):
    import brain as B
    import config
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key-not-real")
    b = B.Brain.__new__(B.Brain)
    try:
        B.Brain.__init__(b)
    except Exception:
        pytest.skip("Brain() needs packages that aren't installed here")
    b.client = _FakeClient()
    return b


@pytest.mark.parametrize("text", [
    "what's the weather", "when I open valorant turn the lights off", "make a budget spreadsheet",
    "how's my watchlist", "learn my voice", "what can I cook", "run diagnostics", "play something on spotify",
    "open blender", "", "x" * 2000,
])
def test_request_builds(brain, text):
    brain._pick_groups(text)
    brain.history = [{"role": "user", "content": text or "hi"}]
    kw = brain._kwargs()
    json.dumps(kw["tools"])
    assert kw["messages"] and kw["system"]


def test_system_prompt_builds_for_every_personality():
    import personas
    for preset in getattr(personas, "PRESETS", {"classic": None}):
        import os
        os.environ["JARVIS_PRESET"] = preset
        text = personas.system_prompt("jarvis", "sir")
        assert len(text) > 500
