"""1.0.43: the icon, the settings page's new pieces, the website and its Pages workflow."""
import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def test_icon_has_every_windows_size():
    ico = Image.open(ROOT / "assets" / "jarvis.ico")
    sizes = {s[0] for s in ico.info["sizes"]}
    assert {16, 24, 32, 48, 256} <= sizes


def test_settings_fields_say_live_and_default():
    import settings
    fields = {f["key"]: f for f in settings.view()}
    assert fields["JARVIS_PRESENCE"]["live"] is True and fields["JARVIS_PRESENCE"]["default"] == "dial"
    assert any(not f["live"] for f in fields.values())                  # some still need a restart
    assert all("default" not in f for f in fields.values() if f["kind"] == "secret")
    page = (ROOT / "ui" / "index.html").read_text(encoding="utf-8")
    for bit in ('id="set-q"', "function saveLabel", "function renderSearch", 'class: "reset"'):
        assert bit in page, bit


def test_site_links_point_at_real_files():
    for page in ("site/index.html", "site/docs/index.html"):
        html = (ROOT / page).read_text(encoding="utf-8")
        base = (ROOT / page).parent
        for src in re.findall(r'(?:src|href)="((?:\.\./)?img/[^"]+)"', html):
            if "${" not in src:                                         # skip template strings in the page's script
                assert (base / src).resolve().exists(), f"{page}: {src}"
    html = (ROOT / "site/index.html").read_text(encoding="utf-8")
    for w in ("bench", "station", "archive", "signal", "chart", "greenhouse"):
        assert (ROOT / "site/img" / f"{w}-1.jpg").exists() and (ROOT / "site/img" / f"{w}-2.jpg").exists()
        assert f'data-w="{w}"' in html


def test_pages_workflow_only_ships_the_site():
    wf = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    assert "path: site" in wf and "tags" not in wf
    assert "contents: read" in wf                                      # can't push or release anything


def test_plugin_help_points_at_the_real_page():
    import plugins
    assert "What he can use" not in plugins.README + plugins.EXAMPLE
