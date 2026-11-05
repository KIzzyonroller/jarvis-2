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
        value = value.strip().strip('"').strip("'")
        if value.startswith("dpapi:"):                     # saved from the Settings panel, encrypted (secretbox.py)
            import secretbox
            value = secretbox.unprotect(value)
        os.environ.setdefault(key.strip(), value)


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
# Names he will never call anyone (letters only, lowercase; spaces and punctuation are ignored when comparing)
BLOCKED_NAMES = ("kizzy", "johndeadlock")
# The creator's own PC: here (and only here) he may call the user "Kizzy". Matched by the computer's name.
HOME_PC = "DESKTOP-A9TTU06"


def on_home_pc():
    import socket
    names = {os.environ.get("COMPUTERNAME", ""), socket.gethostname()}
    return any(n and n.strip().upper() == HOME_PC for n in names)


def blocked_names():
    return tuple(b for b in BLOCKED_NAMES if not (b == "kizzy" and on_home_pc()))


def name_allowed(name):
    flat = "".join(ch for ch in str(name or "").lower() if ch.isalnum())
    return not any(b in flat for b in blocked_names())


ADDRESS_AS = os.environ.get("JARVIS_ADDRESS_AS", "Kizzy" if on_home_pc() else "sir")
if not name_allowed(ADDRESS_AS):
    ADDRESS_AS = "sir"

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
# Languages (langs.py): "en" = English only; "auto" = whatever you speak; or one of es fr it pt hi.
# Anything but English switches hearing to Whisper's multilingual models, and her replies and voice follow.
LANGUAGE = os.environ.get("JUNO_LANGUAGE", "en").lower()
LANGUAGES = LANGUAGE != "en"
HEAR_LANGUAGE = "en" if not LANGUAGES else (None if LANGUAGE == "auto" else LANGUAGE)
if LANGUAGES and not os.environ.get("JARVIS_WHISPER_FAST"):
    WHISPER_FAST = "tiny"            # the English-only tiny model can't hear her name inside another language
MEMORY_FILE_NAME = "memory.json"
ROUTINES_FILE_NAME = "routines.json"
MEMORY_LIMIT = 200            # facts kept
MEMORY_IN_CONTEXT = 60        # most recent facts sent with each request
# Words you say a lot that Whisper might mangle (apps, games, names). Comma separated.
WHISPER_VOCAB = os.environ.get("JARVIS_VOCAB", "Spotify, Discord, YouTube, Chrome, Steam, Notepad, PowerShell, "
                                               "Valorant, Fortnite, Minecraft, Twitch, OBS, VS Code, Reddit, Gmail.")
# Global hotkey to mute/unmute the mic, works even when Jarvis isn't focused
MUTE_HOTKEY = os.environ.get("JARVIS_MUTE_HOTKEY", "ctrl+alt+m")
MIN_SPEECH_RMS = int(os.environ.get("JUNO_MIC_FLOOR", "400"))   # mic loudness that counts as speech; raise if noise keeps triggering it
MIC_DEVICE = os.environ.get("JUNO_MIC", "default")              # Settings > Microphone (a device name, or default)
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
FOLLOW_UP_TIMEOUT = float(os.environ.get("JUNO_FOLLOW_UP", "8"))   # after she asks you something, answer without her name for this long
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
# How many CPU cores his voice may use while it's being generated. All of them makes each sentence a big spike
# (and barely faster); about half, at most 4, keeps it smooth. 0 = let the library decide.
KOKORO_THREADS = int(os.environ.get("JARVIS_VOICE_THREADS", "-1"))

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
# Apps she may never open, close, type into or click in (Settings > Application access), comma separated
BLOCKED_APPS = [a.strip().lower() for a in os.environ.get("JUNO_BLOCKED_APPS", "").split(",") if a.strip()]

# --- staying out of your way
# Things he opens while you're in another app open BEHIND it, so you keep focus.
KEEP_FOCUS = os.environ.get("JARVIS_KEEP_FOCUS", "true").lower() != "false"
KEEP_FOCUS_SECONDS = 12      # how long after launching he guards your focus against apps that grab it
# A small always-on-top HUD in the top-right corner while the main window is minimized.
MINI_HUD = os.environ.get("JARVIS_MINI", "true").lower() != "false"
# The living desktop (livedesk.py): Juno becomes the wallpaper while she runs, desktop icons hidden.
LIVING_DESKTOP = os.environ.get("JARVIS_LIVING_DESKTOP", "true").lower() != "false"
DESK_INTRO = os.environ.get("JARVIS_DESK_INTRO", "true").lower() != "false"     # Juno grabs the screen at startup
DESK_QUALITY = os.environ.get("JUNO_DESK_QUALITY", "medium").lower()   # low / medium / high: frame rate and detail
DESK_VIZ = os.environ.get("JUNO_DESK_VIZ", "both").lower()             # both / corner / second / off
# Her music player (music.py): pops up while music plays, with her sitting on it. Spotify stays in the background.
MUSIC_PLAYER = os.environ.get("JUNO_MUSIC_PLAYER", "true").lower() != "false"
# Frame rate for her animations (desktop and music player), all the time. Say "set your animations to 60 fps" to change it.
try:
    ANIM_FPS = max(5, min(60, int(os.environ.get("JUNO_FPS", "30"))))
except ValueError:
    ANIM_FPS = 30
# Screen watching (screenwatch.py): a live view of the screen in memory while you talk to him, so he sees what you mean.
SCREEN_WATCH = os.environ.get("JARVIS_SCREEN_WATCH", "true").lower() != "false"
# Start with his window minimized (the corner widget shows him), so he never covers the desktop intro or your work.
START_MINIMIZED = os.environ.get("JARVIS_START_MINIMIZED", "true").lower() != "false"
# She starts conversations about what you're doing (proactive.py)
CHAT_FIRST = os.environ.get("JUNO_CHAT_FIRST", "true").lower() != "false"
CHAT_EVERY = os.environ.get("JUNO_CHAT_EVERY", "normal").lower()              # rarely / normal / often
QUIET_HOURS = os.environ.get("JUNO_QUIET_HOURS", "23-8")                     # "23-8" = 11 PM to 8 AM; empty = none
CHAT_NEVER = [a.strip().lower() for a in os.environ.get("JUNO_CHAT_NEVER", "").split(",") if a.strip()]


def _int_env(key, default, lo, hi):
    try:
        return max(lo, min(hi, int(float(os.environ.get(key, default)))))
    except ValueError:
        return default


CHAT_MINUTES = _int_env("JUNO_CHAT_MINUTES", 40, 3, 600)       # "How often" = custom: about this many minutes apart
CHAT_DWELL = _int_env("JUNO_CHAT_DWELL", 0, 0, 120)            # minutes in one thing first (0 = go by "How often")
CHAT_MAX = _int_env("JUNO_CHAT_MAX", 0, 0, 200)                # most a day (0 = go by "How often")
CHAT_PAUSE = _int_env("JUNO_CHAT_PAUSE", 6, 2, 60)             # wait until you've paused this many seconds
CHAT_STYLE = os.environ.get("JUNO_CHAT_STYLE", "mixed").lower()   # mixed / questions / tips / jokes / hype
CHAT_TOPICS = os.environ.get("JUNO_CHAT_TOPICS", "").strip()   # things you like talking about, in your words
CHAT_MUSIC = os.environ.get("JUNO_CHAT_MUSIC", "true").lower() != "false"     # a word about the song now and then
# Check-ins (moments.py)
EVENING_WRAP = os.environ.get("JUNO_EVENING_WRAP", "true").lower() != "false"
EVENING_AT = _int_env("JUNO_EVENING_AT", 20, 16, 23)
RAIN_ALERT = os.environ.get("JUNO_RAIN_ALERT", "true").lower() != "false"
BREAK_EVERY = _int_env("JUNO_BREAK_EVERY", 120, 0, 600)        # minutes at the PC before a break nudge (0 = off)
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
# Apple Music: open songs in the "app", on the "web", or "auto" (the app if it's installed)
APPLE_MUSIC_DEFAULT = os.environ.get("JARVIS_APPLE_MUSIC", "auto").strip().lower()
# Email (optional, read-only; README "Email"): your address and an APP password, never your real one
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "").strip()
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "").strip()
EMAIL_IMAP_HOST = os.environ.get("EMAIL_IMAP_HOST", "").strip()          # worked out from the address if empty
EMAIL_ANNOUNCE = os.environ.get("JARVIS_EMAIL_ANNOUNCE", "false").lower() == "true"   # say new mail out loud
# Discord bot (optional, see README "Discord bot"): an official bot account he chats and posts through
# Let him type messages into YOUR Discord app, as you (each one needs your OK). Off unless you switch it on.
DISCORD_TYPE = os.environ.get("JARVIS_DISCORD_TYPE", "false").lower() == "true"
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
DISCORD_BOT_ON_SERVER = os.environ.get("DISCORD_BOT_ON_SERVER", "false").lower() == "true"   # server/run_bot.py runs it
DISCORD_OWNER_ID = os.environ.get("DISCORD_OWNER_ID", "").strip()      # your Discord user ID: you skip the rate limits
DISCORD_BOT_REPLY = os.environ.get("DISCORD_BOT_REPLY", "everyone").strip().lower()   # everyone, owner or off
DISCORD_UPDATES_CHANNEL = os.environ.get("DISCORD_UPDATES_CHANNEL", "").strip()     # where she posts her update notes
DISCORD_UPDATES_MODE = os.environ.get("DISCORD_UPDATES_MODE", "ask").lower()      # ask / auto / off, after an update
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
GAME_DETECT = os.environ.get("JUNO_GAME_DETECT", "true").lower() != "false"      # gamemode.py: notice games
GAME_CHECKIN = os.environ.get("JUNO_GAME_CHECKIN", "true").lower() != "false"    # "how'd it go?" after a session
GAME_EXTRA = os.environ.get("JUNO_GAME_EXTRA", "")                               # more game .exe names, commas
GAME_ALLOW = os.environ.get("JUNO_GAME_ALLOW", "")                               # Discord names that may interrupt
# Smart lights (smarthome.py): Philips Hue and/or Home Assistant
HUE_BRIDGE = os.environ.get("JUNO_HUE_BRIDGE", "")
HUE_USER = os.environ.get("JUNO_HUE_USER", "")                 # the key the bridge gives when you pair (secret)
HA_URL = os.environ.get("HOME_ASSISTANT_URL", "")
HA_TOKEN = os.environ.get("HOME_ASSISTANT_TOKEN", "")          # long-lived access token (secret)
LIGHTS_SYNC = os.environ.get("JUNO_LIGHTS_SYNC", "false").lower() == "true"
LIGHTS_SYNC_TARGET = os.environ.get("JUNO_LIGHTS_SYNC_TARGET", "all")
STEAM_API_KEY = os.environ.get("STEAM_API_KEY", "")                            # steam.py (secret)
STEAM_ID = os.environ.get("STEAM_ID", "")                                      # profile link, custom name or 17-digit id
STEAM_SALE_ALERTS = os.environ.get("JUNO_STEAM_SALES", "true").lower() != "false"
STEAM_SALE_MIN = _int_env("JUNO_STEAM_SALE_MIN", 20, 1, 95)                    # % off before she mentions it
PATCH_NOTES = os.environ.get("JUNO_PATCH_NOTES", "true").lower() != "false"     # updates for games you play
MOODS = os.environ.get("JUNO_MOODS", "true").lower() != "false"                 # her mood colors her tone
BANTER = os.environ.get("JUNO_BANTER", "true").lower() != "false"               # the AIs quip when you switch
BIRTHDAYS = os.environ.get("JUNO_BIRTHDAYS", "true").lower() != "false"         # birthday reminders
JOURNAL = os.environ.get("JUNO_JOURNAL", "true").lower() != "false"             # nightly journal question
JOURNAL_AT = _int_env("JUNO_JOURNAL_AT", 22, 0, 23)                                    # from this hour
JOURNAL_FILE = os.environ.get("JUNO_JOURNAL_FILE", "")                          # empty = Desktop\Juno Journal.txt
GOODNIGHT_PC = os.environ.get("JUNO_GOODNIGHT_PC", "sleep").lower()             # sleep / lock / nothing
GOODNIGHT_LIGHTS = os.environ.get("JUNO_GOODNIGHT_LIGHTS", "off").lower()       # off / dim / leave
REACTIONS = os.environ.get("JUNO_REACTIONS", "true").lower() != "false"         # small Juno reacts
BUTLER_NUDGE = os.environ.get("JUNO_BUTLER_NUDGE", "true").lower() != "false"   # weekly "Downloads is full" nudge
PHONE_NOTIFS = os.environ.get("JUNO_PHONE_NOTIFS", "true").lower() != "false"   # Phone Link notifications on screen
PHONE_SPEAK = os.environ.get("JUNO_PHONE_SPEAK", "false").lower() == "true"     # ...and read out loud

# Phone remote: type to him from your phone on the same Wi-Fi. Off unless you turn it on.
PHONE = os.environ.get("JARVIS_PHONE", "false").lower() == "true"
PHONE_PORT = int(os.environ.get("JARVIS_PHONE_PORT", "8766"))
# Glass mode (cards over your webcam that you move with your hands). Only ever on this PC (127.0.0.1).
GLASS_PORT = int(os.environ.get("JARVIS_GLASS_PORT", "8767"))
GLASS_WHERE = os.environ.get("JUNO_GLASS_WHERE", "window").lower()     # window (its own, with your camera) / desktop
# Widgets on her desktop (deskwidgets.py): PC stats, now playing, weather, today, notes & timers, Discord
_W_KEYS = {"stats": "JUNO_W_STATS", "music": "JUNO_W_MUSIC", "weather": "JUNO_W_WEATHER", "calendar": "JUNO_W_CALENDAR",
           "notes": "JUNO_W_NOTES", "discord": "JUNO_W_DISCORD"}
DESK_WIDGETS = os.environ.get("JUNO_DESK_WIDGETS", "true").lower() != "false"
DESK_WIDGET_ON = {k: os.environ.get(v, "true").lower() != "false" for k, v in _W_KEYS.items()}
DESK_WIDGETS_WHERE = os.environ.get("JUNO_DESK_WIDGETS_WHERE", "right").lower()      # right / left / second

# Say a pre-recorded "On it." the instant a slow request starts (web search, screen, Blender...)
INSTANT_ACK = os.environ.get("JARVIS_INSTANT_ACK", "true").lower() != "false"

# Voice model: auto (setup.bat measures which is faster on your PC), full, or lite (compressed)
KOKORO_MODEL = os.environ.get("JARVIS_KOKORO", "auto").lower()
# Her voice effect's strength (Settings > Voice & effects): 0 = none of it, 1 = all of it
VOICE_FX_STRENGTH = float(os.environ.get("JUNO_EFFECT_STRENGTH", "0.6"))

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


# Settings that apply the moment you save them (no restart). Everything else restarts her.
LIVE_KEYS = {"JARVIS_MINI", "JUNO_FPS", "JUNO_CHAT_FIRST", "JUNO_CHAT_EVERY", "JUNO_CHAT_MINUTES", "JUNO_CHAT_DWELL",
             "JUNO_CHAT_MAX", "JUNO_CHAT_PAUSE", "JUNO_CHAT_STYLE", "JUNO_CHAT_TOPICS", "JUNO_CHAT_MUSIC",
             "JUNO_QUIET_HOURS", "JUNO_CHAT_NEVER", "JUNO_EVENING_WRAP", "JUNO_EVENING_AT", "JUNO_RAIN_ALERT",
             "JUNO_BREAK_EVERY", "JUNO_GLASS_WHERE", "JUNO_DESK_WIDGETS", "JUNO_DESK_WIDGETS_WHERE", "JUNO_W_STATS",
             "JUNO_W_MUSIC", "JUNO_W_WEATHER", "JUNO_W_CALENDAR", "JUNO_W_NOTES", "JUNO_W_DISCORD", "JUNO_GAME_DETECT", "JUNO_GAME_CHECKIN",
             "JUNO_GAME_EXTRA", "JUNO_GAME_ALLOW", "JUNO_PHONE_NOTIFS", "JUNO_PHONE_SPEAK", "JUNO_BUTLER_NUDGE", "JUNO_HUE_BRIDGE", "JUNO_HUE_USER", "HOME_ASSISTANT_URL",
             "HOME_ASSISTANT_TOKEN", "JUNO_LIGHTS_SYNC", "JUNO_LIGHTS_SYNC_TARGET", "JUNO_JOURNAL", "JUNO_JOURNAL_AT", "JUNO_JOURNAL_FILE",
             "JUNO_GOODNIGHT_PC", "JUNO_GOODNIGHT_LIGHTS", "JUNO_REACTIONS", "STEAM_API_KEY", "STEAM_ID",
             "JUNO_STEAM_SALES", "JUNO_STEAM_SALE_MIN", "JUNO_PATCH_NOTES", "JUNO_MOODS", "JUNO_BANTER", "JUNO_BIRTHDAYS",
             "JUNO_VOICE", "JARVIS_VOICE", "ULTRON_VOICE", "JUNO_OPINIONS", "DISCORD_UPDATES_CHANNEL", "DISCORD_UPDATES_MODE"}
WIDGET_KEYS = {"JUNO_DESK_WIDGETS", "JUNO_DESK_WIDGETS_WHERE", "JUNO_W_STATS", "JUNO_W_MUSIC", "JUNO_W_WEATHER",
               "JUNO_W_CALENDAR", "JUNO_W_NOTES", "JUNO_W_DISCORD"}


def reload_live():
    """Re-read the live settings from the environment (settings.save puts the new values there)."""
    global MINI_HUD, ANIM_FPS, CHAT_FIRST, CHAT_EVERY, CHAT_MINUTES, CHAT_DWELL, CHAT_MAX, CHAT_PAUSE, CHAT_STYLE
    global CHAT_TOPICS, CHAT_MUSIC, QUIET_HOURS, CHAT_NEVER, EVENING_WRAP, EVENING_AT, RAIN_ALERT, BREAK_EVERY
    global GLASS_WHERE, DESK_WIDGETS, DESK_WIDGET_ON, DESK_WIDGETS_WHERE, GAME_DETECT, GAME_CHECKIN, GAME_EXTRA, GAME_ALLOW
    on = lambda k, d="true": os.environ.get(k, d).lower() != "false"
    GAME_DETECT, GAME_CHECKIN = on("JUNO_GAME_DETECT"), on("JUNO_GAME_CHECKIN")
    GAME_EXTRA, GAME_ALLOW = os.environ.get("JUNO_GAME_EXTRA", ""), os.environ.get("JUNO_GAME_ALLOW", "")
    global PHONE_NOTIFS, PHONE_SPEAK, BUTLER_NUDGE
    BUTLER_NUDGE = on("JUNO_BUTLER_NUDGE")
    global HUE_BRIDGE, HUE_USER, HA_URL, HA_TOKEN, LIGHTS_SYNC, LIGHTS_SYNC_TARGET
    HUE_BRIDGE, HUE_USER = os.environ.get("JUNO_HUE_BRIDGE", ""), os.environ.get("JUNO_HUE_USER", "")
    HA_URL, HA_TOKEN = os.environ.get("HOME_ASSISTANT_URL", ""), os.environ.get("HOME_ASSISTANT_TOKEN", "")
    LIGHTS_SYNC = os.environ.get("JUNO_LIGHTS_SYNC", "false").lower() == "true"
    LIGHTS_SYNC_TARGET = os.environ.get("JUNO_LIGHTS_SYNC_TARGET", "all")
    global JOURNAL, JOURNAL_AT, JOURNAL_FILE, GOODNIGHT_PC, GOODNIGHT_LIGHTS, REACTIONS
    JOURNAL, JOURNAL_AT, JOURNAL_FILE = on("JUNO_JOURNAL"), _int_env("JUNO_JOURNAL_AT", 22, 0, 23), os.environ.get("JUNO_JOURNAL_FILE", "")
    GOODNIGHT_PC = os.environ.get("JUNO_GOODNIGHT_PC", "sleep").lower()
    GOODNIGHT_LIGHTS = os.environ.get("JUNO_GOODNIGHT_LIGHTS", "off").lower()
    REACTIONS = on("JUNO_REACTIONS")
    global STEAM_API_KEY, STEAM_ID, STEAM_SALE_ALERTS, STEAM_SALE_MIN, PATCH_NOTES, MOODS, BANTER, BIRTHDAYS
    STEAM_API_KEY, STEAM_ID = os.environ.get("STEAM_API_KEY", ""), os.environ.get("STEAM_ID", "")
    STEAM_SALE_ALERTS, STEAM_SALE_MIN = on("JUNO_STEAM_SALES"), _int_env("JUNO_STEAM_SALE_MIN", 20, 1, 95)
    PATCH_NOTES, MOODS, BANTER, BIRTHDAYS = on("JUNO_PATCH_NOTES"), on("JUNO_MOODS"), on("JUNO_BANTER"), on("JUNO_BIRTHDAYS")
    global DISCORD_UPDATES_CHANNEL, DISCORD_UPDATES_MODE
    DISCORD_UPDATES_CHANNEL = os.environ.get("DISCORD_UPDATES_CHANNEL", "").strip()
    DISCORD_UPDATES_MODE = os.environ.get("DISCORD_UPDATES_MODE", "ask").lower()
    PHONE_NOTIFS, PHONE_SPEAK = on("JUNO_PHONE_NOTIFS"), os.environ.get("JUNO_PHONE_SPEAK", "false").lower() == "true"
    GLASS_WHERE = os.environ.get("JUNO_GLASS_WHERE", "window").lower()
    DESK_WIDGETS = on("JUNO_DESK_WIDGETS")
    DESK_WIDGET_ON = {k: on(v) for k, v in _W_KEYS.items()}
    DESK_WIDGETS_WHERE = os.environ.get("JUNO_DESK_WIDGETS_WHERE", "right").lower()
    MINI_HUD = on("JARVIS_MINI")
    ANIM_FPS = _int_env("JUNO_FPS", 30, 5, 60)
    CHAT_FIRST, CHAT_MUSIC = on("JUNO_CHAT_FIRST"), on("JUNO_CHAT_MUSIC")
    CHAT_EVERY = os.environ.get("JUNO_CHAT_EVERY", "normal").lower()
    CHAT_MINUTES, CHAT_DWELL = _int_env("JUNO_CHAT_MINUTES", 40, 3, 600), _int_env("JUNO_CHAT_DWELL", 0, 0, 120)
    CHAT_MAX, CHAT_PAUSE = _int_env("JUNO_CHAT_MAX", 0, 0, 200), _int_env("JUNO_CHAT_PAUSE", 6, 2, 60)
    CHAT_STYLE = os.environ.get("JUNO_CHAT_STYLE", "mixed").lower()
    CHAT_TOPICS = os.environ.get("JUNO_CHAT_TOPICS", "").strip()
    QUIET_HOURS = os.environ.get("JUNO_QUIET_HOURS", "23-8")
    CHAT_NEVER = [a.strip().lower() for a in os.environ.get("JUNO_CHAT_NEVER", "").split(",") if a.strip()]
    EVENING_WRAP, RAIN_ALERT = on("JUNO_EVENING_WRAP"), on("JUNO_RAIN_ALERT")
    EVENING_AT, BREAK_EVERY = _int_env("JUNO_EVENING_AT", 20, 16, 23), _int_env("JUNO_BREAK_EVERY", 120, 0, 600)
