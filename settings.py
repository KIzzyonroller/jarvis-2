"""
The Settings panel: every key, password, account and option she uses, on pages (PAGES), set inside the app (no .env editing needed).

  * Secret fields (keys, passwords, the Discord token) are password boxes. Their saved value NEVER goes back to
    the screen: the panel only learns "saved" or "not set". Leave one empty to keep it; "Remove" clears it.
  * Saved secrets are encrypted with Windows' per-user protection (secretbox.py) inside the .env file.
  * The Claude key is checked with Anthropic before it's saved.
  * Most settings are read at startup, so saving restarts him (about 10 seconds).
"""
import os
import re

import config
import secretbox

# (section, key, label, kind, help, options). PAGES says which page of Settings each section sits on.
FIELDS = [
    # ---------------------------------------------------------------- General
    ("Claude", "ANTHROPIC_API_KEY", "Claude API key", "secret",
     "From console.anthropic.com > API keys. Required: it's her brain.", None),
    ("Claude", "JARVIS_DAILY_BUDGET", "Daily spending limit ($)", "number",
     "She stops using Claude for the day past this. 0 = no limit.", None),
    ("You", "JARVIS_ADDRESS_AS", "What Juno calls you", "text", "Like your name, boss, or anything you like.", None),
    ("You", "JARVIS_CITY", "Your city", "text", "For weather. Leave empty to work it out from your connection.", None),
    ("Starting up", "JARVIS_START_MINIMIZED", "Start with her window minimized", "bool",
     "She starts in the corner widget so she never covers your work or her desktop intro.", None),
    ("Starting up", "JARVIS_MINI", "Corner widget while minimized", "bool",
     "The little widget in the top-right that shows her listening, thinking and talking.", None),
    ("Starting up", "JARVIS_START_MODE", "Start in", "choice",
     "Calendar mode is just the calendar and reminders, using very little of your PC.",
     [("full", "Full Juno"), ("calendar", "Calendar mode")]),
    ("Starting up", "JARVIS_MORNING_BRIEFING", "Morning briefing", "bool",
     "The first time you talk to her in the morning: weather, your day, and anything new.", None),
    ("Games and alerts", "JARVIS_GAME_MODE", "Keep it short while I'm in a game", "bool",
     "In a fullscreen game or video she answers in one short sentence.", None),
    ("Games and alerts", "JARVIS_ALERTS", "Warn me about problems", "bool",
     "Things like a full drive, overheating or a download stuck. Never during games.", None),

    # ---------------------------------------------------------------- Conversation & personality
    ("Personality", "JUNO_PERSONALITY", "Her personality", "choice", "How she comes across. Her rules stay the same.",
     [("playful", "Playful (quick, curious, a bit chaotic)"), ("calm", "Calm (warm and steady)"),
      ("sassy", "Sassy (teasing, sharp)"), ("sweet", "Sweet (kind, upbeat)"), ("focused", "Focused (businesslike)"),
      ("chaotic", "Chaotic (dramatic, full of energy)")]),
    ("Personality", "JUNO_HUMOR", "Humor", "choice", "",
     [("low", "A little"), ("medium", "Some"), ("high", "A lot")]),
    ("Personality", "JUNO_REPLY_LENGTH", "How much she says", "choice", "",
     [("short", "As short as possible"), ("normal", "Short, more when it helps"), ("detailed", "Fuller answers")]),
    ("Personality", "JARVIS_MAX_WORDS", "Most words she reads out", "number",
     "Past this she finishes the thought and the rest stays on screen. Ask for detail and there's no limit.", None),
    ("Personality", "JUNO_PERSONA_NOTES", "Anything else about her", "text",
     "In your own words: \"call me captain\", \"loves bad puns\", \"never talks about the weather\".", None),
    ("Starting conversations", "JUNO_CHAT_FIRST", "Start conversations about what I'm doing", "bool",
     "When you're paused in something for a while (not mid-typing, not in a game or a call), she says something about it "
     "and listens for your answer. She only knows the app and window title; those go to Claude when she speaks up.", None),
    ("Starting conversations", "JUNO_CHAT_EVERY", "How often", "choice", "",
     [("rarely", "Rarely (a few times a day)"), ("normal", "Now and then (every 30 to 45 minutes at most)"),
      ("often", "Often (every 10 to 15 minutes)")]),
    ("Starting conversations", "JUNO_QUIET_HOURS", "Quiet hours", "text",
     "Like 23-8 for 11 PM to 8 AM. Empty = none.", None),
    ("Starting conversations", "JUNO_CHAT_NEVER", "Never bring up", "text",
     "Apps or words, separated by commas (like: excel, tax, discord). Banking, passwords and private windows never.", None),
    ("Answering", "JARVIS_INSTANT", "Instant commands", "bool",
     "Simple things (volume, play/pause, opening an app) happen right away without asking Claude.", None),
    ("Answering", "JARVIS_INSTANT_ACK", "Say \"on it\" straight away", "bool",
     "A quick acknowledgement while she works on longer things.", None),
    ("Answering", "JUNO_FOLLOW_UP", "Answer without her name for (seconds)", "number",
     "After she asks you something, how long you can reply without saying Juno.", None),

    # ---------------------------------------------------------------- Voice & effects
    ("Voice effect", "JUNO_VOICE_EFFECT", "Effect", "choice", "Added on top of her voice.",
     [("none", "None"), ("ethereal", "Ethereal (airy shimmer)"), ("echo", "Echo (big room)"), ("glitch", "Glitch (digital stutter)"),
      ("robot", "Robot"), ("radio", "Radio"), ("synth", "Synth (deep, metallic)")]),
    ("Voice effect", "JUNO_EFFECT_STRENGTH", "Effect strength", "choice", "",
     [("0.3", "Subtle"), ("0.6", "Medium"), ("0.85", "Strong"), ("1", "Full")]),
    ("Voice engine", "JARVIS_TTS", "Voice engine", "choice",
     "If one fails she falls back to the next.",
     [("kokoro", "Kokoro (free, on this PC, natural)"), ("elevenlabs", "ElevenLabs (most human, paid)"),
      ("edge", "Microsoft online (free)"), ("sapi", "Windows built-in (robotic, always works)")]),
    ("Voice engine", "ELEVENLABS_API_KEY", "ElevenLabs API key", "secret", "Only for the ElevenLabs engine.", None),
    ("Voice engine", "JUNO_ELEVENLABS_VOICE_ID", "ElevenLabs voice ID", "text", "Any voice from your ElevenLabs library.", None),

    # ---------------------------------------------------------------- Languages
    ("Language", "JUNO_LANGUAGE", "She understands and answers in", "choice",
     "Anything but English switches her hearing to a multilingual model (a little slower on the first start while it "
     "downloads), and her voice switches to match.",
     [("en", "English"), ("auto", "Whatever I speak"), ("es", "Spanish"), ("fr", "French"), ("it", "Italian"),
      ("pt", "Portuguese (Brazil)"), ("hi", "Hindi")]),

    # ---------------------------------------------------------------- Microphone
    ("Microphone", "JUNO_MIC", "Microphone", "choice", "If it's unplugged she uses Windows' default.", None),
    ("Microphone", "JUNO_MIC_FLOOR", "How loud you have to be", "choice",
     "Raise it if background noise keeps setting her off.",
     [("250", "Quiet voice is fine"), ("400", "Normal"), ("650", "Speak up"), ("900", "Noisy room")]),
    ("Microphone", "JARVIS_VAD", "Speech detection", "choice", "Stricter ignores more music and TV.",
     [("0.35", "Relaxed"), ("0.5", "Normal"), ("0.65", "Strict"), ("0.8", "Very strict")]),
    ("Microphone", "JARVIS_PAUSE", "Pause that ends what you're saying (seconds)", "number",
     "Shorter is snappier; longer lets you think mid-sentence.", None),
    ("Microphone", "JARVIS_SMART_PAUSE", "Smart pauses", "bool",
     "She answers sooner when what you said is clearly finished, and waits longer after \"and...\".", None),
    ("Microphone", "JARVIS_ECHO_CANCEL", "Cancel her own voice", "bool",
     "So you can talk over her on speakers. Turn off if you only use headphones.", None),
    ("Microphone", "JARVIS_MUTE_HOTKEY", "Mute hotkey", "text", "Like ctrl+alt+m.", None),
    ("Faster hearing", "GROQ_API_KEY", "Groq API key", "secret",
     "Optional. Free at console.groq.com; makes her understand you much faster on slower PCs.", None),

    # ---------------------------------------------------------------- Appearance & animations
    ("Her desktop", "JARVIS_LIVING_DESKTOP", "Juno takes over the desktop", "bool",
     "She becomes your wallpaper on every monitor, and your desktop icons are hidden while she runs.", None),
    ("Her desktop", "JARVIS_DESK_INTRO", "Her intro when she starts", "bool", "She grabs your screen and shatters it.", None),
    ("Her desktop", "JUNO_DESK_QUALITY", "Animation quality", "choice", "Lower is lighter on your PC.",
     [("low", "Light (15 fps)"), ("medium", "Balanced (24 fps)"), ("high", "Smooth (30 fps)")]),
    ("Her desktop", "JUNO_DESK_VIZ", "Voice visualizer", "choice", "",
     [("both", "Corner and second monitor"), ("corner", "Bottom-left corner only"), ("second", "Second monitor only"),
      ("off", "Off")]),
    ("Music player", "JUNO_MUSIC_PLAYER", "Music player pop-up", "bool",
     "When music plays she shows her player (with her sitting on it) instead of opening Spotify's window.", None),

    # ---------------------------------------------------------------- Application access
    ("What she can use", "JARVIS_SCREEN_WATCH", "Watch my screen while we talk", "bool",
     "Faster answers about what's on screen. Kept in memory only, never saved; only while you're talking to her "
     "and never during fullscreen games.", None),
    ("What she can use", "JARVIS_CAMERA", "Camera", "bool", "Only when you ask her to look at you or something you're holding.", None),
    ("What she can use", "JARVIS_READ_ANYWHERE", "Read files anywhere on my drives", "bool",
     "Off: only your user folder and folders you've let her into.", None),
    ("What she can use", "JARVIS_DISCORD_READ", "Read my Discord notifications", "bool",
     "DMs and pings that pop up as Windows notifications.", None),
    ("What she can use", "JARVIS_KEEP_FOCUS", "Stop apps stealing focus", "bool",
     "When she opens something it won't yank you out of what you're doing.", None),
    ("What she can use", "JUNO_BLOCKED_APPS", "Apps she may never touch", "text",
     "Separated by commas (like: steam, outlook, banking). She won't open, close, type in, click in or look at them.", None),
    ("Activity memory", "JARVIS_ACTIVITY", "Remember what I work on", "bool",
     "Logs which app and window is in front (names and titles only, never screenshots or typing), on this PC only, so "
     "you can ask 'what was I working on yesterday?'.", None),
    ("Activity memory", "JARVIS_ACTIVITY_DAYS", "Keep it for (days)", "number", "Older days are deleted.", None),
    ("Activity memory", "JARVIS_ACTIVITY_SKIP", "Never log", "text",
     "Apps or words, separated by commas. Private windows and password managers are never logged anyway.", None),

    # ---------------------------------------------------------------- Connected apps
    ("Email", "EMAIL_ADDRESS", "Email address", "text", "Gmail, Yahoo or iCloud. Read-only: she can't send or delete.", None),
    ("Email", "EMAIL_APP_PASSWORD", "App password", "secret",
     "NOT your normal password. Gmail: myaccount.google.com/apppasswords (needs 2-Step Verification).", None),
    ("Email", "JARVIS_EMAIL_ANNOUNCE", "Say new emails out loud", "bool", "Who it's from and the subject.", None),
    ("Discord bot", "DISCORD_BOT_TOKEN", "Bot token", "secret",
     "discord.com/developers > your app > Bot > Reset Token. Treat it like a password.", None),
    ("Discord bot", "DISCORD_OWNER_ID", "Your Discord user ID", "text",
     "Discord > Settings > Advanced > Developer Mode, then right-click your name > Copy User ID.", None),
    ("Discord bot", "JARVIS_DISCORD_TYPE", "Let her type in my Discord app", "bool",
     "Sends messages from YOUR account by typing into the Discord app, only when you ask, and you approve each one.", None),
    ("Discord bot", "DISCORD_BOT_REPLY", "Who she answers on Discord", "choice", "",
     [("everyone", "Everyone (rate limited)"), ("owner", "Only me"), ("off", "Nobody (read and send only)")]),
    ("Spotify", "SPOTIFY_CLIENT_ID", "Spotify Client ID", "text",
     "Needs Spotify Premium. developer.spotify.com > your app > Settings. Not the secret.", None),
    ("Netflix", "JARVIS_NETFLIX", "Open Netflix in", "choice", "",
     [("auto", "The app if installed"), ("web", "The website"), ("app", "The app")]),
    ("Netflix", "JARVIS_NETFLIX_TRACK", "Keep a log of what I watch", "bool", "Stays on this PC.", None),
    ("Apple Music", "JARVIS_APPLE_MUSIC", "Open Apple Music in", "choice", "",
     [("auto", "The app if installed"), ("web", "The website"), ("app", "The app")]),
    ("Calendar", "JARVIS_CAL_DEFAULT", "Add new events to", "choice",
     "Google and Outlook: she opens the event filled in and presses Save (you OK it first).",
     [("jarvis", "Juno's own calendar"), ("caldav", "My CalDAV calendar (iCloud, Fastmail, Yahoo...)"),
      ("google", "Google Calendar"), ("outlook", "Outlook.com"), ("outlook_work", "Outlook for work or school"),
      ("windows", "Outlook desktop / Windows Calendar app")]),
    ("Calendar", "JARVIS_CAL_ALERT", "Alert before events (minutes)", "number", "0 = when it starts.", None),
    ("Calendar", "GOOGLE_CAL_ICS", "Google Calendar private link", "secret",
     "To SEE your Google events: Google Calendar > Settings > your calendar > Integrate calendar > "
     "'Secret address in iCal format'. Read-only.", None),
    ("Calendar", "OUTLOOK_CAL_ICS", "Outlook calendar link", "secret",
     "To SEE your Outlook events: Outlook.com > Settings > Calendar > Shared calendars > Publish a calendar > "
     "copy the ICS link. Read-only.", None),
    ("Calendar", "OTHER_CAL_ICS", "Other calendar links", "secret",
     "Any other .ics / webcal links (school, sports team, iCloud public calendar). Separate with spaces.", None),
    ("Calendar", "CALDAV_URL", "CalDAV server (two-way)", "text",
     "iCloud: https://caldav.icloud.com  Fastmail: https://caldav.fastmail.com  Yahoo: https://caldav.calendar.yahoo.com",
     None),
    ("Calendar", "CALDAV_USER", "CalDAV username", "text", "Usually your email address.", None),
    ("Calendar", "CALDAV_PASSWORD", "CalDAV app password", "secret",
     "An app password, never your normal one. iCloud: account.apple.com > Sign-In and Security > App-Specific "
     "Passwords.", None),
    ("Calendar", "CALDAV_CALENDAR", "CalDAV calendar name (optional)", "text",
     "Which of that account's calendars to use. Empty = the first one.", None),
    ("Calendar", "JARVIS_CAL_SPEAK", "Calendar mode: say alerts out loud", "bool",
     "With Windows' built-in voice (light). Off: a notification and a chime only.", None),
    ("Blender mode", "MESHY_API_KEY", "Meshy API key", "secret",
     "Unlocks Blender mode (Meshy makes the detailed models). Get it at meshy.ai/developers/keys; needs Meshy Pro "
     "or higher.", None),
    ("Unreal mode", "UNREAL_AI_KEY", "Unreal AI key", "secret",
     "Unlocks Unreal mode; its spending is separate. Claude: console.anthropic.com/settings/keys. OpenRouter: "
     "openrouter.ai/settings/keys. OpenAI: platform.openai.com/api-keys.", None),
    ("Unreal mode", "UNREAL_AI_MODEL", "Model (optional)", "text",
     "Leave empty to use the best one the key can.", None),
]

PAGES = {
    "Claude": "general", "You": "general", "Starting up": "general", "Games and alerts": "general",
    "Personality": "conversation", "Starting conversations": "conversation", "Answering": "conversation",
    "Voice effect": "voice", "Voice engine": "voice",
    "Language": "languages",
    "Microphone": "mic", "Faster hearing": "mic",
    "Her desktop": "appearance", "Music player": "appearance",
    "What she can use": "access", "Activity memory": "access",
}
MODE_KEYS = {"UNREAL_AI_KEY"}
SECRETS = {f[1] for f in FIELDS if f[3] == "secret"}
RETIRED = ("BLENDER_AI_KEY", "BLENDER_AI_MODEL")      # Blender mode used to take an AI key; it's a Meshy key now
DEFAULTS = {"JARVIS_DAILY_BUDGET": "5", "JARVIS_ADDRESS_AS": "sir",
            "JARVIS_MINI": "true", "JARVIS_MORNING_BRIEFING": "true", "JARVIS_GAME_MODE": "true", "JARVIS_ALERTS": "true",
            "JUNO_PERSONALITY": "playful", "JUNO_HUMOR": "medium", "JUNO_REPLY_LENGTH": "normal", "JARVIS_MAX_WORDS": "150",
            "JUNO_CHAT_FIRST": "true", "JUNO_CHAT_EVERY": "normal", "JUNO_QUIET_HOURS": "23-8", "JARVIS_INSTANT": "true",
            "JARVIS_INSTANT_ACK": "true", "JUNO_FOLLOW_UP": "8", "JUNO_VOICE_EFFECT": "none", "JUNO_EFFECT_STRENGTH": "0.6",
            "JARVIS_TTS": "kokoro", "JUNO_ELEVENLABS_VOICE_ID": "EXAVITQu4vr4xnSDxMaL", "JUNO_LANGUAGE": "en",
            "JUNO_MIC": "default", "JUNO_MIC_FLOOR": "400", "JARVIS_VAD": "0.5", "JARVIS_PAUSE": "1.5",
            "JARVIS_SMART_PAUSE": "true", "JARVIS_ECHO_CANCEL": "true", "JARVIS_MUTE_HOTKEY": "ctrl+alt+m",
            "JUNO_DESK_QUALITY": "medium", "JUNO_DESK_VIZ": "both", "JUNO_MUSIC_PLAYER": "true", "JARVIS_CAMERA": "true",
            "JARVIS_DISCORD_READ": "true", "JARVIS_KEEP_FOCUS": "true", "DISCORD_BOT_REPLY": "everyone",
            "JARVIS_NETFLIX": "auto", "JARVIS_NETFLIX_TRACK": "true", "JARVIS_EMAIL_ANNOUNCE": "false",
            "JARVIS_APPLE_MUSIC": "auto", "JARVIS_DISCORD_TYPE": "false",
            "JARVIS_READ_ANYWHERE": "true", "JARVIS_CAL_DEFAULT": "jarvis", "JARVIS_CAL_ALERT": "10",
            "JARVIS_START_MODE": "full", "JARVIS_CAL_SPEAK": "true",
            "JARVIS_ACTIVITY": "false", "JARVIS_ACTIVITY_DAYS": "14",
            "JARVIS_LIVING_DESKTOP": "true", "JARVIS_DESK_INTRO": "true",
            "JARVIS_SCREEN_WATCH": "true", "JARVIS_START_MINIMIZED": "true"}


def _current(key):
    return os.environ.get(key, "")


def view():
    """For the panel. Secrets are reported as saved or not, never their value."""
    out = []
    for section, key, label, kind, help_, options in FIELDS:
        f = {"section": section, "key": key, "label": label, "kind": kind, "help": help_,
             "page": PAGES.get(section, "apps")}
        if kind == "secret":
            v = _current(key)
            f["saved"] = bool(v) and "paste-yours" not in v
            if f["saved"] and len(v) > 12:
                f["hint"] = "ends in " + v[-4:] if key != "EMAIL_APP_PASSWORD" else "saved"
        else:
            f["value"] = _current(key) or DEFAULTS.get(key, "")
        if key == "JUNO_MIC":                       # the mics plugged in right now
            try:
                import speech
                options = speech.mic_devices()
            except Exception:
                options = [("default", "Windows default")]
            if f["value"] not in [o[0] for o in options]:
                options = options + [(f["value"], f["value"] + " (not connected)")]
        if options:
            f["options"] = [{"value": a, "label": b} for a, b in options]
        out.append(f)
    return out


def validate(key, value):
    v = value.strip()
    if key == "ANTHROPIC_API_KEY" and (not v.startswith("sk-ant-") or len(v) < 40 or " " in v):
        return "That doesn't look like a Claude API key. They start with sk-ant- and are long."
    if key == "GROQ_API_KEY" and (not v.startswith("gsk_") or " " in v):
        return "Groq keys start with gsk_."
    if key == "EMAIL_ADDRESS" and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-z]{2,}", v, re.I):
        return "That isn't an email address."
    if key == "EMAIL_APP_PASSWORD" and len(v.replace(" ", "")) < 8:
        return "App passwords are longer than that (Gmail's are 16 letters)."
    if key == "DISCORD_BOT_TOKEN" and (v.count(".") != 2 or len(v) < 50 or " " in v):
        return "That doesn't look like a bot token (three parts separated by dots). Bot > Reset Token copies it."
    if key == "DISCORD_OWNER_ID" and not re.fullmatch(r"\d{15,21}", v):
        return "A Discord user ID is a long number (Copy User ID with Developer Mode on)."
    if key == "SPOTIFY_CLIENT_ID" and not re.fullmatch(r"[0-9a-f]{32}", v, re.I):
        return "A Spotify Client ID is 32 letters and numbers."
    ranges = {"JUNO_FOLLOW_UP": (2, 60, "seconds"), "JARVIS_PAUSE": (0.4, 5, "seconds"), "JARVIS_MAX_WORDS": (20, 600, "words")}
    if key in ranges and v:
        lo, hi, unit = ranges[key]
        try:
            n = float(v)
        except ValueError:
            return f"Use a number of {unit}."
        if not lo <= n <= hi:
            return f"Pick between {lo:g} and {hi:g} {unit}."
    if key == "JUNO_QUIET_HOURS" and v and not re.fullmatch(r"\d{1,2}\s*-\s*\d{1,2}", v):
        return "Like 23-8 (11 PM to 8 AM), or leave it empty."
    if key == "JUNO_PERSONA_NOTES" and len(v) > 600:
        return "Keep it under 600 characters."
    if key == "JARVIS_DAILY_BUDGET":
        try:
            if float(v) < 0:
                raise ValueError
        except ValueError:
            return "Use a number of dollars, like 5."
    if key in MODE_KEYS:
        import providers
        problem = providers.looks_valid(v)
        if problem:
            return problem
    if key == "MESHY_API_KEY":
        import meshy
        problem = meshy.looks_valid(v)
        if problem:
            return problem
    if key == "UNREAL_AI_MODEL" and (len(v) > 100 or " " in v):
        return "A model name has no spaces, like gpt-5 or anthropic/claude-sonnet-4.5."
    if key in ("GOOGLE_CAL_ICS", "OUTLOOK_CAL_ICS", "OTHER_CAL_ICS"):
        for u in re.split(r"[\s,]+", v):
            if u and not re.match(r"(?i)^(https|webcal)://\S+$", u):
                return "Paste the full link (it starts with https:// or webcal://)."
    if key == "CALDAV_URL" and not re.match(r"(?i)^https://\S+$", v):
        return "The server address starts with https://"
    if key == "JARVIS_CAL_ALERT":
        try:
            if not 0 <= float(v) <= 10080:
                raise ValueError
        except ValueError:
            return "Minutes, like 10."
    if key == "JARVIS_ACTIVITY_DAYS":
        try:
            if not 1 <= float(v) <= 365:
                raise ValueError
        except ValueError:
            return "Days, from 1 to 365."
    if key == "JARVIS_ACTIVITY_SKIP" and len(v) > 500:
        return "Keep the list under 500 characters."
    if key == "JARVIS_ADDRESS_AS" and len(v) > 30:
        return "Keep it short."
    if key == "JARVIS_ADDRESS_AS" and not config.name_allowed(v):
        return "He won't call anyone that. Pick another name."
    return None


def check_claude_key(key):
    """None if Anthropic accepts it (or can't be reached right now), else a sentence why not."""
    try:
        import anthropic
        anthropic.Anthropic(api_key=key, timeout=15, max_retries=0).models.list(limit=1)
    except Exception as e:
        if type(e).__name__ in ("AuthenticationError", "PermissionDeniedError"):
            return "Anthropic says that key isn't valid. Copy it again from console.anthropic.com."
    return None


def save(changes, clear=()):
    """changes: {KEY: new value} (empty strings are ignored, so blank secret boxes keep what's saved).
    clear: keys to remove. Returns (ok, {KEY: problem})."""
    known = {f[1]: f for f in FIELDS}
    values, errors = {}, {}
    for key, value in (changes or {}).items():
        if key not in known:
            continue
        value = str(value if value is not None else "").strip()
        if not value:
            continue
        kind = known[key][3]
        if kind == "bool":
            value = "true" if value.lower() in ("true", "1", "on", "yes") else "false"
        elif kind == "choice":
            allowed = [o[0] for o in known[key][5]]
            if value not in allowed:
                errors[key] = "Pick one of the options."
                continue
        elif key in ("EMAIL_APP_PASSWORD", "GROQ_API_KEY", "ANTHROPIC_API_KEY", "SPOTIFY_CLIENT_ID"):
            value = value.replace(" ", "") if key == "EMAIL_APP_PASSWORD" else value
        problem = validate(key, value)
        if problem:
            errors[key] = problem
            continue
        values[key] = value
    if "ANTHROPIC_API_KEY" in values and "ANTHROPIC_API_KEY" not in errors:
        problem = check_claude_key(values["ANTHROPIC_API_KEY"])
        if problem:
            errors["ANTHROPIC_API_KEY"] = problem
            values.pop("ANTHROPIC_API_KEY")
    for k in [k for k in values if k in MODE_KEYS]:
        import providers
        ok, msg = providers.check(values[k])
        if not ok:
            errors[k] = msg
            values.pop(k)
    if "MESHY_API_KEY" in values:
        import meshy
        ok, msg = meshy.check(values["MESHY_API_KEY"])
        if not ok:
            errors["MESHY_API_KEY"] = msg
            values.pop("MESHY_API_KEY")
    if errors:
        return False, errors
    for key in clear or ():
        if key in known and key != "ANTHROPIC_API_KEY":
            values[key] = ""
    if not values:
        return True, {}
    write_env({k: (secretbox.protect(v) if k in SECRETS and v else v) for k, v in values.items()})
    for k, v in values.items():                  # so a view() before the restart shows the new state
        os.environ[k] = v
    return True, {}


def write_env(values, path=None):
    """Set KEY=value lines in the .env file, keeping everything else in it as it was."""
    path = path or config.ENV_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = ["# Jarvis keys and settings (the Settings panel writes this). Keep this file private."]
    done = set()
    for i, line in enumerate(lines):
        k = line.split("=", 1)[0].strip().lstrip("#").strip()
        if "=" in line and k in values and k not in done:
            lines[i] = f"{k}={values[k]}"
            done.add(k)
    lines += [f"{k}={v}" for k, v in values.items() if k not in done]
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)
