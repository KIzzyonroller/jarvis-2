# What's new

Newest first. After an update, Jarvis shows everything added since the version you had before.
Each release starts with a "## version" line: the same number you type when you run the Release workflow (1.0.12, 1.0.13...).

## 1.0.14
- **Smaller CPU spikes when he talks.** Making his voice used every core on your PC in bursts, with the cores spinning even between sentences. Now it uses a few cores, they rest between sentences, it stays just ahead of what he's saying instead of making the whole reply at once, and when both of them talk they take turns making their voices. Speech recognition's threads rest between bits of listening too. Same voice, same speed.

## 1.0.13
- **He watches things for you.** "Tell me when my download finishes", "let me know when Blender's done rendering", "tell me when that GPU drops under 500 dollars" (paste or open the shop page), "ping me when 'In stock' shows up on this page", "tell me when Discord closes", "tell me when a file shows up in my Renders folder". When it happens he says it, shows it here and on your phone, and pops a Windows notification. Add "and then open it" and he does that too (you OK it when you set it up). Last resort for things nothing else can see, like a game queue: "watch my screen and tell me when the match is found" (he looks every few minutes; each look costs about a cent). They're listed in the System panel under Watching, with Stop.
- **Activity memory (off until you turn it on).** Switch it on in the System panel or Settings, and he keeps track of which app and window you're in. Then ask "what was I working on yesterday afternoon?", "how long was I in Blender today?", "when did I last have the budget spreadsheet open?" or "reopen what I had going on Friday". Only app and window names, never screenshots or typing, kept on this PC for 14 days. Private windows and password managers are never logged, you can add your own "never log" list, and "pause activity memory for an hour" or "wipe it" work any time. While it's on he also knows which app you're in when you say "save this" or "what's this?".

## 1.0.12
- **A full calendar.** "Dentist Tuesday at 3", "gym Monday Wednesday Friday 6 to 7am", "Mom's birthday March 3" (every year, on its own), "what's on tomorrow?", "am I free Friday afternoon?", "move the dentist to 4", "skip standup this Wednesday". Repeating events, alerts before things start (10 minutes by default, spoken), clash warnings, and today's events in the morning briefing. The System panel has an Agenda tab for the next 7 days.
- **Your calendar apps.** See your Google Calendar and Outlook events by pasting their private calendar link in Settings > Calendar. iCloud, Fastmail, Yahoo and Nextcloud connect two-way (CalDAV, with an app password). New events can go straight to Google Calendar or Outlook too: he opens the event filled in and presses Save after you OK it. Or to Outlook desktop and the Windows Calendar app.
- **Calendar mode.** Just the calendar and reminders in one window, using very little of your PC: no microphone, voice models, animations or AI running in the background. Type things the way you'd say them ("lunch with Sam tomorrow at noon"), see the month at a glance, and get alerts as Windows notifications with a chime (and Windows' own voice, if you like). Say "calendar mode", press Calendar mode in the System panel, or set Settings > Calendar > Start in. "Full Jarvis" in the window switches back.

## 1.0.11
- **Blender mode now uses a Meshy key, and makes detailed models.** Creatures, characters, statues, figurines, ornate props: describe it or give him a picture, and Meshy makes it in a minute or two. It lands in your Blender standing on the floor at the size you asked for, and he checks it, adds measured parts and exports it for printing. Get the key at meshy.ai/developers/keys (Meshy Pro or higher). Studio shows your Meshy credits left. The old Blender AI key slot is gone; the thinking runs on your main Claude key.
- **Where to get each key** is written right in Studio, on the first-run screen and in Settings.
- **Saving a key or setting always restarts him now**, including in Studio (the Unreal key didn't), and restarts can't get stuck any more: before, if something was slow to close, the new copy could give up and you'd be left with no Jarvis.

## 1.0.10
- **RGB lighting by voice.** "Make my lights red", "keyboard purple", "fans blue", "rainbow", "RGB off", "brightness 40", "put my lighting back". Works with Corsair iCUE, Razer Synapse, Logitech G HUB, OpenRGB and SignalRGB, all at once if you have several. If one needs a setting switched on, he tells you exactly which.
- **Closing apps actually works now.** "Close Discord" quits it properly instead of leaving it in the tray, "close Steam" shuts Steam down cleanly, "close Word" finds Word, "close Minecraft" finds the game by its window, and "close YouTube" closes just that tab. If an app is asking about unsaved work, he tells you instead of forcing it. Several at once: "close Discord, Steam and Chrome". "What's open?" lists your apps and how much memory each uses.
- **Let him into specific folders.** "You can work in my Game Project folder" lets him edit there without asking every time (deleting still asks). "You can look in my USB drive" lets him read it. You approve each one, they're listed in the System panel with Remove, and passwords and keys stay off-limits. New in Settings: turn off "Read files anywhere" to keep him to your user folder plus the folders you've let him into.
- **He waits for apps that are still loading.** Right after an app opens, or while Windows says it's not responding, he waits before typing, clicking or looking at it. Links in an already-open browser wait for the page.

## 1.0.9
- **The What's new pop-up now shows after every update, titled with the version you're actually on.** (1.0.8 still named it after the old notes.)

## 1.0.7
- **Studio: Blender and Unreal modes.** Each runs on its own AI key (Claude, OpenRouter or OpenAI, whichever you paste), so its spending is separate from your Jarvis key. They're locked until you add a key: on the first-run card, in Studio (the new cube button at the top), or in Settings. Unlocked, they check the real API of the version you have open before writing code, then work in the editor and check the result. Unreal mode is new: it works in your open Unreal Editor (one-time setup is shown in Studio), and everything it does is one Ctrl+Z.
- **He checks the app is open first.** Asking for something in an app that's closed (a song on Spotify, a message in Discord, typing in Notepad) used to start the app and act straight away, while it was still on its loading screen, so things got missed. Now he checks whether it's open, opens it if not, waits until it has actually finished loading, and only then does it. If it's already open he uses it as it is instead of opening it again.

## 2026.10.23.14
- **Living backgrounds.** Jarvis gets faint equations drifting over graph paper while a Fourier series slowly builds a wave; Ultron gets red fractures creeping in from the edges, corrupted fragments and a vast iris that slowly dilates. Very subtle, never behind him, and switchable in the System panel.
- **He says what he's doing as he does it, then stops.** "Opening Spotify." is heard before Spotify opens, and no more "Done, I've opened Spotify" afterwards. He still speaks up after an action when there's an answer, a problem or a question.
- **He presses play himself.** Without Spotify Premium (or in Apple Music), he opens the song and presses its Play button for you, the way a screen reader would: no mouse needed, works behind a game. If an app hides its buttons he uses the screen and mouse instead (never while you're in a fullscreen game).
- **Shuffle:** "shuffle my gym playlist on Spotify", "turn on shuffle", in Spotify and Apple Music.
- **Playlists from your library and from friends:** "play my gym playlist" searches everything you've made or saved; "play Alex's chill playlist" checks playlists of Alex's you've saved, then Alex's public ones.
- **Send from your own Discord:** "send Alex 'running late' from my Discord" types it into your Discord app as you. Off until you switch it on in Settings > Discord bot, and you approve every message (who it goes to and the exact text). If Discord's switcher lands on the wrong chat, he stops without sending.
- He won't call anyone "John Deadlock", and only calls people "Kizzy" on the creator's own PC.
- Updates: "check for an update" now checks HIS updates (it used to open Windows Update), and if he can't update he says exactly why.

## 2026.10.23.13
- **Settings inside the app.** Click Settings (System panel) to set your Claude and Groq keys, email, Discord bot, Spotify, Netflix and Apple Music, your name and city. Passwords and keys are hidden as you type, never shown again after saving, and stored encrypted on this PC.
- **Change their voices live.** Pick a different voice, speed and pitch for Jarvis and Ultron in Settings (with a Preview button), or just ask: "talk a bit faster", "use a deeper voice", "try an American voice".
- **Apple Music.** "Play Blinding Lights on Apple Music" finds that exact song and opens it in the Apple Music app or on the web.
- **This pop-up.** After every update he shows what's new; "What's new" in the System panel shows it again.
- Fixed: an error box about "cublas64_12.dll" on PCs with an NVIDIA card.
- First-time setup now finishes (your key, then his voice download) before he starts listening or talking.

## 2026.10.23.11
- **Email:** "read my emails", read one out, search, and optional announcements of new mail. Read-only.
- **Netflix:** open it on the web or in the app, and "what did I watch on Netflix this week?"
- **Spotify:** plays on this PC instead of your phone, checks the song really started, and "Spotify status" explains problems.

## 2026.10.23.8
- **Installable app** with automatic updates.
- **Discord bot** with a switch for sending messages.
- Follow-ups aren't ignored any more while he's "listening" on slower PCs.
- Longer answers when a question needs it, and decimals read as "four point five".
- Voice recognition (voice lock) removed: it was too picky about your tone.
