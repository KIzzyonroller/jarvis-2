"""
Test setup. Runs before any Jarvis module is imported:
  * a throwaway home folder, so nothing touches your real Documents\\Jarvis, memories or settings
  * no API keys, so nothing can reach Claude, Groq or Discord by accident

Run everything:  python -m pytest tests -q        (build.ps1 runs this before every release)
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="jarvis-tests-"))
for k in ("HOME", "USERPROFILE"):
    os.environ[k] = str(_TMP)
os.environ["LOCALAPPDATA"] = str(_TMP / "AppData" / "Local")
os.environ["APPDATA"] = str(_TMP / "AppData" / "Roaming")
for k in ("ANTHROPIC_API_KEY", "GROQ_API_KEY", "DISCORD_BOT_TOKEN", "ELEVENLABS_API_KEY"):
    os.environ[k] = ""
os.environ["JARVIS_TESTING"] = "1"
(_TMP / "Documents" / "Jarvis").mkdir(parents=True, exist_ok=True)

import config  # noqa: E402

config.HOME = _TMP
config.JARVIS_DIR = _TMP / "Documents" / "Jarvis"
