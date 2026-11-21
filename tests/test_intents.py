"""Instant commands (no Claude) catch what they should and leave the rest alone."""
import pytest

import intents


def _which(text):
    t = intents.normalize(text)
    for pat, fn in intents.RULES:
        if pat.match(t):
            return fn.__name__
    return None


@pytest.mark.parametrize("text,handler", [
    ("run your diagnostics", "_diag"),
    ("run diagnostics", "_diag"),
    ("run a diagnostics check", "_diag"),
    ("undo that", "_undo"),
    ("clip that", "_clip"),
    ("what's 15% of 240", "_calc"),
    ("run the setup again", "_tour"),
    ("send a crash report", "_report"),
])
def test_routes(text, handler):
    assert _which(text) == handler


@pytest.mark.parametrize("text", [
    "open your settings", "run your diagnostics", "open yourself",
])
def test_never_opens_a_windows_app_for_things_about_him(text):
    assert _which(text) != "_open" or intents.recognize(text) is False


@pytest.mark.parametrize("text", [
    "explain to me why my tabs download html files", "write me a cover letter for the junior dev job",
    "what's the difference between a virus and bacteria",
])
def test_real_questions_go_to_claude(text):
    assert not intents.recognize(text)
