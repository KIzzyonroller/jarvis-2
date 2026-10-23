"""
Jarvis settings. Most things you'd want to tweak live here.
Secrets (your API key) go in the .env file (see ENV_FILE below), not here.
"""
import os
import sys
from pathlib import Path

# Two ways he runs:
#   from source (python jarvis.py): everything lives in this folder, like always.
#   installed (the Setup.exe build): the program folder is replaced on every update, so anything that
#   has to survive (keys, downloaded voice models) lives in %LOCALAPPDATA%\JarvisData instead.
FROZEN = bool(getattr(sys, "frozen", False))
BASE_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent
RES_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))       # files shipped with him: ui, VERSION, the Blender add-on
DATA_DIR = (Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "JarvisData") if FROZEN else BASE_DIR
ENV_FILE = DATA_DIR / ".env"


def _load_env():
    env = ENV_FILE
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env()

# ---------------------------------------------------------------- brain
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# Optional cloud speech recognition (much faster than local on slower PCs). Free account at console.groq.com.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
CLOUD_STT_MODEL = os.environ.get("JARVIS_CLOUD_STT_MODEL", "whisper-large-v3-turbo")
# Cloud for everything you say (not just sentences aimed at him): fastest on slow PCs. Only works with voice
# lock on, so other people and videos are never sent. Off by default; see README before turning it on.
# claude-sonnet-5-5 is smart. claude-haiku-5-5 is faster and cheaper,
# which honestly matters a lot for a voice assistant. Try both.
MODEL = os.environ.get("JARVIS_MODEL", "claude-sonnet-5-5")
MAX_TOKENS = 8000               # room for reasoning + tool calls
WEB_SEARCH_MAX_USES = 3          # web searches allowed per request
HISTORY_MESSAGES = 30            # how much conversation Jarvis remembers

# Show Jarvis's reasoning live in the app. Costs nothing extra, but on newer
# models it adds a little delay before he starts talking. Set to false in
# .env (JARVIS_SHOW_REASONING=false) if you'd rather have max speed.
SHOW_REASONING = os.environ.get("JARVIS_SHOW_REASONING", "true").lower() != "false"

# What Jarvis calls you. "sir" is canon, but you do you.
ADDRESS_AS = os.environ.get("JARVIS_ADDRESS_AS", "sir")

# Optional: makes "what's the weather" work without saying the city.
CITY = os.environ.get("JARVIS_CITY", "")
REGION = os.environ.get("JARVIS_REGION", "")
COUNTRY = os.environ.get("JARVIS_COUNTRY", "")      # 2-letter code, e.g. CA, US
TIMEZONE = os.environ.get("JARVIS_TIMEZONE", "")    # e.g. America/Toronto

# ---------------------------------------------------------------- ears
# Always listening. Say "Jarvis" (or "Ultron") at the START or END of what
# you say: "Jarvis, open Spotify" / "open Spotify, Jarvis".
LISTEN_NAMES = ["Jarvis", "Ultron"]
SAMPLE_RATE = 16000
CHUNK = 1280              # 80 ms
# Speech recognition runs in two passes:
#   fast:     every utterance, just to catch "Jarvis"/"Ultron". Cheap.
#   accurate: re-transcribes only what you say TO him, carefully. "auto" = large-v3-turbo on an
#             NVIDIA GPU, distil-small.en on CPU (about twice as fast as small.en). Other options: small.en, medium.en, distil-large-v3, large-v3.
WHISPER_FAST = os.environ.get("JARVIS_WHISPER_FAST", "tiny.en")   # just listens for the name; the accurate pass does the real work
WHISPER_THREADS = int(os.environ.get("JARVIS_WHISPER_THREADS", "4"))  # cap so listening never hogs every core
WHISPER_ACCURATE = os.environ.get("JARVIS_WHISPER", "auto")
WHISPER_DEVICE = os.environ.get("JARVIS_WHISPER_DEVICE", "auto").lower()   # auto, cpu, cuda
MEMORY_FILE_NAME = "memory.json"
ROUTINES_FILE_NAME = "routines.json"
MEMORY_LIMIT = 200            # facts kept
MEMORY_IN_CONTEXT = 60        # most recent facts sent with each request
# Words you say a lot that Whisper might mangle (apps, games, names). Comma separated.
WHISPER_VOCAB = os.environ.get("JARVIS_VOCAB", "Spotify, Discord, YouTube, Chrome, Steam, Notepad, PowerShell, "
                                               "Valorant, Fortnite, Minecraft, Twitch, OBS, VS Code, Reddit, Gmail.")
# Global hotkey to mute/unmute the mic, works even when Jarvis isn't focused
MUTE_HOTKEY = os.environ.get("JARVIS_MUTE_HOTKEY", "ctrl+alt+m")
MIN_SPEECH_RMS = 400      # mic loudness that counts as speech; raise if noise keeps triggering it
SILENCE_SECONDS = float(os.environ.get("JARVIS_PAUSE", "1.5"))  # pause length that ends a sentence
# After you finish, he waits a beat before answering, and longer if it sounds unfinished
# ("Jarvis, open the..." / just "Jarvis"). Start talking again in that window and he keeps listening.
HOLD_SECONDS = 0.7          # normal sentence
HOLD_COMPLETE = 0.2         # a clearly finished command or question: go almost immediately
EARLY_SILENCE = float(os.environ.get("JARVIS_EARLY_PAUSE", "0.55"))  # after this much quiet he checks if you're done
SMART_ENDPOINT = os.environ.get("JARVIS_SMART_PAUSE", "true").lower() != "false"
LIVE_TRANSCRIBE = os.environ.get("JARVIS_LIVE_TRANSCRIBE", "true").lower() != "false"   # careful pass runs while you talk
CAREFUL_BUDGET = float(os.environ.get("JARVIS_CAREFUL_BUDGET", "1.5"))   # skip the local careful pass if it'd take longer
WHISPER_BEAM = int(os.environ.get("JARVIS_WHISPER_BEAM", "0"))   # careful-pass search width; 0 = auto (5 on GPU, 3 on CPU)
HOLD_UNFINISHED = 2.5       # ends with "and", "the", "to", a comma...
HOLD_NAME_ONLY = 1.6        # just "Jarvis" (then he says "Yes?")
MAX_RECORD_SECONDS = 20
FOLLOW_UP_TIMEOUT = 8     # after he asks you something (or says "Yes?"), answer without his name for this long
MERGE_SECONDS = 3.0       # pause mid-command and keep talking within this, and he stitches it together
# He reads out about this many words, then finishes the paragraph (the idea) he's on, up to 1.6x this.
# Anything after that stays on screen and he says so. Ask for detail ("explain", "tell me more") for no limit.
MAX_SPOKEN_WORDS = int(os.environ.get("JARVIS_MAX_WORDS", "150"))
                          # (unless you ask for detail). The full text always shows in the app.


# ---------------------------------------------------------------- mouth
# Which voice engine to use. Falls back down the list if one fails:
#   kokoro      free, runs on your PC, natural-sounding (default)
#   elevenlabs  most human-sounding, paid; set ELEVENLABS_API_KEY in .env
#   edge        Microsoft online voice, free, a bit flatter
#   sapi        built-in Windows voice, robotic, always works
TTS_ENGINE = os.environ.get("JARVIS_TTS", "kokoro").lower()
MODELS_DIR = DATA_DIR / "models"

# Kokoro British male voices: bm_george, bm_fable, bm_lewis, bm_daniel
# (American: am_michael, am_adam, am_fenrir, am_puck ... full list prints if you pick a bad one)
KOKORO_VOICE = os.environ.get("JARVIS_VOICE", "bm_george")
KOKORO_SPEED = float(os.environ.get("JARVIS_VOICE_SPEED", "1.05"))
KOKORO_LANG = "en-gb"

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")     # optional: real Spotify control (README explains)
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")  # "George", British
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_flash_v2_5")             # fastest

# Edge voice (fallback engine)
TTS_VOICE = "en-GB-RyanNeural"
TTS_RATE = "+8%"

# ---------------------------------------------------------------- files
HOME = Path.home()
JARVIS_DIR = HOME / "Documents" / "Jarvis"
WRITE_ROOTS = [JARVIS_DIR]   # free to create/edit here; anywhere else asks (with an "always allow" option)


def _fixed_drives():
    if sys.platform != "win32":
        return []
    try:
        import ctypes
        import string
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        return [Path(f"{d}:\\") for i, d in enumerate(string.ascii_uppercase)
                if mask & (1 << i) and ctypes.windll.kernel32.GetDriveTypeW(f"{d}:\\") == 3]
    except Exception:
        return []


# Reading/searching: your whole user folder, plus every local drive unless READ_ANYWHERE=false.
# Password stores, keys and browser logins are always off-limits (permissions.is_secret).
READ_ANYWHERE = os.environ.get("JARVIS_READ_ANYWHERE", "true").lower() != "false"
READ_ROOTS = [HOME] + (_fixed_drives() if READ_ANYWHERE else [])
NOTES_FILE = JARVIS_DIR / "notes.md"
REMINDERS_FILE = JARVIS_DIR / "reminders.json"
SCREENSHOT_DIR = JARVIS_DIR / "Screenshots"
CACHE_DIR = JARVIS_DIR / "cache"
MODELS_3D_DIR = JARVIS_DIR / "3D"

# ---------------------------------------------------------------- eyes
# Webcam: Jarvis only takes a photo when you ask him to look, then releases the camera.
CAMERA_ENABLED = os.environ.get("JARVIS_CAMERA", "true").lower() != "false"
CAMERA_INDEX = int(os.environ.get("JARVIS_CAMERA_INDEX", "0"))   # try 1 if you have several cameras

# --- staying out of your way
# Things he opens while you're in another app open BEHIND it, so you keep focus.
KEEP_FOCUS = os.environ.get("JARVIS_KEEP_FOCUS", "true").lower() != "false"
KEEP_FOCUS_SECONDS = 12      # how long after launching he guards your focus against apps that grab it
# A small always-on-top HUD in the top-right corner while the main window is minimized.
MINI_HUD = os.environ.get("JARVIS_MINI", "true").lower() != "false"
# A briefing the first time you start or wake the PC each day (the day rolls over at 4 AM)
MORNING_BRIEFING = os.environ.get("JARVIS_MORNING_BRIEFING", "true").lower() != "false"
# Headlines for the briefing (any RSS feed). Empty = no news.
NEWS_RSS = os.environ.get("JARVIS_NEWS_RSS", "https://www.cbc.ca/webfeed/rss/rss-topstories")
# Daily spending limit for Claude, in dollars (an estimate; 0 = no limit). He warns at 80%.
DAILY_BUDGET = float(os.environ.get("JARVIS_DAILY_BUDGET", "5"))
# How long conversation memory (Documents/Jarvis/history.db) keeps things, in days
HISTORY_DAYS = int(os.environ.get("JARVIS_HISTORY_DAYS", "365"))
# Read new Discord messages out loud as they arrive (you can also say "stop reading my Discord messages")
DISCORD_READ = os.environ.get("JARVIS_DISCORD_READ", "true").lower() != "false"
# Netflix: open it on the "web" or in the "app" by default ("auto" = the app if installed, the web to search)
NETFLIX_DEFAULT = os.environ.get("JARVIS_NETFLIX", "auto").strip().lower()
NETFLIX_TRACK = os.environ.get("JARVIS_NETFLIX_TRACK", "true").lower() != "false"     # keep a log of what you watch
# Email (optional, read-only; README "Email"): your address and an APP password, never your real one
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "").strip()
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "").strip()
EMAIL_IMAP_HOST = os.environ.get("EMAIL_IMAP_HOST", "").strip()          # worked out from the address if empty
EMAIL_ANNOUNCE = os.environ.get("JARVIS_EMAIL_ANNOUNCE", "false").lower() == "true"   # say new mail out loud
# Discord bot (optional, see README "Discord bot"): an official bot account he chats and posts through
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
DISCORD_OWNER_ID = os.environ.get("DISCORD_OWNER_ID", "").strip()      # your Discord user ID: you skip the rate limits
DISCORD_BOT_REPLY = os.environ.get("DISCORD_BOT_REPLY", "everyone").strip().lower()   # everyone, owner or off
# Started with Windows: seconds to wait after login before loading (keeps login snappy)
STARTUP_DELAY = float(os.environ.get("JARVIS_STARTUP_DELAY", "10"))

# --- speed
# Everyday commands ("pause", "volume 30", "open Spotify", "what time is it") run instantly with no AI call.
INSTANT_COMMANDS = os.environ.get("JARVIS_INSTANT", "true").lower() != "false"
# Short, simple requests go to a faster model; anything involving the screen, files, Blender, code etc. stays on MODEL.
# Set JARVIS_FAST_MODEL= (empty) to always use MODEL.
FAST_MODEL = os.environ.get("JARVIS_FAST_MODEL", "claude-haiku-5-5")

# Game mode: while you're in a fullscreen game or video he keeps answers to one short sentence
# and shows non-urgent heads-ups on screen instead of talking over your game.
GAME_MODE = os.environ.get("JARVIS_GAME_MODE", "true").lower() != "false"

# Phone remote: type to him from your phone on the same Wi-Fi. Off unless you turn it on.
PHONE = os.environ.get("JARVIS_PHONE", "false").lower() == "true"
PHONE_PORT = int(os.environ.get("JARVIS_PHONE_PORT", "8766"))

# Say a pre-recorded "On it." the instant a slow request starts (web search, screen, Blender...)
INSTANT_ACK = os.environ.get("JARVIS_INSTANT_ACK", "true").lower() != "false"

# Voice model: auto (setup.bat measures which is faster on your PC), full, or lite (compressed)
KOKORO_MODEL = os.environ.get("JARVIS_KOKORO", "auto").lower()

# --- hearing
# Cancel his own voice out of the mic so you can talk over him on speakers (no headphones needed)
ECHO_CANCEL = os.environ.get("JARVIS_ECHO_CANCEL", "true").lower() != "false"
VAD_THRESHOLD = float(os.environ.get("JARVIS_VAD", "0.5"))   # 0..1; raise if noise still triggers him

# --- both at once ("Jarvis and Ultron, ...")
DUO_SECOND_WORDS = 45        # the one who answers second keeps it shorter

# --- Blender (3D modelling)
BLENDER_PATH = os.environ.get("JARVIS_BLENDER", "")     # blender.exe, if he can't find it on his own
BLENDER_PORT = 9877                                     # the Jarvis Bridge add-on listens here (localhost only)

# Speak up unprompted about low battery, maxed-out RAM, a nearly full drive
ALERTS = os.environ.get("JARVIS_ALERTS", "true").lower() != "false"

# ---------------------------------------------------------------- safety
# Risky actions (shell commands, deleting, editing files outside the Jarvis
# folder, shutdown, force-closing apps) pop an approval prompt. You click
# Authorize or say "yes". No answer within this many seconds = denied.
CONFIRM_TIMEOUT = 45
# Global keys that answer an approval from anywhere (in a game, another app...). "always" = yes and stop asking.
APPROVE_HOTKEY = os.environ.get("JARVIS_APPROVE_HOTKEY", "ctrl+alt+y")
DENY_HOTKEY = os.environ.get("JARVIS_DENY_HOTKEY", "ctrl+alt+n")
COMMAND_TIMEOUT = 60      # max seconds a PowerShell command may run
