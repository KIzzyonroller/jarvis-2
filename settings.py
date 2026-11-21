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
     "From console.anthropic.com > API keys. Required: it's his brain.", None),
    ("Claude", "JARVIS_DAILY_BUDGET", "Daily spending limit ($)", "number",
     "He stops using Claude for the day past this. 0 = no limit.", None),
    ("You", "JARVIS_ADDRESS_AS", "What he calls you", "text", "Like your name, boss, or anything you like.", None),
    ("You", "JARVIS_CITY", "Your city", "text", "For weather. Leave empty to work it out from your connection.", None),
    ("Starting up", "JARVIS_START_MINIMIZED", "Start with his window minimized", "bool",
     "He starts in the corner widget so he never covers your work or his desktop intro.", None),
    ("Starting up", "JARVIS_MINI", "Corner widget while minimized", "bool",
     "The little widget in the top-right that shows him listening, thinking and talking. Changes right away; or "
     "say \"turn off the corner widget\".", None),
    ("Starting up", "JARVIS_START_MODE", "Start in", "choice",
     "Calendar mode is just the calendar and reminders, using very little of your PC.",
     [("full", "Full Jarvis"), ("calendar", "Calendar mode")]),
    ("Starting up", "JARVIS_MORNING_BRIEFING", "Morning briefing", "bool",
     "The first time you talk to him in the morning: weather, your day, and anything new.", None),
    ("Games and alerts", "JARVIS_GAME_MODE", "Keep it short while I'm in a game", "bool",
     "In a fullscreen game or video he answers in one short sentence.", None),
    ("Games and alerts", "JUNO_GAME_DETECT", "Notice when I'm playing", "bool",
     "Games from Steam, Epic, Riot, Xbox, GOG, EA, Ubisoft and Battle.net (even alt-tabbed): no conversation starters, "
     "check-ins or song comments, and Discord is only read out from the people below. He only knows the game's name.", None),
    ("Games and alerts", "JUNO_GAME_CHECKIN", "Ask how it went", "bool",
     "When a game closes after 20 minutes or more, he asks how the session went.", None),
    ("Games and alerts", "JUNO_GAME_ALLOW", "Discord people who can interrupt a game", "text",
     "Names separated by commas. Their messages still get read out while you play. Or say \"let Kai through while I'm gaming\".", None),
    ("Games and alerts", "JUNO_GAME_EXTRA", "Other games he should notice", "text",
     "Program names separated by commas (like: minecraft.exe, osu!.exe) for games outside the usual launchers.", None),
    ("Games and alerts", "JARVIS_ALERTS", "Warn me about problems", "bool",
     "Things like a full drive, overheating or a download stuck. Never during games.", None),

    # ---------------------------------------------------------------- Conversation & personality
    ("Check-ins", "JARVIS_BEDTIME", "Bedtime (wind-down)", "choice",
     "Half an hour before, he says what's first tomorrow, goes quiet (whisper mode) and slowly dims and warms the "
     "lights. At bedtime he offers goodnight once. Or say \"my bedtime is 11:30\".", [('off', 'Off'), ('20:00', '8:00 pm'), ('20:30', '8:30 pm'), ('21:00', '9:00 pm'), ('21:30', '9:30 pm'), ('22:00', '10:00 pm'), ('22:30', '10:30 pm'), ('23:00', '11:00 pm'), ('23:30', '11:30 pm'), ('00:00', '12:00 am'), ('00:30', '12:30 am'), ('01:00', '1:00 am'), ('01:30', '1:30 am'), ('02:00', '2:00 am'), ('02:30', '2:30 am'), ('03:00', '3:00 am'), ('03:30', '3:30 am')]),
    ("What he can use", "JARVIS_CLIP_HISTORY", "Clipboard history", "bool",
     "Remember what you copy (in memory only, gone when he closes) so you can ask for something you copied earlier. "
     "Passwords and anything a password manager marks private are never kept.", None),
    ("What he can use", "JARVIS_SHOT_SEARCH", "Search my screenshots", "bool",
     "He reads the text in your screenshots on this PC, a few at a time, so you can find them by what was on screen. "
     "Only the words are kept, in Documents\\Jarvis.", None),
    ("Starting up", "JARVIS_PERFORMANCE", "Performance mode", "choice",
     "Lite makes him easier on a slower PC: a lighter speech model, the desktop at 15 frames a second with no effects, "
     "no ambient lines. Auto picks lite on PCs with under 8 GB of RAM or 4 or fewer CPU threads.",
     [("auto", "Auto"), ("full", "Full"), ("lite", "Lite")]),
    ("Starting up", "JARVIS_CRASH_REPORTS", "Crash reports", "choice",
     "When something breaks, the details are saved on this PC. With Ask, he offers (at most once a day) to open a "
     "report on GitHub for you to check and send yourself. Nothing is ever sent automatically.",
     [("ask", "Save them, and offer to send"), ("off", "Don't offer")]),
    ("Whisper mode", "JARVIS_EMOTION", "Emotion in his voice", "bool",
     "A little brighter and quicker for good news, slower and softer for bad news or late at night. Subtle on purpose.", None),
    ("Whisper mode", "JARVIS_WHISPER", "Whisper mode", "choice",
     "He talks quietly and keeps it short. Auto: between the hours below, and whenever a call app (Discord, Zoom, "
     "Teams, Meet...) is using your mic. Or say \"whisper mode on\".", [("auto", "Auto"), ("on", "Always"), ("off", "Never")]),
    ("Whisper mode", "JARVIS_WHISPER_FROM", "Quiet from", "choice", "", [('0', '12 am'), ('1', '1 am'), ('2', '2 am'), ('3', '3 am'), ('4', '4 am'), ('5', '5 am'), ('6', '6 am'), ('7', '7 am'), ('8', '8 am'), ('9', '9 am'), ('10', '10 am'), ('11', '11 am'), ('12', '12 pm'), ('13', '1 pm'), ('14', '2 pm'), ('15', '3 pm'), ('16', '4 pm'), ('17', '5 pm'), ('18', '6 pm'), ('19', '7 pm'), ('20', '8 pm'), ('21', '9 pm'), ('22', '10 pm'), ('23', '11 pm')]),
    ("Whisper mode", "JARVIS_WHISPER_TO", "Until", "choice", "", [('0', '12 am'), ('1', '1 am'), ('2', '2 am'), ('3', '3 am'), ('4', '4 am'), ('5', '5 am'), ('6', '6 am'), ('7', '7 am'), ('8', '8 am'), ('9', '9 am'), ('10', '10 am'), ('11', '11 am'), ('12', '12 pm'), ('13', '1 pm'), ('14', '2 pm'), ('15', '3 pm'), ('16', '4 pm'), ('17', '5 pm'), ('18', '6 pm'), ('19', '7 pm'), ('20', '8 pm'), ('21', '9 pm'), ('22', '10 pm'), ('23', '11 pm')]),
    ("Whisper mode", "JARVIS_WHISPER_VOL", "How quiet", "choice", "",
     [("20", "Very quiet"), ("35", "Quiet"), ("55", "A bit quieter")]),
    ("Automation", "JARVIS_TRIGGERS", "Triggers", "bool",
     "Things he does by himself when something happens: a game or app opens, a time of day, you get back to the PC. "
     "Set them up by voice: \"when I open Dead by Daylight, turn the lights red and open Discord\", \"every "
     "weekday at 8, tell me the market and the weather\".", None),
    ("While you're away", "JARVIS_WELCOME_BACK", "\"Where did I leave off\" when you're back", "choice",
     "After a break this long, he tells you what you were doing, what you last asked him, and what's due soon.",
     [("0", "Off"), ("10", "After 10 minutes away"), ("20", "After 20 minutes"), ("45", "After 45 minutes")]),
    ("While you're away", "JARVIS_AMBIENT", "Little lines from his world", "choice",
     "Now and then (never mid-game or mid-call), one line that fits his scene: the station, the archive...",
     [("off", "Off"), ("rare", "Rarely (a few a day)"), ("sometimes", "Sometimes")]),
    ("Weekly letter", "JARVIS_LETTER", "A letter every Sunday", "bool",
     "Sunday evening he writes you a letter (a Word file on your desktop): what you did this week, what he noticed, "
     "and some honest commentary.", None),
    ("Games and alerts", "JARVIS_PLAY_BREAK", "Gaming break nudge", "choice",
     "After this much play in one sitting he suggests a break, between matches, never mid-game.",
     [("0", "Off"), ("120", "After 2 hours"), ("180", "After 3 hours"), ("240", "After 4 hours")]),
    ("Games and alerts", "JARVIS_POSTMATCH", "Post-match stats", "bool",
     "After a session of a Steam game that publishes stats (Dead by Daylight, CS2...), he tells you what changed: "
     "escapes, kills, wins. Needs your Steam key and ID, and Steam's Game details set to public.", None),
    ("Games and alerts", "JARVIS_HENRIK_KEY", "Valorant: HenrikDev API key", "secret",
     "Valorant isn't on Steam. A free key from api.henrikdev.xyz (sign in with Discord) lets him read your last match.", None),
    ("Games and alerts", "JARVIS_RIOT_ID", "Valorant: your Riot ID", "text", "Like Name#TAG.", None),
    ("Games and alerts", "JARVIS_RIOT_REGION", "Valorant: region", "choice", "",
     [("na", "North America"), ("latam", "Latin America"), ("br", "Brazil"), ("eu", "Europe"), ("ap", "Asia Pacific"), ("kr", "Korea")]),
    ("Games and alerts", "JARVIS_CLIP_WITH", "\"Clip that\" uses", "choice",
     "Which recorder saves the clip. He only presses its own save shortcut.",
     [("auto", "Whichever is running"), ("nvidia", "NVIDIA Instant Replay (Alt+F10)"), ("gamebar", "Xbox Game Bar (Win+Alt+G)")]),
    ("Games and alerts", "JARVIS_SALES_RADAR", "Sales radar", "bool",
     "Once a week, Steam games on sale that are like the ones you actually play (not ones you own).", None),
    ("Games and alerts", "JARVIS_MONTH_REPORT", "Monthly gaming report", "bool",
     "On the 1st: hours per game, sessions, longest sitting, wins and losses, and the change from last month.", None),
    ("Games and alerts", "JARVIS_PATCH_ALERTS", "Patch heads-up when you launch a game", "bool",
     "If the game updated in the last two days, he tells you the gist as it loads.", None),
    ("Personality", "JUNO_PERSONALITY", "His personality", "choice", "How he comes across. His rules stay the same.",
     [("classic", "Classic (dry British wit, calm)"), ("warm", "Warm (loyal old butler)"),
      ("sharp", "Sharp (sardonic, unimpressed)"), ("focused", "Focused (businesslike)"),
      ("theatrical", "Theatrical (grand, dramatic)")]),
    ("Personality", "JUNO_HUMOR", "Humor", "choice", "",
     [("low", "A little"), ("medium", "Some"), ("high", "A lot")]),
    ("Personality", "JUNO_REPLY_LENGTH", "How much he says", "choice", "",
     [("short", "As short as possible"), ("normal", "Short, more when it helps"), ("detailed", "Fuller answers")]),
    ("Personality", "JARVIS_MAX_WORDS", "Most words he reads out", "number",
     "Past this he finishes the thought and the rest stays on screen. Ask for detail and there's no limit.", None),
    ("Personality", "JUNO_PERSONA_NOTES", "Anything else about him", "text",
     "In your own words: \"call me captain\", \"loves bad puns\", \"never talks about the weather\".", None),
    ("Personality", "JUNO_OPINIONS", "His opinions", "text",
     "He has his own tastes (music, games, hot takes) and sticks to them. Add or change them here, like: "
     "\"loves Dead by Daylight killers, hates country music\".", None),
    ("Personality", "JUNO_MOODS", "Moods", "bool",
     "His tone shifts a little with the hour, how long you've been gone, how your games are going, and how you've "
     "been talking to him. He never announces it.", None),
    ("Personality", "JARVIS_VOICE", "His voice", "choice", "Changes straight away. ElevenLabs voices are set on the Voice page.",
     [("bm_lewis", "Lewis (British)"), ("bm_george", "George (British, deeper)"), ("bm_daniel", "Daniel (British, crisp)"),
      ("bm_fable", "Fable (British, storyteller)"), ("am_michael", "Michael (American)")]),
    ("Check-ins", "JUNO_BIRTHDAYS", "Birthday reminders", "bool",
     "Birthdays you mention get a heads-up three days before (gift time) and on the day.", None),
    ("Steam", "STEAM_API_KEY", "Steam Web API key", "secret",
     "Free: steamcommunity.com/dev/apikey (any domain name, like localhost). Lets him see friends online, your library "
     "and wishlist. Read-only.", None),
    ("Steam", "STEAM_ID", "Your Steam profile", "text",
     "The link to your profile, your custom URL name, or your 17-digit Steam ID. Set Game details to Public in Steam's "
     "privacy settings so he can see your library.", None),
    ("Steam", "JUNO_STEAM_SALES", "Wishlist sale alerts", "bool", "Checked twice a day.", None),
    ("Steam", "JUNO_STEAM_SALE_MIN", "Only when it's at least", "choice", "",
     [("10", "10% off"), ("20", "20% off"), ("33", "33% off"), ("50", "50% off"), ("75", "75% off")]),
    ("Steam", "JUNO_PATCH_NOTES", "Patch notes for games I play", "bool",
     "When a Steam game you've played in the last two weeks posts an update, he tells you and can sum it up.", None),
    ("Stocks", "JUNO_STOCKS", "Watchlist", "text",
     "Tickers or company names, separated by commas (like: NVDA, AAPL, Bitcoin). Or just say \"Jarvis, add AMD to my "
     "watchlist\". Prices come from Yahoo Finance (free, can be up to 15 minutes behind).", None),
    ("Stocks", "JUNO_STOCK_ALERTS", "Heads-up on big moves", "bool",
     "When something on your watchlist moves a lot in a day, he mentions it (never mid-game) and can tell you why.", None),
    ("Stocks", "JUNO_STOCK_ALERT_PCT", "Big means at least", "choice", "",
     [("3", "3% in a day"), ("4", "4% in a day"), ("5", "5% in a day"), ("8", "8% in a day"), ("10", "10% in a day")]),
    ("Stocks", "JUNO_STOCKS_BRIEFING", "Markets in the morning briefing", "bool",
     "One line: the big indexes and anything on your watchlist that moved 2% or more. He gives his read on stocks "
     "when you ask, but he isn't a financial advisor and he can't buy or sell anything.", None),
    ("Games and alerts", "JUNO_GAME_BRIEFING", "Briefing when a game starts", "bool",
     "Friends online, queue times (Dead by Daylight), the latest patch notes and how your games have gone, on the "
     "desktop while it loads. Needs the living desktop.", None),
    ("Stocks", "JUNO_STOCK_EARNINGS", "Night-before earnings heads-up", "bool",
     "The evening before a company on your watchlist reports, he mentions it and offers what he'd watch.", None),
    ("Stocks", "JUNO_STOCKS_WEEKLY", "Sunday recap", "bool",
     "Sunday evening: how the market, your watchlist and his paper calls did this week. In a few words.", None),
    ("Starting conversations", "JUNO_CHAT_FIRST", "Start conversations about what I'm doing", "bool",
     "When you're paused in something for a while (not mid-typing, not in a game or a call), he says something about it "
     "and listens for your answer. He only knows the app and window title; those go to Claude when he speaks up.", None),
    ("Starting conversations", "JUNO_CHAT_EVERY", "How often", "choice", "",
     [("rarely", "Rarely (a few times a day)"), ("normal", "Now and then (every 30 to 45 minutes at most)"),
      ("often", "Often (every 10 to 15 minutes)"), ("custom", "Custom (the minutes below)")]),
    ("Starting conversations", "JUNO_CHAT_MINUTES", "Custom: about every (minutes)", "number",
     "Used when How often is Custom.", None),
    ("Starting conversations", "JUNO_CHAT_DWELL", "Only after I've been in something for", "choice", "",
     [("0", "Depends on How often"), ("2", "2 minutes"), ("5", "5 minutes"), ("10", "10 minutes"), ("20", "20 minutes"),
      ("30", "30 minutes")]),
    ("Starting conversations", "JUNO_CHAT_MAX", "Most times a day", "choice", "",
     [("0", "Depends on How often"), ("3", "3"), ("6", "6"), ("12", "12"), ("24", "24"), ("200", "No limit")]),
    ("Starting conversations", "JUNO_CHAT_PAUSE", "Wait until I've paused for", "choice",
     "How long since your last key press or mouse move before he speaks up.",
     [("3", "3 seconds"), ("6", "6 seconds"), ("15", "15 seconds"), ("30", "30 seconds")]),
    ("Starting conversations", "JUNO_CHAT_STYLE", "What he starts with", "choice", "",
     [("mixed", "Whatever fits"), ("questions", "Curious questions"), ("tips", "Useful tips"),
      ("jokes", "Jokes and teasing"), ("hype", "Hype and encouragement")]),
    ("Starting conversations", "JUNO_CHAT_TOPICS", "Things I like talking about", "text",
     "Optional, in your own words (like: game dev, hockey, Blender). He brings them in when they connect.", None),
    ("Starting conversations", "JUNO_CHAT_MUSIC", "Talk about the songs I play", "bool",
     "Now and then, when a new song starts, he says something about it. At most every 30 minutes.", None),
    ("Starting conversations", "JUNO_QUIET_HOURS", "Quiet hours", "text",
     "Like 23-8 for 11 PM to 8 AM. Empty = none.", None),
    ("Starting conversations", "JUNO_CHAT_NEVER", "Never bring up", "text",
     "Apps or words, separated by commas (like: excel, tax, discord). Banking, passwords and private windows never.", None),
    ("Check-ins", "JUNO_EVENING_WRAP", "Evening wrap-up", "bool",
     "Once an evening: tomorrow's weather, what's on tomorrow, and where your time went today.", None),
    ("Check-ins", "JUNO_EVENING_AT", "Evening wrap-up from", "choice", "",
     [(str(h), f"{h - 12} PM") for h in range(17, 24)]),
    ("Check-ins", "JUNO_RAIN_ALERT", "Rain heads-up", "bool", "When rain or snow is likely in the next hour or so.", None),
    ("Check-ins", "JUNO_JOURNAL", "Journal question at night", "bool",
     "Once a night he asks one question about your day and writes your answer in \"Jarvis Journal.txt\" on your "
     "desktop (plain text: edit or delete it any time). Say \"skip\" and nothing's written.", None),
    ("Check-ins", "JUNO_JOURNAL_AT", "Ask from", "choice", "",
     [(str(h), f"{(h - 1) % 12 + 1} {'PM' if h >= 12 else 'AM'}") for h in (19, 20, 21, 22, 23)]),
    ("Check-ins", "JUNO_JOURNAL_FILE", "Journal file (optional)", "text",
     "Full path if you want it somewhere else. Empty = your desktop.", None),
    ("Check-ins", "JUNO_GOODNIGHT_PC", "When I say goodnight, the PC", "choice",
     "After 30 seconds (say anything to stop it). It never sleeps while a game, render or download is still going; "
     "it locks instead.",
     [("sleep", "Goes to sleep"), ("lock", "Locks"), ("nothing", "Stays as it is")]),
    ("Check-ins", "JUNO_GOODNIGHT_LIGHTS", "...and the lights", "choice", "Needs smart lights connected.",
     [("off", "Turn off"), ("dim", "Dim to 10%"), ("leave", "Leave them")]),
    ("Check-ins", "JUNO_BUTLER_NUDGE", "Messy Downloads heads-up", "bool",
     "At most once a week, if Downloads has piled up (old installers, duplicates), he offers to tidy it. He always "
     "shows you what moves or goes to the Recycle Bin first.", None),
    ("Check-ins", "JUNO_BREAK_EVERY", "Break reminders", "choice", "After this long at the PC without a 5-minute break.",
     [("0", "Off"), ("45", "45 minutes"), ("60", "1 hour"), ("90", "1.5 hours"), ("120", "2 hours"), ("180", "3 hours")]),
    ("Answering", "JARVIS_LEAN_TOOLS", "Load tools as needed", "bool",
     "He gets the everyday tools plus whatever your request needs, instead of all ~55 every time. Faster and much "
     "cheaper per question. Turn off if he ever says he can't do something he should.", None),
    ("Answering", "JARVIS_INSTANT", "Instant commands", "bool",
     "Simple things (volume, play/pause, opening an app) happen right away without asking Claude.", None),
    ("Answering", "JARVIS_INSTANT_ACK", "Say \"on it\" straight away", "bool",
     "A quick acknowledgement while he works on longer things.", None),
    ("Answering", "JUNO_FOLLOW_UP", "Answer without his name for (seconds)", "number",
     "After he asks you something, how long you can reply without saying Jarvis.", None),

    # ---------------------------------------------------------------- Voice & effects
    ("Voice effect", "JUNO_VOICE_EFFECT", "Effect", "choice", "Added on top of his voice.",
     [("none", "None"), ("ethereal", "Ethereal (airy shimmer)"), ("echo", "Echo (big room)"), ("glitch", "Glitch (digital stutter)"),
      ("robot", "Robot"), ("radio", "Radio"), ("synth", "Synth (deep, metallic)")]),
    ("Voice effect", "JUNO_EFFECT_STRENGTH", "Effect strength", "choice", "",
     [("0.3", "Subtle"), ("0.6", "Medium"), ("0.85", "Strong"), ("1", "Full")]),
    ("Voice engine", "JARVIS_TTS", "Voice engine", "choice",
     "If one fails he falls back to the next.",
     [("kokoro", "Kokoro (free, on this PC, natural)"), ("elevenlabs", "ElevenLabs (most human, paid)"),
      ("edge", "Microsoft online (free)"), ("sapi", "Windows built-in (robotic, always works)")]),
    ("Voice engine", "ELEVENLABS_API_KEY", "ElevenLabs API key", "secret", "Only for the ElevenLabs engine.", None),
    ("Voice engine", "JUNO_ELEVENLABS_VOICE_ID", "ElevenLabs voice ID", "text", "Any voice from your ElevenLabs library.", None),

    # ---------------------------------------------------------------- Languages
    ("Language", "JUNO_LANGUAGE", "He understands and answers in", "choice",
     "Anything but English switches his hearing to a multilingual model (a little slower on the first start while it "
     "downloads), and his voice switches to match.",
     [("en", "English"), ("es-en", "Spanish and English, mixed"), ("auto", "Whatever I speak"), ("es", "Spanish"), ("fr", "French"), ("it", "Italian"),
      ("pt", "Portuguese (Brazil)"), ("hi", "Hindi")]),

    # ---------------------------------------------------------------- Microphone
    ("Microphone", "JUNO_MIC", "Microphone", "choice", "If it's unplugged he uses Windows' default.", None),
    ("Who he listens to", "JARVIS_VOICE_ID", "Only answer my voice", "bool",
     "Once he's learned your voice (say \"Jarvis, learn my voice\" and talk for about 20 seconds), anything said "
     "in another voice is ignored, even with his name. Checked on this PC; nothing is uploaded.", None),
    ("Who he listens to", "JARVIS_VOICE_ID_STRICT", "How sure he has to be", "choice",
     "Strict ignores more people but may sometimes miss you on a bad mic.",
     [("relaxed", "Relaxed"), ("normal", "Normal"), ("strict", "Strict")]),
    ("Who he listens to", "JARVIS_GUEST_MODE", "Guests he knows", "bool",
     "Friends whose voices he's learned (\"learn my friend Leo's voice\") can ask questions and play music, but can't "
     "change anything, see your personal stuff or approve anything. Off: only you.", None),
    ("Who he listens to", "JARVIS_BARGE_IN", "Cut in while he's talking", "bool",
     "Start talking over him and he quietens straight away; \"wait, no...\" or \"actually...\" stops him and he answers "
     "the new thing. Once he knows your voice, anything you say over him counts.", None),
    ("Who he listens to", "JARVIS_CONVO", "Conversation mode", "choice",
     "After he answers, keep talking without saying his name for this long. Best with \"Only answer my voice\" on, "
     "or friends in the room will be talking to him too.",
     [("0", "Off"), ("20", "20 seconds"), ("45", "45 seconds"), ("120", "2 minutes")]),
    ("Who he listens to", "JARVIS_PRIVATE", "Private mode", "bool",
     "Speech recognition runs only on this PC (never Groq), even for things you say to him. A bit slower and less "
     "accurate on a slow PC. What you ask him still goes to Claude to answer.", None),
    ("Microphone", "JUNO_MIC_FLOOR", "How loud you have to be", "choice",
     "Raise it if background noise keeps setting him off.",
     [("250", "Quiet voice is fine"), ("400", "Normal"), ("650", "Speak up"), ("900", "Noisy room")]),
    ("Microphone", "JARVIS_VAD", "Speech detection", "choice", "Stricter ignores more music and TV.",
     [("0.35", "Relaxed"), ("0.5", "Normal"), ("0.65", "Strict"), ("0.8", "Very strict")]),
    ("Microphone", "JARVIS_PAUSE", "Pause that ends what you're saying (seconds)", "number",
     "Shorter is snappier; longer lets you think mid-sentence.", None),
    ("Microphone", "JARVIS_SMART_PAUSE", "Smart pauses", "bool",
     "He answers sooner when what you said is clearly finished, and waits longer after \"and...\".", None),
    ("Microphone", "JARVIS_ECHO_CANCEL", "Cancel his own voice", "bool",
     "So you can talk over him on speakers. Turn off if you only use headphones.", None),
    ("Microphone", "JARVIS_MUTE_HOTKEY", "Mute hotkey", "text", "Like ctrl+alt+m.", None),
    ("Faster hearing", "GROQ_API_KEY", "Groq API key", "secret",
     "Optional. Free at console.groq.com; makes him understand you much faster on slower PCs.", None),

    # ---------------------------------------------------------------- Appearance & animations
    ("His desktop", "JARVIS_LIVING_DESKTOP", "His world as your desktop", "bool",
     "His world and his visualizer become your wallpaper on every monitor; desktop icons are hidden while he runs.", None),
    ("His desktop", "JUNO_DESK_SCENE", "Scene", "choice",
     "Where he lives. A still picture: nothing moves but his voice ring, and only while you two are talking. "
     "Changes straight away. Or say \"Jarvis, switch your desktop to the archive\".",
     [("bench", "Drafting bench (his blueprints at night)"), ("station", "Orbital station (above a planet)"),
      ("archive", "The archive (his private library)"), ("signal", "Listening post (a signals room)"),
      ("chart", "Cartographer (a map of your digital island)")]),
    ("His desktop", "JUNO_PULLS", "Pull things up while he answers", "bool",
     "Ask about a stock, the weather, your day, your PC or anything he searches, and a live panel builds in beside him "
     "(the sources he read, a preview of a file he made...). \"Clear that\" puts them away, \"show me\" brings one to "
     "the middle, \"back\" undoes that. Off: only when you ask (\"pull up my PC\").", None),
    ("His desktop", "JUNO_DESK_CALM", "Calm panels", "bool",
     "Panels and widgets just appear, with no sweep-in or scanning effects. Off: the old animated panels.", None),
    ("His desktop", "JUNO_FPS", "Frame rate", "choice",
     "For him on the desktop and on the music player. Or just tell him: \"set your animations to 60 fps\".",
     [("10", "10 fps (lightest)"), ("15", "15 fps"), ("20", "20 fps"), ("24", "24 fps"), ("30", "30 fps"),
      ("45", "45 fps"), ("60", "60 fps (smoothest)")]),
    ("His desktop", "JUNO_DESK_VIZ", "Voice visualizer", "choice", "",
     [("both", "Middle of every monitor"), ("main", "Middle of the main monitor"), ("second", "Other monitors only"),
      ("corner", "Small, bottom-left corner"), ("off", "Off")]),
    ("Desktop widgets", "JUNO_DESK_WIDGETS", "Widgets on his desktop", "bool",
     "Live cards on your wallpaper: PC stats, what's playing, weather, today, notes and Discord. To look at (the "
     "desktop can't take clicks). Or tell him: \"hide the desktop widgets\".", None),
    ("Desktop widgets", "JUNO_DESK_WIDGETS_WHERE", "Where they go", "choice", "",
     [("right", "Right side of the main monitor"), ("left", "Left side of the main monitor"),
      ("second", "My other monitor (if I have one)")]),
    ("Desktop widgets", "JUNO_W_STATS", "PC stats", "bool",
     "Processor, memory, graphics card load and temperature (NVIDIA), video memory, disk and network.", None),
    ("Desktop widgets", "JUNO_W_MUSIC", "Now playing", "bool", "Hides itself when nothing's playing.", None),
    ("Desktop widgets", "JUNO_W_WEATHER", "Weather", "bool", "Now and the next few hours.", None),
    ("Desktop widgets", "JUNO_W_CALENDAR", "Today", "bool", "Your calendar and reminders, counting down to the next one.", None),
    ("Desktop widgets", "JUNO_W_NOTES", "Notes, lists and timers", "bool",
     "The sticky notes, checklists and timers you make in glass mode (or ask him for).", None),
    ("Desktop widgets", "JUNO_W_DISCORD", "Messages", "bool", "The last few Discord messages and phone notifications, as they come in.", None),
    ("Desktop widgets", "JUNO_W_STOCKS", "Watchlist", "bool", "Your stocks and how they're doing today (Settings > Connected apps > Stocks).", None),
    ("Glass mode", "JUNO_GLASS_WHERE", "Where glass mode shows up", "choice",
     "Its own window shows your camera behind the cards. On your desktop, the cards float over his world on your main "
     "monitor instead (your windows get minimized so you can see it, and come back when you close it). The desktop "
     "can't take mouse clicks, so there it's hands only. Needs \"His world as your desktop\" on. Or just tell him: "
     "\"put glass mode on my desktop\".",
     [("window", "Its own window"), ("desktop", "On my desktop")]),
    ("Music player", "JUNO_MUSIC_PLAYER", "Music player pop-up", "bool",
     "When music plays he shows his player instead of opening Spotify's window.", None),

    # ---------------------------------------------------------------- Application access
    ("What he can use", "JARVIS_SCREEN_WATCH", "Watch my screen while we talk", "bool",
     "Faster answers about what's on screen. Kept in memory only, never saved; only while you're talking to him "
     "and never during fullscreen games.", None),
    ("What he can use", "JARVIS_CAMERA", "Camera", "bool", "Only when you ask him to look at you or something you're holding.", None),
    ("What he can use", "JARVIS_FREE_CREATE", "Where he can create without asking", "choice",
     "New files and folders only: changing, moving or deleting anything that's already yours still asks (and "
     "\"Always allow\" on that prompt stops it asking). Windows and program folders always ask.",
     [("personal", "Desktop, Documents, Downloads, Pictures, Music, Videos"), ("jarvis", "Only his own folder")]),
    ("What he can use", "JARVIS_READ_ANYWHERE", "Read files anywhere on my drives", "bool",
     "Off: only your user folder and folders you've let him into.", None),
    ("What he can use", "DISCORD_BOT_ON_SERVER", "Discord bot runs on my server", "bool",
     "Turn on if you set up the bot on an always-on server (server/README.md), so the PC doesn't start a second copy. "
     "Takes effect after a restart.", None),
    ("What he can use", "JUNO_PHONE_NOTIFS", "Show my phone's notifications", "bool",
     "Through Windows' Phone Link app (Start > Phone Link: pair your phone and turn on notifications). Texts and app "
     "notifications show on his desktop and in the log. Nothing is ever sent to your phone.", None),
    ("What he can use", "JUNO_PHONE_SPEAK", "Read phone notifications out loud", "bool",
     "Off by default. Never during games (except people you've let through) or while muted.", None),
    ("What he can use", "JARVIS_DISCORD_READ", "Read my Discord notifications", "bool",
     "DMs and pings that pop up as Windows notifications.", None),
    ("What he can use", "JARVIS_KEEP_FOCUS", "Stop apps stealing focus", "bool",
     "When he opens something it won't yank you out of what you're doing.", None),
    ("What he can use", "JUNO_BLOCKED_APPS", "Apps he may never touch", "text",
     "Separated by commas (like: steam, outlook, banking). He won't open, close, type in, click in or look at them.", None),
    ("Activity memory", "JARVIS_ACTIVITY", "Remember what I work on", "bool",
     "Logs which app and window is in front (names and titles only, never screenshots or typing), on this PC only, so "
     "you can ask 'what was I working on yesterday?'.", None),
    ("Activity memory", "JARVIS_ACTIVITY_DAYS", "Keep it for (days)", "number", "Older days are deleted.", None),
    ("Activity memory", "JARVIS_ACTIVITY_SKIP", "Never log", "text",
     "Apps or words, separated by commas. Private windows and password managers are never logged anyway.", None),

    # ---------------------------------------------------------------- Connected apps
    ("Email", "EMAIL_ADDRESS", "Email address", "text", "Gmail, Yahoo or iCloud. Read-only: he can't send or delete.", None),
    ("Email", "EMAIL_APP_PASSWORD", "App password", "secret",
     "NOT your normal password. Gmail: myaccount.google.com/apppasswords (needs 2-Step Verification).", None),
    ("Email", "JARVIS_EMAIL_ANNOUNCE", "Say new emails out loud", "bool", "Who it's from and the subject.", None),
    ("Smart home", "HOME_ASSISTANT_URL", "Home Assistant address", "text",
     "Like http://homeassistant.local:8123. Home Assistant covers almost every brand of light. Philips Hue works "
     "without it: just say \"pair my Hue bridge\".", None),
    ("Smart home", "HOME_ASSISTANT_TOKEN", "Home Assistant access token", "secret",
     "Home Assistant > your profile (bottom left) > Security > Long-lived access tokens > Create token.", None),
    ("Smart home", "JUNO_HUE_BRIDGE", "Hue Bridge address (optional)", "text",
     "Only if he can't find it by himself (like 192.168.1.20).", None),
    ("Smart home", "JUNO_HUE_USER", "Hue Bridge key", "secret", "Filled in for you when you pair.", None),
    ("Smart home", "JUNO_LIGHTS_SYNC", "Lights take his colours", "bool",
     "The lights below take his blue while he runs.", None),
    ("Smart home", "JUNO_LIGHTS_SYNC_TARGET", "Which lights", "text", "A room or light name, or all.", None),
    ("Discord bot", "DISCORD_BOT_TOKEN", "Bot token", "secret",
     "discord.com/developers > your app > Bot > Reset Token. Treat it like a password.", None),
    ("Discord bot", "DISCORD_OWNER_ID", "Your Discord user ID", "text",
     "Discord > Settings > Advanced > Developer Mode, then right-click your name > Copy User ID.", None),
    ("Discord bot", "JARVIS_DISCORD_TYPE", "Let him type in my Discord app", "bool",
     "Sends messages from YOUR account by typing into the Discord app, only when you ask, and you approve each one.", None),
    ("Discord bot", "DISCORD_BOT_REPLY", "Who he answers on Discord", "choice", "",
     [("everyone", "Everyone (rate limited)"), ("owner", "Only me"), ("off", "Nobody (read and send only)")]),
    ("Discord bot", "DISCORD_UPDATES_CHANNEL", "Channel for his update notes", "text",
     "Like #updates, or \"updates in My Server\", or a channel ID. After every update, his bot posts what's new there "
     "(once per version). Anyone can also ask the bot \"what's new\" or \"changelog 1.0.25\".", None),
    ("Discord bot", "DISCORD_UPDATES_MODE", "When he updates", "choice",
     "Ask: after an update he asks if you want the notes posted (say yes, or tap Yes). Any time, you can also say "
     "\"post the changelog\". On a server the bot can't ask you, so set it to post by itself there.",
     [("ask", "Ask me, then post"), ("auto", "Post by himself"), ("off", "Only when I ask")]),
    ("Spotify", "SPOTIFY_CLIENT_ID", "Spotify Client ID", "text",
     "Needs Spotify Premium. developer.spotify.com > your app > Settings. Not the secret.", None),
    ("Netflix", "JARVIS_NETFLIX", "Open Netflix in", "choice", "",
     [("auto", "The app if installed"), ("web", "The website"), ("app", "The app")]),
    ("Netflix", "JARVIS_NETFLIX_TRACK", "Keep a log of what I watch", "bool", "Stays on this PC.", None),
    ("Apple Music", "JARVIS_APPLE_MUSIC", "Open Apple Music in", "choice", "",
     [("auto", "The app if installed"), ("web", "The website"), ("app", "The app")]),
    ("Calendar", "JARVIS_CAL_DEFAULT", "Add new events to", "choice",
     "Google and Outlook: he opens the event filled in and presses Save (you OK it first).",
     [("jarvis", "His own calendar"), ("caldav", "My CalDAV calendar (iCloud, Fastmail, Yahoo...)"),
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
    "Claude": "general", "You": "general", "Stocks": "apps", "Starting up": "general", "Games and alerts": "general",
    "Personality": "conversation", "Starting conversations": "conversation", "Check-ins": "conversation", "Answering": "conversation",
    "Voice effect": "voice", "Voice engine": "voice",
    "Language": "languages",
    "Microphone": "mic", "Faster hearing": "mic", "Who he listens to": "mic", "Whisper mode": "voice",
    "Automation": "conversation", "While you're away": "conversation", "Weekly letter": "conversation",
    "His desktop": "appearance", "Music player": "appearance", "Desktop widgets": "appearance", "Glass mode": "appearance",
    "What he can use": "access", "Activity memory": "access",
}
MODE_KEYS = {"UNREAL_AI_KEY"}
SECRETS = {f[1] for f in FIELDS if f[3] == "secret"}
RETIRED = ("BLENDER_AI_KEY", "BLENDER_AI_MODEL")      # Blender mode used to take an AI key; it's a Meshy key now
DEFAULTS = {"JARVIS_DAILY_BUDGET": "5", "JARVIS_ADDRESS_AS": "sir",
            "JARVIS_MINI": "true", "JARVIS_MORNING_BRIEFING": "true", "JARVIS_GAME_MODE": "true", "JUNO_GAME_DETECT": "true", "JUNO_GAME_CHECKIN": "true", "JARVIS_ALERTS": "true",
            "JUNO_PERSONALITY": "classic", "JUNO_HUMOR": "medium", "JUNO_REPLY_LENGTH": "normal", "JARVIS_MAX_WORDS": "150",
            "JUNO_CHAT_FIRST": "true", "JUNO_CHAT_EVERY": "normal", "JUNO_CHAT_MINUTES": "40", "JUNO_CHAT_DWELL": "0",
            "JUNO_CHAT_MAX": "0", "JUNO_CHAT_PAUSE": "6", "JUNO_CHAT_STYLE": "mixed", "JUNO_CHAT_MUSIC": "true",
            "JUNO_EVENING_WRAP": "true", "JUNO_EVENING_AT": "20", "JUNO_RAIN_ALERT": "true", "JUNO_BREAK_EVERY": "120", "JUNO_BUTLER_NUDGE": "true", "JUNO_MOODS": "true", "JUNO_BANTER": "true", "JUNO_BIRTHDAYS": "true",
            "JUNO_STEAM_SALES": "true", "JUNO_STEAM_SALE_MIN": "20", "JUNO_PATCH_NOTES": "true",
            "JARVIS_VOICE": "bm_lewis", "JUNO_JOURNAL": "true", "JUNO_JOURNAL_AT": "22",
            "JUNO_GOODNIGHT_PC": "sleep", "JUNO_GOODNIGHT_LIGHTS": "off", "JUNO_REACTIONS": "true", "JUNO_LIGHTS_SYNC": "false", "JUNO_LIGHTS_SYNC_TARGET": "all", "JUNO_QUIET_HOURS": "23-8", "JARVIS_INSTANT": "true",
            "JARVIS_INSTANT_ACK": "true", "JUNO_FOLLOW_UP": "8", "JUNO_VOICE_EFFECT": "none", "JUNO_EFFECT_STRENGTH": "0.6",
            "JARVIS_TTS": "kokoro", "JUNO_ELEVENLABS_VOICE_ID": "EXAVITQu4vr4xnSDxMaL", "JUNO_LANGUAGE": "en",
            "JUNO_MIC": "default", "JUNO_MIC_FLOOR": "400", "JARVIS_VAD": "0.5", "JARVIS_PAUSE": "1.5",
            "JARVIS_SMART_PAUSE": "true", "JARVIS_ECHO_CANCEL": "true", "JARVIS_MUTE_HOTKEY": "ctrl+alt+m",
            "JUNO_DESK_SCENE": "bench", "JUNO_DESK_CALM": "true", "JUNO_STOCK_ALERTS": "true", "JUNO_STOCK_ALERT_PCT": "4", "JUNO_STOCKS_BRIEFING": "true", "JARVIS_LEAN_TOOLS": "true", "JARVIS_PERFORMANCE": "auto", "JARVIS_POSTMATCH": "true", "JARVIS_RIOT_REGION": "na", "JARVIS_CLIP_WITH": "auto",
            "JARVIS_SALES_RADAR": "true", "JARVIS_MONTH_REPORT": "true", "JARVIS_GUEST_MODE": "true", "JARVIS_BARGE_IN": "true", "JARVIS_EMOTION": "true", "JARVIS_BEDTIME": "off", "JARVIS_CLIP_HISTORY": "true", "JARVIS_SHOT_SEARCH": "true", "JARVIS_CRASH_REPORTS": "ask", "JARVIS_VOICE_ID": "true", "JARVIS_VOICE_ID_STRICT": "normal", "JARVIS_CONVO": "45",
            "JARVIS_PRIVATE": "false", "JARVIS_WHISPER": "auto", "JARVIS_WHISPER_FROM": "23", "JARVIS_WHISPER_TO": "7",
            "JARVIS_WHISPER_VOL": "35", "JARVIS_TRIGGERS": "true", "JARVIS_PLAY_BREAK": "180", "JARVIS_WELCOME_BACK": "20",
            "JARVIS_AMBIENT": "rare", "JARVIS_LETTER": "true", "JARVIS_PATCH_ALERTS": "true", "JARVIS_FREE_CREATE": "personal", "JUNO_PULLS": "true", "JUNO_GAME_BRIEFING": "true", "JUNO_STOCKS_WEEKLY": "true", "JUNO_STOCK_EARNINGS": "true", "JUNO_W_STOCKS": "true", "JUNO_FPS": "30", "JUNO_DESK_VIZ": "both", "JUNO_GLASS_WHERE": "window", "JUNO_DESK_WIDGETS": "true",
            "JUNO_DESK_WIDGETS_WHERE": "right", "JUNO_W_STATS": "true", "JUNO_W_MUSIC": "true", "JUNO_W_WEATHER": "true",
            "JUNO_W_CALENDAR": "true", "JUNO_W_NOTES": "true", "JUNO_W_DISCORD": "true", "JUNO_MUSIC_PLAYER": "true", "JARVIS_CAMERA": "true",
            "JARVIS_DISCORD_READ": "true", "JUNO_PHONE_NOTIFS": "true", "JUNO_PHONE_SPEAK": "false", "JARVIS_KEEP_FOCUS": "true", "DISCORD_BOT_REPLY": "everyone", "DISCORD_UPDATES_MODE": "ask",
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
            opts = known[key][5]
            if opts is None and key == "JUNO_MIC":         # filled in from the mics plugged in right now
                try:
                    import speech
                    opts = speech.mic_devices()
                except Exception:
                    opts = []
                opts = list(opts) + [("default", "")]
            allowed = [o[0] for o in (opts or [])]
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
