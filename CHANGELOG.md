# What's new

Newest first. After an update, Juno shows everything added since the version you had before.
Each release starts with a "## version" line: the same number you type when you run the Release workflow (1.0.12, 1.0.13...).

## 1.0.26
- **Juno is the main one now, and Jarvis and Ultron are back.** She's who you get every time the app starts. Switch with the buttons at the top of her window (Juno, Jarvis, Both, Ultron), or say "switch to Jarvis" or "Ultron, ...". "Both" is still Jarvis and Ultron taking turns.
- **Each of them has their own desktop.** Juno's purple glowing world with her diamond, Jarvis's cold blue lab light with his arc reactor, and Ultron's red furnace sky with his eye. The desktop, its visualizers and the pop-up panels all switch the moment you switch who you're talking to.
- **Glass mode: line up your hand.** If the tracked dots sit off your hand, press C (or "Line up my hand" in the help) and pinch the two circles; it corrects for your camera from then on. Tracking also lags less behind your hand.
- **PC doctor.** "Why is my PC slow?" gets what's hogging the processor and memory, disk space, days since a restart, graphics card heat and startup load, with the likely cause first. Also: "anything out of date?" (app updates, graphics driver age, Windows updates; she reports, you install), "what's filling my drive?" (big folders, caches you can clear, Steam games you haven't played in months), "why did that crash?" (she reads Windows' crash log and explains it), "what starts with Windows?" (and turning one off or on, after you approve; drivers and anti-cheat are never touched), and "is it my internet or the game?" (router vs internet ping, packet loss, Wi-Fi signal, and a speed test if you ask).
- **Steam.** Who's online and what they're playing, "what should I play?" from your library and playtime, wishlist sale alerts (twice a day, 20% off or more by default), and patch notes: when a game you've played lately updates, she tells you and sums it up on request. Needs a free Steam Web API key and your profile in Settings > Connected apps > Steam. Read-only.
- **Dead by Daylight queue times.** "How are killer queues in US East?" She checks deadbyqueue.com (an unofficial fan site) when you ask, including which regions are down.
- **Losing streaks.** Say how your games went ("we lost again", "gg we won") and she keeps count. After three losses in a row she's on your side and might suggest a break, once.
- **Moods.** Her tone shifts a little with the hour, how long you've been away, how your games are going and how you've been talking to her. She never announces it. Turn it off in Settings > Conversation & personality.
- **Banter.** Sometimes when you switch AIs, the one you're leaving gets a word in first, in their own voice.
- **Opinions.** Juno, Jarvis and Ultron each have their own tastes in music and games, plus some hot takes, and they stick to them. Add your own for Juno in Settings.
- **A voice for each.** Pick Juno's, Jarvis's and Ultron's voices in Settings > Conversation & personality. It changes right away. Ultron now has his own deeper voice instead of sharing Jarvis's.
- **Birthday radar.** Mention a birthday ("Kai's birthday is March 3rd") and she reminds you three days ahead (gift time) and on the day.
- **Instant light commands.** "Lights off", "bedroom lights on", "lights to 30 percent", "make the lights purple" and "goodnight" now happen instantly without waiting on Claude.
- **Discord bot on a server.** New `server/` folder with a step-by-step guide to running her Discord bot 24/7 on a cheap Linux server. Turn on "Discord bot runs on my server" in Settings so the PC doesn't run a second copy.
- **She posts her own update notes on Discord.** Pick a channel in Settings > Discord bot. After an update she asks "Post what's new on Discord?" and posts it when you say yes (or set her to post by herself, or only when asked). Any time, say "post the changelog" and she shows it to you, then posts it. The post is the headlines for a big release, or titles plus a line each for smaller ones. Anyone in Discord can ask the bot "what's new", "changelog 1.0.25" or "changelog full", and "copy the changelog for Discord" puts it on your clipboard.
- **Speed log.** Every answer records where the time went: hearing you, Claude's first word, tools, and her voice (timings only, never what was said). Ask "speed report" for medians and the slow cases. It's also saved as speed_report.txt in her data folder. This is the measuring step before making her faster.
- **Goodnight.** Say goodnight: she tells you tomorrow's first thing and the weather, pauses the music, turns the lights off (if connected), and puts the PC to sleep after 30 seconds. Say anything to stop it. It won't sleep while a game, render or download is still going; it locks instead. Choose sleep / lock / nothing and lights off / dim / leave in Settings > Check-ins.
- **Journal.** Once a night (10 PM by default) she asks one question about your day and writes your answer in "Juno Journal.txt" on your desktop. It's plain text, so edit or delete anything. "Journal: ..." adds an entry any time, "what did I write last week?" reads it back, and "skip" means nothing gets written.
- **Game mode.** She notices when you're playing (Steam, Epic, Riot, Xbox, GOG, EA, Ubisoft, Battle.net, or games you add) and stays quiet until it closes, even if you alt-tab: no conversation starters, check-ins or song comments, and Discord only gets read out from people you let through ("let Kai through while I'm gaming"). After a session of 20 minutes or more she asks how it went. She only ever knows the game's name; nothing reads, clicks or types in the game.
- **Game cards in glass mode.** Each game gets its own card with your notes and your own quick timers ("add a 60 second timer called DS for Dead by Daylight", then "start the DS timer" or pinch it). It pops up when the game starts if glass mode is open.
- **Read the text on screen.** "What does that error say?", "copy the text in that window", "read what's around my mouse". Windows' own text recognition does it on your PC, so it's exact and instant.
- **Clipboard tricks.** "Translate what I copied", "fix this code", "summarize this", "what's this picture?" (copied images work too). She puts the result back on your clipboard, ready to paste.
- **Your phone's notifications.** Set up Windows' Phone Link once and your texts and app notifications show up in her messages widget and pop-ups. Ask "anything on my phone?". Reading them aloud is off unless you turn it on. Nothing is ever sent to the phone.
- **File butler.** "How messy is my Downloads?", "tidy my Downloads" (sorts loose files into Installers, Archives, Pictures and so on, and "undo the tidy" puts them back), "clean my Downloads" (old installers, archives and duplicate downloads go to the Recycle Bin). She always shows you the list and asks first. At most once a week she'll mention it if things pile up.
- **Smart lights.** Philips Hue (say "pair my Hue bridge" and press its button) or anything in Home Assistant (Settings > Connected apps > Smart home). "Lights off", "bedroom to 30 percent", "make the lights purple". Turn on "Lights take her colours" and they go purple, blue or red when you switch between Juno, Jarvis and Ultron.
- **Edit what she remembers.** The Memory tab in her window now has Edit and Forget on every item, and Routines can be run, edited, deleted or added right there.
- **Widgets on her desktop.** Live cards down the side of your wallpaper: PC stats (CPU, GPU and RAM rings, GPU temperature, video memory, disk, network speed, a CPU/GPU graph, uptime), now playing, the weather with the next six hours, today's calendar counting down to the next thing, your glass-mode notes, checklists and running timers, and the latest Discord messages. Each one hides when it has nothing to show, and they stop updating while a fullscreen game is in front. Settings > Appearance & animations > Desktop widgets to pick which ones and where (right, left, or your other monitor), or tell her ("hide the Discord widget", "move the widgets to my other monitor").
- **Glass mode got a lot more to pull up.** Ask for any of these and they appear as cards you can grab:
  - **Live:** timers (a ring that counts down and chimes; twist with both hands like a dial to add minutes), a stopwatch, PC stats (CPU, memory, GPU load and temperature, video memory, download), now playing with buttons, weather with an hourly strip you scrub by moving your finger over it, today's calendar counting down to the next thing, progress bars, and a Discord feed that fills as messages arrive.
  - **Things you press:** checklists (ticks are remembered), volume and brightness sliders you pinch and slide, an app launcher, sticky notes that stay until you close them, your open windows (bring one up, move it to the other monitor, close it), and her yes/no questions as big Yes and No buttons.
  - **Things to look at:** bar and line charts, a map of any place, YouTube results (pinch one and it plays on your PC), a folder of photos to flick through, and 3D models (.glb or .gltf) that spin on their own and turn when you twist.
  - **New hand moves:** pinch any button; flick your wrist right or left for next or previous song (a quick snap, arm still); hold an open hand still to play or pause; thumbs up or down to answer her; hold up 1 to 5 fingers to pick that number on the list that's up close; hold a peace sign for a screenshot; both palms open and still brings back the last card you threw away. She also knows which card you're pointing at.
  - **Hands are allowed to be human.** Holds (crumpling with a fist, play/pause, numbers, thumbs) no longer start over when your hand wobbles, drifts, or your fist loosens for a moment: a slip pauses the countdown instead of resetting it. A pinch that flickers as your hand passes a button doesn't press it, and Reset, Close, Done and Yes/No need a real pinch (about a quarter second), so timers stop getting reset by accident.
  - **Pin a card** (the pin in its corner) and it's back next time you open glass mode.
  - **Looks:** fingertip trails, a ripple when you pinch, crumpled cards shatter into pieces (Ultron's burn up into embers), a faint blue grid for Jarvis, red scanlines and glitches for Ultron, and glitter off Juno's fingertips.
  - **Cards on your desktop without glass mode.** "Put that list on my desktop" shows it as a card on her wallpaper for a while (10 minutes by default).
  - **Glass mode on your desktop** (Settings > Appearance & animations > Glass mode, or tell her "put glass mode on my desktop"). Instead of its own window with your camera behind the cards, the cards float over her world on your main monitor. Your windows minimize so you can see it and come back when you close it. The desktop can't take clicks, so it's hands only there; say "line up my hand" if the dots are off. If the camera can't be used there, the cards stay on the desktop to look at and she tells you how to get your hands back. Needs "Her world as your desktop" on.
  - Not included: in-game FPS and CPU temperature (Windows only gives those to admin tools), directions on the map, and throwing windows to a screen edge (it's a button instead).
- **The desktop visualizer isn't clipped any more** when the voice gets loud.
- **Your desktop is her world.** Her purple sky, floor and drifting shards become your wallpaper, with a big voice visualizer in the middle of each monitor that moves with her voice (Settings > Appearance & animations to change where they go). While she works, the same holographic panels from her window pop up either side of it: the web search radar, the PowerShell terminal, launch sequences, now playing, volume, weather and your day, Discord messages and her thinking. She herself lives on the music player.
- **Her music player.** When music plays she pops up a player in the bottom-right corner: now playing, the sound waves, the time (1:03 / 3:31), the song and who made it, a progress bar you can click, and previous / pause / next. Its colours follow whoever you're talking to: purple and mint for Juno, blue and cyan for Jarvis, red and ember for Ultron. It's a quarter bigger than first planned, fits properly with Windows display scaling (the buttons were getting cut off). It works with Spotify, Apple Music, Media Player and most music apps, goes away 15 seconds after you pause, hides during fullscreen games, and you can drag it or close it. Settings > Appearance & animations to turn it off.
- **No more Jarvis blue while she listens.** Your words show in her mint green now, and the floating shards on the desktop use her colors.
- **Smoother: 30 fps everywhere.** Her desktop and music player animate at 30 frames a second all the time, not 10 while she's idle. Want it different? Tell her ("set your animations to 60 fps", "you're lagging my game, go lighter") or pick it in Settings > Appearance & animations. It changes live and is remembered.
- **Spotify stays out of your way.** Asking for a song no longer throws Spotify's window in your face; it plays in the background. Say "open Spotify and play..." if you want to see it.
- **She'll start conversations, your way.** Now and then, when you've been in something a while and paused, she says something about what you're doing (she only knows the app and window title, never your screen). Settings > Conversation & personality lets you pick how often (or a custom number of minutes), how long you have to be in something first, the most times a day, how long you have to pause, what she opens with (questions, tips, jokes, hype or whatever fits), topics you like, quiet hours, and things she should never bring up. These apply instantly, no restart.
- **She talks about your music.** When a new song starts she sometimes says something about it (at most every 30 minutes, never in a game or a call). Settings to turn it off.
- **More check-ins like the morning briefing,** with panels on her window and the desktop:
  - **Evening wrap-up** (from 8 PM, or the hour you pick): tomorrow's weather, what's on tomorrow, and where your time went today.
  - **Rain heads-up** when rain or snow is likely within the hour.
  - **Break reminders** after 2 hours at the PC without a real break (or 45 minutes to 3 hours, or off).
  - The **morning briefing** is still there the first time you start or wake the PC each day, and its weather and day cards now pop up on the desktop too.
- **Corner widget on or off, instantly.** Settings > General, or just say "turn off the corner widget". No restart.
- **Settings rebuilt.** A sidebar with its own page for each area: General, Conversation & personality, Voice & effects, Languages, Microphone, Appearance & animations, Window dimming, Application access and Connected apps, with a lot more you can change:
  - Her personality, humor, how much she says, and notes in your own words.
  - Voice effects (echo, ethereal, robot, glitch, radio, synth) and how strong they are.
  - The language she speaks and hears.
  - Which microphone she uses and how loud you have to be.
  - Desktop animation quality and where the visualizer goes.
  - Window dimming: fade her window when you're not using it, and bring it back brighter and more solid while she talks. (Windows can't make this kind of window see-through, so fading dims it instead.)
  - Apps she's never allowed to touch.

## 1.0.23
- **You can talk to Juno now.** Say "Juno, ..." or "switch to Juno", or press Juno at the top of his window. She has her own voice, her own personality and a purple theme. The secret code still merges them into her.
- **No more flashing.** The desktop thought Explorer had restarted every second and a half and redrew everything. Fixed, and that was also a big part of the CPU use.
- **Much lighter on your PC.** The heaviest effects are gone (Ultron's smoke and a lot of separate glows), the voice visualizers are drawn a cheaper way, and they slow to 10 frames a second while nobody's talking.
- **He starts minimized** (the corner widget shows him), so he never covers Juno's intro. Settings > Desktop to change it.
- Say "open", "summon", "launch", "pull up" and so on and whoever you're talking to plays the summon move, every time.
- The sword floating over Jarvis's shoulder is gone.
- A small voice visualizer now sits in the bottom-left corner of your main screen, and the little leftover window bar Windows was parking there is hidden while they're your desktop.

## 1.0.22
- **He watches your screen while you talk to him.** Ask "what's this error?", "what am I looking at?" or "read this" and he already sees it, so he answers in one go instead of stopping to take a picture first. Usually a second or more faster. After he clicks something he waits only until the screen settles, and if nothing changed he doesn't look twice. It stays in memory (never saved), only while you're talking to him, and never during fullscreen games. Settings > Desktop to turn it off.
- **Glass mode tracks your hands better.** Steadier (the whole hand is smoothed, not just the pointer, so no more jitter when you hold still), quicker when you move, pinches still count with your hand turned sideways, a blurry frame no longer drops the card you're holding, and two hands crossing over don't swap. It also asks your camera for 60 frames a second if it can do it.

## 1.0.21
- **They're your desktop now.** Jarvis, Juno and Ultron live on your wallpaper across both monitors, with the new look. Whoever you're talking to listens, thinks and talks with you, raises his sword (or tears the air open) when he opens something for you, and squares up when he needs your OK. The second monitor gets a visualizer that moves with his voice.
- **Juno takes the screen when he starts.** Her hands grab the edges, she opens her eyes, grins, and your old screen shatters into her world.
- Your desktop icons are hidden while he runs and come back the moment you close him. Everything else on your desktop is untouched.
- It stops drawing while a fullscreen game or video is in front, so it costs nothing while you play.
- Don't want it? Settings > Desktop: turn off the takeover, or just Juno's intro.

## 1.0.20
- **Rolled back.** 1.0.18 made a mess of him, so this puts Jarvis back exactly how he was in 1.0.17: the desktop characters, the Options panel, graphics card setup and the small local brain are gone for now. Everything you had before 1.0.18 works like it did.
- Anything you saved about Juno stays put. He no longer wipes it at start.

## 1.0.17
- **The little desktop companion is gone.** The secret code still works, but it does something new now. It'll make sense once Jarvis and Ultron can walk around your desktop.
- Every app he opens for you will get its own entrance animation once the desktop characters land (Ultron reaches out and tears it open, Jarvis throws a ring of light from his staff).

## 1.0.16
- **Someone new is hiding in here.** Old-school gamers know the code. Say it out loud, or type it.

## 1.0.15
- **Glass mode: things you can grab.** Say "open glass mode" (or press Glass mode in the System panel) and a window opens with your camera behind glass. Ask him to show you something ("show me the top 5 budget mics", "put my week up", "show me a screenshot") and it floats in as glass cards you handle with your hands:
  - pinch a card and move to drag it, let go mid-swing to throw it (off the screen closes it)
  - a quick pinch brings it up close, another sends it back
  - pinch one card with both hands and pull apart to make it bigger (twist to tilt it)
  - make a fist over a card and hold it to crumple it
  - sweep an open hand fast across the screen to clear everything
  The mouse works too. He knows what's on the glass and which card you're holding, so "what's this one?" works. Your camera picture never leaves your PC: the hand tracking runs inside that window. The first time, allow the camera when it asks.

- **New faces.** Pick how he looks in the System panel under Face, or say "Jarvis, change your face" (or "switch to the ferro face"). Both of them change together, each in their own colors:
  - **Scope:** an oscilloscope. A slow figure at rest, a flat line your voice shakes while he listens, shapes sweeping while he thinks, and a trace that swells as he talks. Ultron's signal is squarer and breaks up.
  - **Lattice:** a wireframe geodesic sphere. It pushes out when he talks, light runs along its edges while he thinks, and it pulls in to listen. Ultron's grows spikes.
  - **Contour:** a topographic map of a mountain. His voice raises the peaks, thinking turns the land, and ripples run down the slopes when you talk. Ultron's is broken, jagged ground.
  - **Ferro:** a drop of ferrofluid on a magnet. It wobbles at rest and bristles into spikes in time with his voice. Ultron's spikes are longer and meaner.
  - **Classic** is the one you know, and it's still the default.

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
