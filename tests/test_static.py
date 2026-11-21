"""Cheap checks over the whole codebase: everything compiles, versions agree, the UI's scripts parse."""
import py_compile
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".venv", "build", "dist", "Releases", "__pycache__", "node_modules"}


def _py_files():
    return [p for p in ROOT.rglob("*.py") if not SKIP & set(p.relative_to(ROOT).parts)]


def test_every_python_file_compiles():
    bad = []
    for p in _py_files():
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as e:
            bad.append(f"{p.name}: {e.msg}")
    assert not bad, "\n".join(bad)


def test_changelog_top_matches_version():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    top = re.search(r"^## (\d+\.\d+\.\d+)", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    assert top, "CHANGELOG.md has no '## x.y.z' heading"
    assert top.group(1) == version, f"VERSION says {version} but the newest CHANGELOG section is {top.group(1)}"


def test_no_em_dashes_in_spoken_or_changelog_text():
    """House style: no em dashes in what people read."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").split("\n## ", 2)
    newest = text[1] if len(text) > 1 else ""
    assert "—" not in newest, "The newest CHANGELOG section has an em dash"


def test_ui_scripts_parse():
    node = shutil.which("node")
    if not node:
        import pytest
        pytest.skip("node isn't installed")
    bad = []
    for p in (ROOT / "ui").rglob("*.js"):
        r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
        if r.returncode:
            bad.append(f"{p.name}: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'syntax error'}")
    assert not bad, "\n".join(bad)


def test_inline_scripts_in_html_parse(tmp_path):
    node = shutil.which("node")
    if not node:
        import pytest
        pytest.skip("node isn't installed")
    bad = []
    for p in (ROOT / "ui").glob("*.html"):
        html = p.read_text(encoding="utf-8")
        for i, (attrs, js) in enumerate(re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", html, re.S)):
            if not js.strip() or re.search(r'type="(importmap|application/(ld\+)?json)"', attrs):
                continue
            f = tmp_path / f"{p.stem}_{i}.{'mjs' if 'module' in attrs else 'js'}"
            f.write_text(js, encoding="utf-8")
            r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
            if r.returncode:
                bad.append(f"{p.name} script #{i}: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'syntax error'}")
    assert not bad, "\n".join(bad)


def test_build_inputs_are_in_the_repo():
    """The installer build needs these. 1.0.41's first build failed because assets/jarvis.ico wasn't in the repo."""
    missing = [p for p in ("assets/jarvis.ico", "app_main.py", "jarvis.spec", "VERSION", "CHANGELOG.md", "ui/index.html",
                           "jarvis_blender_bridge.py") if not (ROOT / p).exists()]
    assert not missing, ("Missing from the repo (commit them in GitHub Desktop): " + ", ".join(missing))
