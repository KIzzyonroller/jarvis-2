"""
The Settings panel: every key, password and account he uses, set inside the app (no .env editing needed).

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

# (section, key, label, kind, help, options)
FIELDS = [
    ("Claude", "ANTHROPIC_API_KEY", "Claude API key", "secret",
     "From console.anthropic.com > API keys. Required: it's his brain.", None),
    ("Claude", "JARVIS_DAILY_BUDGET", "Daily spending limit ($)", "number",
     "He stops using Claude for the day past this. 0 = no limit.", None),
    ("You", "JARVIS_ADDRESS_AS", "What Jarvis calls you", "text", "Like sir, boss, or your name.", None),
    ("You", "JARVIS_CITY", "Your city", "text", "For weather. Leave empty to work it out from your connection.", None),
    ("Faster hearing", "GROQ_API_KEY", "Groq API key", "secret",
     "Optional. Free at console.groq.com; makes him understand you much faster on slower PCs.", None),
    ("Email", "EMAIL_ADDRESS", "Email address", "text", "Gmail, Yahoo or iCloud. Read-only: he can't send or delete.", None),
    ("Email", "EMAIL_APP_PASSWORD", "App password", "secret",
     "NOT your normal password. Gmail: myaccount.google.com/apppasswords (needs 2-Step Verification).", None),
    ("Email", "JARVIS_EMAIL_ANNOUNCE", "Say new emails out loud", "bool", "Who it's from and the subject.", None),
    ("Discord bot", "DISCORD_BOT_TOKEN", "Bot token", "secret",
     "discord.com/developers > your app > Bot > Reset Token. Treat it like a password.", None),
    ("Discord bot", "DISCORD_OWNER_ID", "Your Discord user ID", "text",
     "Discord > Settings > Advanced > Developer Mode, then right-click your name > Copy User ID.", None),
    ("Discord bot", "JARVIS_DISCORD_TYPE", "Let him type in my Discord app", "bool",
     "Sends messages from YOUR account by typing into the Discord app, only when you ask, and you approve each one.", None),
    ("Discord bot", "DISCORD_BOT_REPLY", "Who he answers on Discord", "choice", "",
     [("everyone", "Everyone (rate limited)"), ("owner", "Only me"), ("off", "Nobody (read and send only)")]),
    ("Spotify", "SPOTIFY_CLIENT_ID", "Spotify Client ID", "text",
     "Needs Spotify Premium. developer.spotify.com > your app > Settings. Not the secret.", None),
    ("Netflix", "JARVIS_NETFLIX", "Open Netflix in", "choice", "",
     [("auto", "The app if installed"), ("web", "The website"), ("app", "The app")]),
    ("Netflix", "JARVIS_NETFLIX_TRACK", "Keep a log of what I watch", "bool", "Stays on this PC.", None),
    ("Apple Music", "JARVIS_APPLE_MUSIC", "Open Apple Music in", "choice", "",
     [("auto", "The app if installed"), ("web", "The website"), ("app", "The app")]),
    ("Calendar", "JARVIS_CAL_DEFAULT", "Add new events to", "choice",
     "Google and Outlook: he opens the event filled in and presses Save (you OK it first).",
     [("jarvis", "Jarvis's own calendar"), ("caldav", "My CalDAV calendar (iCloud, Fastmail, Yahoo...)"),
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
    ("Calendar", "JARVIS_START_MODE", "Start in", "choice",
     "Calendar mode is just the calendar and reminders, using very little of your PC.",
     [("full", "Full Jarvis"), ("calendar", "Calendar mode")]),
    ("Calendar", "JARVIS_CAL_SPEAK", "Calendar mode: say alerts out loud", "bool",
     "With Windows' built-in voice (light). Off: a notification and a chime only.", None),
    ("Files", "JARVIS_READ_ANYWHERE", "Read files anywhere on my drives", "bool",
     "Off: he only reads your user folder and folders you've let him into (System panel lists them).", None),
    ("Activity memory", "JARVIS_ACTIVITY", "Remember what I work on", "bool",
     "Logs which app and window is in front (names and titles only, never screenshots or typing), on this PC only, so "
     "you can ask 'what was I working on yesterday?' or 'reopen what I had open on Friday'.", None),
    ("Activity memory", "JARVIS_ACTIVITY_DAYS", "Keep it for (days)", "number", "Older days are deleted.", None),
    ("Activity memory", "JARVIS_ACTIVITY_SKIP", "Never log", "text",
     "Apps or words, separated by commas (like: bank, tax, steam). Private windows and password managers are never "
     "logged anyway.", None),
    ("Blender mode", "MESHY_API_KEY", "Meshy API key", "secret",
     "Unlocks Blender mode (Meshy makes the detailed models). Get it at meshy.ai/developers/keys; needs Meshy Pro "
     "or higher.", None),
    ("Unreal mode", "UNREAL_AI_KEY", "Unreal AI key", "secret",
     "Unlocks Unreal mode; its spending is separate. Claude: console.anthropic.com/settings/keys. OpenRouter: "
     "openrouter.ai/settings/keys. OpenAI: platform.openai.com/api-keys.", None),
    ("Unreal mode", "UNREAL_AI_MODEL", "Model (optional)", "text",
     "Leave empty to use the best one the key can.", None),
]
MODE_KEYS = {"UNREAL_AI_KEY"}
SECRETS = {f[1] for f in FIELDS if f[3] == "secret"}
RETIRED = ("BLENDER_AI_KEY", "BLENDER_AI_MODEL")      # Blender mode used to take an AI key; it's a Meshy key now
DEFAULTS = {"JARVIS_DAILY_BUDGET": "5", "JARVIS_ADDRESS_AS": "sir", "DISCORD_BOT_REPLY": "everyone",
            "JARVIS_NETFLIX": "auto", "JARVIS_NETFLIX_TRACK": "true", "JARVIS_EMAIL_ANNOUNCE": "false",
            "JARVIS_APPLE_MUSIC": "auto", "JARVIS_DISCORD_TYPE": "false",
            "JARVIS_READ_ANYWHERE": "true", "JARVIS_CAL_DEFAULT": "jarvis", "JARVIS_CAL_ALERT": "10",
            "JARVIS_START_MODE": "full", "JARVIS_CAL_SPEAK": "true",
            "JARVIS_ACTIVITY": "false", "JARVIS_ACTIVITY_DAYS": "14"}


def _current(key):
    return os.environ.get(key, "")


def view():
    """For the panel. Secrets are reported as saved or not, never their value."""
    out = []
    for section, key, label, kind, help_, options in FIELDS:
        f = {"section": section, "key": key, "label": label, "kind": kind, "help": help_}
        if kind == "secret":
            v = _current(key)
            f["saved"] = bool(v) and "paste-yours" not in v
            if f["saved"] and len(v) > 12:
                f["hint"] = "ends in " + v[-4:] if key != "EMAIL_APP_PASSWORD" else "saved"
        else:
            f["value"] = _current(key) or DEFAULTS.get(key, "")
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
