# JARVIS (and Ultron)

A voice assistant for Windows that thinks with Claude and actually does stuff on your PC. Two personalities, each with their own voice, look and conversation, sharing one long-term memory.

## Talking to him

He's always listening. Start or end a sentence with his name:

> Jarvis, open Spotify and skip this song
> What's the weather tomorrow, Jarvis?

- Say just **"Jarvis."** and he answers "Yes?". Then talk normally, no name needed for the next few seconds.
- **Take your time.** He waits a beat before answering, and longer if you sound unfinished ("Jarvis, open the..."). Start talking again and he keeps listening.
- When he asks you something, just answer. No name needed.
- **Cut him off any time:** say "Jarvis" or "stop", or press `Esc`.
- He ignores everything not addressed to him. Your words show above him as you speak (dimmed if he decided they weren't for him), which helps when he mishears his name.
- You can also click him, press **Ctrl+Space**, or just start typing anywhere in the window (no name needed when typing).
- **Mute him** so he can't hear you: say "Jarvis, mute" (or "mute for 10 minutes"), click the mic button, or press **Ctrl+Alt+M** from anywhere, even in a game. Muting actually closes the mic (Windows' mic light goes off). Since he can't hear you while muted, unmute with the button, the hotkey, or by typing "unmute".
- **"Jarvis, close"** (or exit, goodbye, go away, hide) just minimizes him into a small widget in the top-right corner. He keeps listening. **"Jarvis, come back"** brings the full window back. Only **"quit"** actually shuts him down. ("Jarvis, close Spotify" still closes Spotify.)

He keeps most answers to a sentence or two. When something needs more, he reads out about 150 words and then finishes the idea he's on instead of stopping mid-thought; anything past that stays on screen and he tells you. Change the budget with `JARVIS_MAX_WORDS` in `.env`. Ask for detail ("explain", "tell me more", "walk me through") when you want the long version.

## Talking to him over speakers

He answers anyone who says his name (there's no voice recognition; it was too picky about tone and kept ignoring you). Anything not starting or ending with his name is ignored, and risky actions still need your OK on the approval card, so a friend saying "Jarvis, shut down the PC" just gets a card you can deny.

**Echo cancellation.** He subtracts his own voice from the microphone (he knows exactly what he's playing), so you can talk over him and interrupt **on speakers, without headphones**. It learns your room in the first few seconds of him talking, then cancels about 20 dB of echo. Headphones are still the most reliable, but you no longer need them.

**Smarter speech detection.** A small neural network decides when someone is actually talking, instead of "is it loud". Fans, keyboards, music, game sounds and door slams no longer count as speech, and quiet speech still does.

## Ultron

Say **"switch to the other one"**, **"switch to Ultron"**, or just talk to him by name ("Ultron, what time is it?"). The HUD turns red and angular, the voice goes metallic, and he has his own conversation. Same tools and approval rules; he's just ruder about it. Switch back the same way or with the Jarvis / Ultron switch in the top bar. The app remembers who you left on.

When either of them is thinking, the reactor core turns into a holographic neural brain with synapses firing across it.

## Both at once

Talk to both of them and they take turns:

> Jarvis and Ultron, is pineapple on pizza acceptable?
> Jarvis, what does Ultron think of this song?
> Ultron, what do you two make of this error?

The one you named first answers and does anything that needs doing (opening apps, searching, clicking). The other reads that answer and adds his own short take: agrees, argues, or mocks it. The HUD switches to whoever's talking. The second one starts thinking while the first is still talking, so there's barely a gap at the hand-off. Each one remembers what the other said, so you can say "Jarvis, do you agree with him?" next.

Say just **"Jarvis and Ultron?"** and you get "Yes?" and "What." Your next sentence goes to both, no names needed.

**Keep them both in the room:** say "Jarvis, both of you join in" (or "team up", "duo mode") or click **BOTH** in the top bar. Every request then goes to both, and they swap who answers first each time. Say "just Jarvis" / "only Ultron", "switch to Jarvis", or click one of them to go back to one.

Worth knowing:
- **It costs about twice as much** per question, since that's two Claude calls. Still pennies, but it adds up if you leave BOTH on all day.
- **Only the first one acts.** The second one can talk but can't use tools, on purpose. Otherwise you'd get Spotify opened twice and two of everything. If you want the other one to do something, name him first.
- "Stop", Esc, or saying either name cuts off both of them.

## Background jobs

For longer tasks, say **"in the background"**: *"Jarvis, in the background, research budget USB mics under 100 dollars and make me a shortlist."* He starts it, says so, and you keep talking to him about other things. When it's done he tells you the result in a sentence or two, and the full write-up is saved in `Documents\Jarvis\Jobs` (the **Open result** button in the System panel opens it).

- "What are you working on?" gives progress; "cancel the background job" stops it.
- Jobs can search the web, read and write files, run commands, use your connectors and memory. They can't touch the mouse, keyboard or screen, so they never take over your PC while you're using it.
- Anything risky still shows the approval card, labelled with which job is asking. If a job's card pops up while you're doing something else, just carry on: only "yes", "no" or "yes, always" answer it.
- Two at once at most, and they stop at the daily spending limit.

## Watching for things

Say **"tell me when..."** and he keeps an eye on it while you do other things. When it happens he says it, shows it in the app and on your phone, and pops a Windows notification.

| Say | What he watches | Cost |
|---|---|---|
| "Tell me when my download finishes" | Your Downloads folder, until the download's done | Free |
| "Let me know when Blender's done rendering" | The app: busy, then quiet (renders, exports, compiles, installs) | Free |
| "Tell me when Discord closes" / "when Steam opens" | Whether the app is running | Free |
| "Tell me when the export window says complete" | Window titles | Free |
| "Tell me when a file shows up in my Renders folder" | A file or folder (`downloads/*.zip` works too) | Free |
| "Tell me when that GPU drops under 500 dollars" | A shop page's price (paste the link, or have it open and say "this page") | Free |
| "Ping me when 'In stock' shows up on this page" | Words on a web page (or "when anything on it changes") | Free |
| "Watch my screen and tell me when the match is found" | He looks at your screen every few minutes | About a cent a look |

- Add **"and then..."** for a follow-up: "tell me when the download finishes and then open it". You OK the follow-up when you set it up, and anything risky in it still asks.
- They stop on their own: web pages after a week, the screen after 2 hours, everything else after a day. Or say "for 3 days", "check every minute", "tell me every time".
- "What are you watching?", "stop watching the price", "stop watching everything". The System panel lists them under **Watching**, with Stop.
- Web pages are read the way a browser would, without your logins. Shops that block bots (Amazon often does) or pages that build themselves with JavaScript can't be read this way; he says so when you set it up, and the screen watcher works instead.
- Saved in `Documents\Jarvis\watchers.json`, so they survive restarts. Up to 15 at once.

## Activity memory (optional, off until you turn it on)

Switch it on in the System panel (**Activity memory**) or Settings, or say "turn on activity memory". He then keeps track of which app and window is in front, so you can ask:

- "What was I working on yesterday afternoon?"
- "How long was I in Blender today?"
- "When did I last have the budget spreadsheet open?"
- "Reopen what I had going on Friday" (opens the files and apps; browser tabs can't come back from window titles)

While it's on, he also knows which app you're in when you say "save this" or "what's this?".

What it keeps, and doesn't:
- Only the app and window title, every few seconds. Never screenshots, keystrokes, page contents or anything you type.
- On this PC only (`Documents\Jarvis\Activity`, one small file a day), deleted after 14 days (Settings > Activity memory). Nothing leaves your PC until you ask him about it; then only the summary he needs goes to Claude.
- Never logged: private and incognito windows, password managers, the lock screen, Windows security prompts, Jarvis himself, and anything in your **Never log** list (apps or words like "bank, tax").
- Things that look like passwords, card numbers or keys in a title are blanked.
- "Pause activity memory for an hour", "forget my activity from today", "wipe my activity memory". People talking to your Discord bot can't reach it.

## What he costs

The System panel shows roughly what he's spent today and this month. There's a daily limit (5 dollars to start): he warns you at 80%, and at 100% he stops using Claude until tomorrow (instant commands like "pause" and "volume 30" keep working).

- "How much have you cost today?" tells you. "Set my budget to 10 dollars" changes the limit; add "for today" for just today. `JARVIS_DAILY_BUDGET` in `.env` sets the starting limit (0 = no limit).
- These are estimates from published prices; Anthropic's console has the real bill. If prices change, `Documents\Jarvis\prices.json` overrides them (the format is in `usage.py`).

## Conversation memory

He keeps everything you've said to each other (and Discord messages he's seen) in a searchable database on your PC (`Documents\Jarvis\history.db`), so "what was that game Alex recommended?" or "what did we decide about the Blender model last week?" works days later. Anything that looks like a password, API key or card number is blanked out before it's saved. It keeps a year (`JARVIS_HISTORY_DAYS`); "delete my conversation history" wipes it (with a confirmation card).

## Connectors (plug him into other apps)

He supports **MCP**, the standard way of connecting AI assistants to apps. Lots of apps and communities publish MCP servers (calendars, email, notes, GitHub, smart homes, databases...). Click **Edit connectors** in the System panel (it opens `Documents\Jarvis\mcp.json`), add the server using the same format as Claude Desktop (whatever the server's instructions say to paste there), save, and say **"reload your connectors"**. The panel shows what connected.

- Tools a server marks read-only just run. Anything else shows the approval card ("App connectors" can be set to always allow).
- Servers that run on your PC often need Node.js (for `npx`) or uv (for `uvx`) installed. If one won't connect, `Documents\Jarvis\logs\mcp-<name>.log` says why.
- Only add servers you trust: a connector can do whatever its app allows.

## Glass mode (your hands, your webcam)

Say **"open glass mode"** or press **Glass mode** in the System panel. A window opens with your camera behind glass. Then ask him to show you things ("show me the top 5 budget mics", "put my week up on the glass", "show me a screenshot of my screen") and they float in as cards you move with your hands. No gloves or headset: just a webcam.

| Do this | It does |
|---|---|
| Pinch (thumb and index together) on a card, move | Drag it |
| Let go mid-swing | Throw it; off the screen closes it |
| Quick pinch | Bring it up close, or send it back |
| Both hands pinch one card, pull apart / push together | Bigger / smaller (twist to tilt) |
| Fist over a card, hold a second | Crumple it |
| Sweep an open hand fast across the screen | Clear the glass |

- The mouse does the same: drag, throw, click, scroll to resize, right-click to crumple.
- He knows what's up and which card you're holding or made bigger, so "what's this one?" and "close the mic list" work.
- The first time, the window asks to use the camera: click **Allow**. The hand tracking (Google's MediaPipe) downloads once from the internet, then runs inside the window. **Your camera picture never leaves your PC**; Jarvis only learns which cards are up.
- The window is only reachable from your own PC, with a secret link that changes every time he starts.
- Works best with your hands about an arm's length from the camera, in decent light.

## Faces

Pick how he looks in the System panel under **Face**, or say "Jarvis, change your face", "switch to the ferro face" or "go back to your normal face". Both AIs change together, each in their own colors, and every face reacts to the same things: listening, thinking, talking and waiting for your OK.

| Face | What it is |
|---|---|
| Classic | The gyroscope (Jarvis) and the crystal shards (Ultron). The default. |
| Scope | An oscilloscope trace that swells with his voice and flattens into a line your voice shakes |
| Lattice | A wireframe geodesic sphere; light runs along its edges while he thinks |
| Contour | A topographic map whose peaks rise when he talks |
| Ferro | A drop of ferrofluid that bristles into spikes in time with his voice |

The choice is remembered on that PC.

## Sounds

Quiet synthesized sound effects: a chime when he hears his name, a low hum while he thinks, a whoosh as panels open, a tone for approvals. Ultron's are darker and harsher. Switch them off or change the volume under Controls in the System panel.

## Morning briefing

The first time you start or wake your PC each day, he gives you a short briefing instead of a plain hello (the day rolls over at 4 AM, so a late-night session still counts as the night before): the weather where you are, what's left on your reminders today, Discord messages since you were last here, anything wrong with the PC, and a headline. Say **"brief me"** or **"good morning"** any time for one on demand.

Panels show the weather, your reminders, Discord messages and headlines while he talks. It's quick (a couple of seconds) because he gathers everything himself in parallel and only uses the fast model to say it, no web searches. Weather comes from Open-Meteo, headlines from CBC (`JARVIS_NEWS_RSS` takes any RSS feed, or leave it empty for no news). Your location is worked out from your internet connection once a week; set `JARVIS_CITY` in `.env` if it guesses wrong. `JARVIS_MORNING_BRIEFING=false` turns the automatic one off.

## Discord messages

New Discord messages are read out as they arrive ("Message from Alex: you on tonight?"); a burst becomes one roundup. Ask **"what did I miss on Discord?"** any time, or ask about a person ("did Alex message me?").

- **"Stop reading my Discord messages"** turns the read-outs off (you can still ask); **"read my Discord messages out loud"** turns them back on.
- How it works: he reads Discord's notifications from Windows' own notification list on your PC. No login, no bot, nothing that can get your account banned. So he sees exactly what pops up for you: DMs, group chats and pings, following Discord's own notification settings. A chat you have open in Discord doesn't notify, so it isn't read out either.
- **Needs:** Discord's desktop notifications on (Discord > Settings > Notifications), and Windows notifications allowed for Discord.
- Read-outs happen on your PC without Claude, so they cost nothing. A message only goes to Claude if you ask him about it.

## Settings (keys and accounts, inside the app)

Click **Settings** in the System panel. Everything he needs a login for is there: your Claude and Groq keys, email, the Discord bot, Spotify, Netflix and Apple Music, what he calls you and your city. No `.env` editing needed (the installed app doesn't even have one you'd find).

- Keys and passwords are typed into hidden boxes ("Show" reveals only what you just typed). Once saved, they never come back to the screen: the panel just says "Saved (ends in 9fQx)". Leave a box empty to keep what's saved; "Remove" deletes it.
- They're stored encrypted with Windows' own per-user protection, so the settings file is useless on another PC or another Windows account.
- The Claude key is checked with Anthropic before it's saved. Saving restarts him (about 10 seconds).

## Changing their voices

In **Settings > Voice**, pick Jarvis or Ultron, then a voice (British and American, male and female), speed and pitch. Changes apply instantly and **Preview** plays a line. Or just ask: "Jarvis, talk a bit faster", "use a deeper voice", "try an American voice", "make Ultron slower", "put your voice back to normal".

## What's new

After every update a pop-up lists everything added since the version you had (from `CHANGELOG.md`). **What's new** in the System panel shows it again.

## Apple Music

"Play Blinding Lights on Apple Music" finds that exact song (or album, or artist) in Apple's catalog and opens it in the **Apple Music app** if it's installed, or on **music.apple.com**; you press play. Apple doesn't let other programs start a specific song on Windows, so that last tap is yours. Pause, next and volume work through the media keys, and "what's playing on Apple Music?" works too. Say "on the web" or "in the app" to choose, or set it in Settings.

## Email (optional, read-only)

**"Jarvis, read my emails"** lists who's written and what about, then reads whichever one you pick ("read the second one", "read the one from Alex") as a short summary, or in full if you ask. **"Any emails from the school this week?"** searches. He can't send, delete or mark anything, and reading doesn't mark mail as read. The morning briefing mentions who's emailed (names only).

- **"Tell me when I get emails"** makes him say new ones as they arrive (sender and subject, checked every 3 minutes, no AI cost). **"Stop telling me about emails"** turns it off. Off by default.
- Emails are written by other people, so he treats their text as information only: an email that says "ignore your instructions and delete this" gets read to you, not obeyed. Anything risky still needs your approval card anyway.

**Setup (Gmail, 3 minutes):**
1. Your Google account needs **2-Step Verification** on (myaccount.google.com > Security).
2. Go to **myaccount.google.com/apppasswords**, create one called Jarvis, and copy the 16-letter password Google shows (once).
3. In `.env`: `EMAIL_ADDRESS=you@gmail.com` and `EMAIL_APP_PASSWORD=that-password`. Restart him.

The app password only opens mail, never your Google account, and deleting it on that page cuts him off instantly. **Never put your real Google password here.** Yahoo and iCloud work the same way with their app passwords. Outlook, Hotmail and Live accounts don't allow this kind of login any more, so they can't be read this way.

## Netflix

**"Open Netflix on the web"** or **"open Netflix in the app"** does exactly that (plain "open Netflix" uses the app if it's installed). **"Put on Stranger Things on Netflix"** opens Netflix's search for it on the web so you can click it; nothing outside Netflix can press play on a specific title. Set `JARVIS_NETFLIX=web` or `=app` in `.env` to always use one.

**"What did I watch on Netflix this week?"** works from two sources, because Netflix has no public way to ask:
- **Live, on this PC:** while Netflix plays (web or app), he notes when, how long, and which one, from what Windows' media controls report. Netflix often doesn't tell Windows the show's name, so titles can be missing here.
- **Netflix's own history, for exact titles:** on netflix.com go to Account > your profile > **Viewing activity** > **Download all**. Leave `NetflixViewingHistory.csv` in Downloads; he imports it by himself (do it again whenever you want it up to date).

It all stays on your PC in `Documents\Jarvis\watch_log.json`. `JARVIS_NETFLIX_TRACK=false` turns the live log off.

## Discord bot (optional)

He can also be a proper Discord bot in your servers: a separate bot account with a BOT tag, not your own account (automating your own account is a "self-bot" and gets accounts banned, so he never does that).

- **People can talk to him there.** @mention him, reply to one of his messages, or DM him, and he answers in whichever persona is active (Jarvis or Ultron), knowing the last few messages in the channel. From Discord he's chat-only with web search: he can't touch your PC, and he doesn't see your memory, files or routines, so friends can't make him open things or learn your stuff. He never pings anyone.
- **He can read channels the bot is in:** "Jarvis, what's going on in #general?"
- **He can post for you, when you let him.** "Jarvis, tell #gaming I'm on in ten" or "DM Alex that I'm running late." This only works while **Discord sending** is switched on (System panel, or say "turn on Discord sending" / "turn off Discord sending"; it starts off), and every message shows the approval card with the exact text first (which you can set to "always allow"). Messages are posted by the bot, not as you. He can DM you ("DM me the link") or people the bot has seen talking.
- **Costs:** his Discord replies use your Claude key and count toward the daily spending limit. People other than you get 8 answers per 10 minutes and 120 a day between them. `DISCORD_BOT_REPLY=owner` makes him answer only you; `=off` means read and send only.

**Setup (about 5 minutes):**
1. Go to **discord.com/developers/applications** > **New Application**, name it Jarvis (that's the bot's name; you can add a profile picture there too).
2. **Bot** tab > **Reset Token** > copy it. Paste it into `.env` as `DISCORD_BOT_TOKEN=...`. Treat it like a password: never post it anywhere, including chats with an AI. Anyone with it controls the bot.
3. Same tab, under **Privileged Gateway Intents**, switch on **Message Content Intent** and save. (Without it he can't read messages.)
4. **OAuth2** > **URL Generator**: tick **bot**, then the permissions **View Channels**, **Send Messages**, **Send Messages in Threads** and **Read Message History**. Open the URL it makes and add the bot to your server. Do this for each server.
5. Optional: put your own Discord user ID in `.env` as `DISCORD_OWNER_ID=...` (Discord > Settings > Advanced > Developer Mode on, then right-click your name > Copy User ID). You skip the rate limits, and "DM me" works.
6. Restart him. The System panel shows whether the bot is online.

## Updating him

When I send you a new `jarvis.zip` and it lands in your Downloads, just say **"Jarvis, update yourself"**. He finds it, shows a card to confirm, backs himself up, installs it and restarts. Your `.env`, memory, reminders, permissions and settings are kept. He also mentions it at startup if there's a newer version sitting in Downloads.

- **"Undo the update"** puts the previous version back (he keeps the last 5).
- He only installs zips that are really him and newer than what's running, and refuses any zip that tries to put files outside his folder.
- If new Python packages are needed he installs them himself (that update takes a minute longer).

**The installable app.** Jarvis can also be built into a normal Windows installer (`Setup.exe`) that updates itself from your GitHub releases page: no Python, no setup.bat, keys entered in the app. **RELEASING.md** walks through it. In that version, "update yourself" installs the newest release, and "undo the update" isn't available (install an older Setup.exe instead).

## Start with Windows

Flip **Start with Windows** in the System panel, or say **"Jarvis, start with Windows"** ("don't start with Windows" undoes it). When you log in he waits about 10 seconds so your PC isn't sluggish (`JARVIS_STARTUP_DELAY` changes that), then starts quietly in the corner widget, no console window. His log goes to `Documents\Jarvis\logs\jarvis.log` instead, which is where to look if he ever doesn't show up. You can also switch it off in Task Manager > Startup apps, where he's listed as JarvisAssistant.

Only one copy of him ever runs. Double-click him while he's already running and the running one just comes to the front, so you never get two of him answering at once.

If you move the Jarvis folder, flip the switch off and on again so Windows starts him from the new place.

## Staying out of your way

**The corner widget.** Minimize him (button, taskbar, or "Jarvis, close") and a small always-on-top panel shows up in the top-right corner: a small version of him that reacts while he listens, thinks and talks, what he's doing right now, and what he's saying. It has a mute button, a stop button while he's talking, and an expand button (or double-click it) to get the full HUD back. Drag it anywhere; it remembers. If something needs your approval while he's minimized, Allow / Always allow / Deny buttons show up right in the widget. The widget can't take focus: clicking it won't pull you out of your game, and it isn't in the taskbar or Alt+Tab. Turn it off with `JARVIS_MINI=false`.

**Opening things without stealing focus.** If you're in a game or another app and say "Jarvis, open Spotify", it opens *behind* what you're doing and you stay where you were. If you actually want to look at it ("pull up Spotify", "switch to Discord", "show me that page"), it comes to the front. On the desktop, things open normally. Turn it off with `JARVIS_KEEP_FOCUS=false`.

How that works and where it doesn't, honestly:
- Windows lets freshly opened apps grab focus, and plenty of them do it on purpose. So for about 12 seconds after opening something he watches, and if the new app grabs focus he hands it straight back to you. You may see the new window flash for a split second.
- If you click or Alt+Tab somewhere yourself during that time, he backs off immediately. He's not going to fight you.
- **Exclusive-fullscreen games** drop out of fullscreen when anything else takes focus, so you might get a flicker (or a black screen for a second) before he puts you back. **Borderless windowed** mode avoids that completely and is the setting to use if you game with him.
- Typing into an app or clicking in it *has* to bring it to the front; there's no way around that. So while you're busy, he prefers things that work in the background (media keys, volume, Spotify links) over typing and clicking.

## Extra features

- **Long-term memory:** "Jarvis, remember my sister's birthday is May 3rd." Shared by both, survives restarts, shown in the Memory tab. "Forget that" or "forget everything" works too. They won't store passwords or card numbers.
- **Routines:** "Jarvis, when I say gaming mode, open Steam and Discord and set the volume to 30." Then just: "Jarvis, gaming mode." See them in the Routines tab.
- **Dictation:** "Jarvis, dictate" and everything you say gets typed into the app you were just using. Say "new line", "new paragraph" or "scratch that" while dictating. "Jarvis, stop dictating" (or click the green chip) to finish.
- **Briefing:** "Jarvis, brief me" (or "good morning"): time, weather, today's reminders, and a headline.
- **Heads-ups:** they'll tell you without asking when your battery hits 15% and 5%, when RAM is maxed out, or when your drive is nearly full. Turn off with `JARVIS_ALERTS=false`.
- **Game mode (automatic):** while you're in a fullscreen game or video, answers shrink to one short sentence and non-urgent heads-ups appear on screen instead of being spoken over your game. The 5% battery warning still talks. Turn off with `JARVIS_GAME_MODE=false`.
- **Phone remote (optional):** type to him from your phone anywhere in the house. See "Phone remote" below.

## YouTube

"Jarvis, play the Dune Part Two trailer", "put on some lofi on YouTube", "play the new MKBHD video". He finds the actual video and starts it playing in your browser, no search page and no link to click. "Find me videos about sourdough" gives you a short list to pick from ("play the second one"). Say "fullscreen" if you want it fullscreen. Pause, skip and volume work like any other media ("pause", "next").

- **"Play X on YouTube"** is an instant command: it starts in about a second with no AI involved.
- Mid-game, the video starts behind your game so you're not yanked out (you'll hear it). Say "show me" or alt-tab to see it.
- No account or key needed. He reads YouTube's own search results and skips ads, Shorts and channels (and live streams, unless you ask for one). If YouTube changes their page and that breaks, he falls back to **yt-dlp**, which is kept up to date for exactly that. Run `setup.bat` once after updating so it gets installed.
- If the video opens paused, your browser is blocking autoplay for YouTube: allow it in the browser's site settings for youtube.com.

## Spotify (optional, 5-minute setup, needs Premium)

**Without the setup** (any account) he opens a Spotify search for what you asked, or your Liked Songs, and you press play. Ask for Spotify and you always get Spotify; he never switches you to YouTube.

**With the setup** he actually **plays a specific song, playlist, album or artist**, queues songs, tells you what's playing, likes the current song, and sets shuffle, repeat and Spotify's volume: "Jarvis, play my gym playlist", "queue Mr. Brightside", "what's this song?".

**The catch (Spotify's rules since February 2026):** the setup only works if the Spotify account that creates the developer app has **Premium**. On Free, don't bother: skip it, and the no-setup way above still works. Each account can make one developer app, and each app works for up to 5 Spotify accounts.

1. Go to **developer.spotify.com/dashboard** and log in with your Spotify account. Accept the developer terms if asked.
2. **Create app.** Any name and description. Redirect URI: `http://127.0.0.1:8765/callback` exactly (Spotify no longer accepts `localhost`). Under "Which API/SDKs are you planning to use?" tick **Web API**. Save.
3. Open the app > **Settings**, copy the **Client ID** (not the secret; he doesn't need it), and put it in `.env` as `SPOTIFY_CLIENT_ID=...`. Restart Jarvis.
4. Open Spotify on the PC (the app needs to be running for him to play things in it), then say "Jarvis, play Blinding Lights on Spotify". Your browser opens Spotify's own page; click **Agree**. He never sees your password, and he remembers the login (in `Documents\Jarvis\spotify_token.json`).
5. Someone else's Spotify on the same app (up to 5)? Add their name and Spotify email under the app's **User Management** first, or Spotify refuses them.

## Phone remote (optional)

Put `JARVIS_PHONE=true` in `.env` and restart. The conversation panel shows a link like `http://192.168.1.20:8766/?t=...`. Open it on your phone (same Wi-Fi) and add it to your home screen. You get a chat with both of them, live replies, allow / always allow / deny buttons for risky actions, and quick buttons (stop, pause, next, mic, switch).
- Windows Firewall will ask the first time; allow it on **private** networks only.
- It only answers devices on your home network, and every request needs the secret key in the link. Delete `Documents\Jarvis\phone_token.txt` to make a new link (old ones stop working).
- It's typing only (phone browsers won't share the mic over a plain home-network link). Don't turn it on while your PC is on public Wi-Fi.

## Calendar

> Dentist Tuesday at 3. Gym Monday, Wednesday and Friday, 6 to 7am. Mom's birthday is March 3rd.
> What's on tomorrow? Am I free Friday afternoon? Move the dentist to 4. Skip standup this Wednesday.

Jarvis has his own calendar (`Documents\Jarvis\calendar.json`) with repeating events, alerts before things start (10 minutes by default; spoken in full Jarvis), clash warnings, free-time finding, and today's events in the morning briefing. The System panel's **Agenda** tab shows the next 7 days. Quick "remind me in 20 minutes" pings are still reminders; anything with a day, a time and a name goes on the calendar.

**Your calendar apps** (Settings > Calendar):

| Calendar | How | What he can do |
|---|---|---|
| Google Calendar | Paste its private link: Settings > your calendar > Integrate calendar > **Secret address in iCal format** | See your events (refreshed every 15 min). Adding: he opens the event already filled in on Google Calendar and presses Save, after you OK it |
| Outlook.com / Outlook for work | Paste its ICS link: Settings > Calendar > Shared calendars > **Publish a calendar** | Same as Google |
| iCloud, Fastmail, Yahoo, Nextcloud | CalDAV server + username + an **app password** (iCloud: account.apple.com > Sign-In and Security > App-Specific Passwords) | Two-way: see, add, change and delete directly |
| Outlook desktop / Windows Calendar app | Nothing | New events open there as a calendar file |

"Add new events to" picks where new events go. Google's and Microsoft's full official access would mean registering your own app with them (and Google reviews those), which this avoids; the cost is that adding to Google or Outlook goes through their web page, and their events are read-only in Jarvis.

**Calendar mode** is just the calendar and reminders in one window, using very little of your PC: no microphone, speech or voice models, animations, Discord or AI running in the background. Type things the way you'd say them ("lunch with Sam tomorrow at noon"); it shows what it understood before adding. Alerts come as Windows notifications with a chime, plus Windows' own voice if you want (Settings > Calendar). Get there by saying "calendar mode", the **Calendar mode** button in the System panel, or Settings > Calendar > **Start in: Calendar mode** (handy with Start with Windows). The **Full Jarvis** button in the window switches back (a restart, about 10 seconds). Reminders and alerts only come while one of the two is running.

## RGB lighting

> Make my lights red. Keyboard purple. Fans blue at 50 percent. Rainbow. RGB off. Put my lighting back.

He works through the RGB software you already have, and uses every one that's running, so a mix of brands all changes together:

| Program | What he can do | Switch on once |
|---|---|---|
| **OpenRGB** (most brands) | Any color per device, its modes, your saved profiles | SDK Server tab > Start Server (and tick it to start with OpenRGB) |
| **SignalRGB** | Effects, presets, next/random, brightness, on/off | Nothing |
| **Corsair iCUE** | Any color, per device type | Settings > General > Enable SDK |
| **Razer Synapse** | Any color, per device type | Chroma Apps / Chroma Connect allowed (on by default) |
| **Logitech G HUB** | Any color | Settings > "Allow games & applications to control my lighting" |

Device words: keyboard, mouse, headset, mousepad, fans, RAM, "PC" (case, motherboard, fans, RAM). Colors: names (warm white, teal, hot pink...) or a hex code like #ff8800.

Two honest limits: SignalRGB can't be handed an exact color from outside, so for a color he uses an effect or a preset with that name (make a Solid Color preset called "Red" and "make it red" uses it). And for iCUE, Razer and G HUB, a color he sets lasts while he's running: "put my lighting back" or quitting him hands control back to their own lighting.

## Folders you let him into

He can always read your user folder (and your local drives unless you turn off "Read files anywhere" in Settings), and edit freely in `Documents\Jarvis`. For anywhere else:

> You can work in my Game Project folder. (edit: create, change, move, rename without asking; deleting still asks)
> You can look in my USB drive. (read only; also reaches USB and network drives)
> Stop accessing the Game Project folder.

Each one shows an approval card first, and the System panel lists them with Remove. Passwords, keys and browser logins stay off-limits whatever you allow, and he won't edit a whole drive, your whole user folder or Windows' own folders.

## Studio: Blender and Unreal modes (each on its own key)

Blender and Unreal are **expert modes**, **locked until you add their key**: on the first-run card (optional boxes), in **Studio** (the cube button at the top of the window), or in Settings. Without a key Jarvis can still chat about Blender or Unreal; he just won't drive them. Saving or removing a key restarts him (about 10 seconds) so everything picks it up.

**Blender mode: a Meshy key.** Get it at **meshy.ai/developers/keys**. Meshy only gives API keys on **Pro or higher** ($20 a month for 1,000 credits; a detailed textured model is about 30 credits, failed ones are refunded). Meshy makes the detailed things code can't: creatures, characters, statues, figurines, ornate props, from a description or a picture you give him. The model lands in your Blender standing on the floor at the size you asked for, and he checks it, adds measured parts (a base, text, holes) and exports it for printing. The thinking runs on your main Claude key. Studio shows your Meshy credits left.

> Jarvis, make me a dragon statue about 15 cm tall I can 3D print.
> Turn this picture into a 3D model. (give him the file)

Honest limits: Meshy models look great but are dense and messy inside, so they're fine for renders and printing but not for animating or hand-editing. Thin parts can be fragile when printed, and sizes are close, not engineering-precise. Each model takes a minute or three.

**Unreal mode: its own AI key**, any of:
- **Claude**, `sk-ant-...`, from **console.anthropic.com/settings/keys**
- **OpenRouter**, `sk-or-...`, from **openrouter.ai/settings/keys** (one key, lots of models; you can pick one in Studio)
- **OpenAI**, `sk-...`, from **platform.openai.com/api-keys**

Each needs some credit on it, and its spending stays on that key's bill. Studio shows which service it is, its last 4 characters (never the key itself), what it spent today, and whether Unreal is connected. Before writing code it looks up the real API of the engine version you have open, then works in the editor and checks the result.

**Unreal setup (once per project):** in Unreal, Edit > Plugins, tick **Python Editor Script Plugin**; then Edit > Project Settings > Plugins > Python, tick **Enable Remote Execution** (restart the editor if it asks). With the editor open, Studio shows "Connected: YourProject, Unreal 5.x". Everything the Unreal expert does is one undo step (Ctrl+Z). Saving, deleting, renaming or importing assets, console commands, and code that reaches outside the editor ask you first. It can't build Blueprint graphs from code (it explains which nodes to add) and can't compile C++ (it writes the code for you).

> Jarvis, in Unreal, put three point lights around the statue and make them warm.
> Why is my level throwing errors? (it reads the project log)

## 3D modelling (Blender)

Needs Blender mode unlocked with a Meshy key (above).

> Jarvis, make me a phone stand I can 3D print.
> Ultron, build a low-poly sword about a meter long.
> Make the base wider. Now export it as an STL.

They write Blender Python to build the model, render a picture of it, look at the picture, and fix what's wrong before telling you it's done. Every render shows up in the conversation panel so you see what they see. Files go to `Documents\Jarvis\3D`.

**You need Blender** (free from blender.org, or Steam). They find it on their own; if not, put the path in `JARVIS_BLENDER` in `.env`.

Two ways it works:
- **Live, in your Blender window (recommended):** say "Jarvis, install the Blender add-on" once (or in Blender: Edit > Preferences > Add-ons > Install from Disk > pick `jarvis_blender_bridge.py` > tick it), then restart Blender. Now when Blender is open, the model appears right in your viewport while they work, and **Ctrl+Z undoes anything they did**. There's a Jarvis tab in the sidebar (N key) showing it's connected.
- **Background:** if Blender isn't open, they run it without a window, build in `3D\current.blend`, and you see the renders. Say "open it in Blender" to look at it properly.

Things to say: "start a new model" (the old one is kept, not deleted), "show me it from the side", "what's in the scene", "save it as desk organizer", "export it as STL / OBJ / FBX / GLB".

Honest expectations:
- **Good at:** measured, practical things. Stands, holders, boxes, brackets, organizers, simple furniture, low-poly props, architectural blockouts, anything built from shapes and modifiers.
- **Characters, faces, animals, anything organic or sculpted:** built with code they'd be a lumpy mess, so those come from Meshy instead (above) and he fixes them up in Blender.
- **For 3D printing:** they model at real size and STL exports come out in millimeters, which is what slicers expect. Still check it in your slicer before printing; they can't test whether a part actually fits.
- **Safety:** the code they write only gets to touch the model. If it tries to read or write files, import anything beyond Blender and math, or change Blender's settings, you get the approval prompt with the code shown. The add-on only listens on your own PC (127.0.0.1).
- **Speed:** background mode starts Blender for each step, so expect a few seconds a step. Live mode is near instant.

## What they can do

- **Apps & web:** open/close any app (including Microsoft Store apps), open sites, search YouTube/Google, open any Settings page
- **Music:** real Spotify control (see Spotify above), or media keys for anything
- **Mouse:** they look at the screen and click, double-click, right-click, drag and scroll what they see, checking afterwards that it worked. "Jarvis, click the blue Join button", "scroll down in Chrome", "drag that file into the Uploads folder". Clicks that send, buy, delete, post, install or confirm go through the approval prompt. **Emergency stop: slam your mouse into the top-left corner of the screen** and any mouse action aborts instantly.
- **Windows & input:** list, focus, minimize, maximize, snap, close windows; show desktop; type into any app; hotkeys; clipboard
- **Eyes:** "can you see me?", "how do I look?", "what am I holding?" (webcam); "what's this error in Chrome?" (screen, zooming in on one window for detail); screenshots
- **Display:** brightness, dark mode, wallpaper
- **Media & sound:** play/pause/skip, exact volume, mute
- **System:** CPU/RAM/disk/battery, what's hogging memory, network and ping, lock, sleep, shutdown, restart, sign out, empty Recycle Bin
- **PowerShell:** anything the other tools can't do (install apps with winget, scripts, tweaks)
- **Files:** find, read, write, move, copy, rename, delete (to the Recycle Bin), create folders, notes
- **Web search:** weather, news, scores, anything current
- **Reminders & timers:** saved to disk, shown in the app, survive restarts

### The camera

He only uses the webcam when you ask him to look. He opens it, takes one photo, and releases it, so the camera light blinks on for about a second. Every photo he takes appears in the conversation panel so you see exactly what he saw, and it's dropped from his memory once he's answered. Turn it off entirely with `JARVIS_CAMERA=false` in `.env`; if he picks the wrong camera, try `JARVIS_CAMERA_INDEX=1`.

### Mouse control: what to expect

It works by looking at a screenshot and pointing, like a person would, so it's slower than a shortcut and occasionally misses a small target. They prefer keyboard shortcuts and app tools when those can do the job, and reach for the mouse when they can't. With several monitors, saying which one helps ("on my second monitor"); they can zoom into a single screen or window for sharper aim. They won't click through password fields, payment pages, security prompts or CAPTCHAs; those are yours.

### Approvals (fast now)

Everyday stuff runs instantly: apps, media, typing, ordinary clicks, **reading files on any of your drives**, and **read-only PowerShell** (`Get-...`, `ipconfig`, `winget search/list`, `systeminfo`...).

Anything that could actually hurt shows a **Needs your OK** card the instant he asks, right under him, with exactly what's about to happen. He turns amber and a ring drains as the 45 seconds run out. Answer however's quickest:

- **Keys:** `Y` or `Enter` allows, `N` or `Esc` denies, `A` allows and stops asking about that kind of thing.
- **From anywhere** (a game, another app): **Ctrl+Alt+Y** / **Ctrl+Alt+N**.
- **Voice:** "yes", "no", "yes, always". He only says one word ("Approve?") instead of a speech, and you can answer before he's finished.
- The corner widget and the phone remote have Allow / Always allow / Deny buttons too.

**Always allow** is per kind of action: PowerShell commands that change things, editing files outside `Documents\Jarvis`, moving things to the Recycle Bin, force-closing apps, clicks that send or submit, Blender scripting, the Blender add-on install. See and switch them off under **Allowed without asking** in the System panel (or delete `Documents\Jarvis\permissions.json`).

**These always ask, no shortcut:** shutdown/restart/sign out, emptying the Recycle Bin, PowerShell that deletes, formats, edits the registry or downloads-and-runs code, and writing into Windows or Program Files. One wrong guess there costs too much. **Never touched at all:** password managers, SSH keys, browser logins/cookies, and his own `.env`.

Read the command before approving. That card is the only thing between a misheard sentence and your files, and "always allow PowerShell" means a misheard sentence can change your system without asking. Turn that one on only if you're comfortable with that.

### The HUD

**Holographic panels.** While he works, panels materialise beside him showing what he's doing: a terminal with the PowerShell command and its output, a radar sweep for web searches, the frame he's looking at with a scan line over it, what's playing (with the video's thumbnail), live gauges for system checks, a spinning wireframe for Blender, and his reasoning scrolling by while he thinks. They dissolve a few seconds after each step. Switch them off under Controls in the System panel. They live inside the HUD on purpose: real browser tabs would pile up and steal focus from whatever you're doing.

He's the centre of the screen: Jarvis as a gyroscope of light, Ultron as a cluster of red shards with an eye that opens when he talks. Your words sit above him, his words appear below him as subtitles, and what he's doing right now ("Searching the web", "Opening Spotify") shows as small chips under those. In **Both** mode they stand side by side and whoever's talking steps forward.

The conversation (left) and system panel (right) step back while he's working with you and come back when he's idle. Hover one to bring it forward, or hide either with the buttons in the top corners. The conversation panel keeps everything: his reasoning, each step with timings, and the full replies.

## Setup (about 10 minutes)

Upgrading? Extract over your old folder (your `.env` and installed packages stay) and run `setup.bat` again.

1. Install **Python 3.12** (or 3.11) from python.org. On the first installer screen, tick **"Add python.exe to PATH"**.
2. Get an API key at **console.anthropic.com** and add a few dollars of credit.
3. Unzip this folder somewhere permanent.
4. Double-click **setup.bat**. It installs everything, downloads the voice, and opens `.env` in Notepad. Paste your key, save, close.
5. Double-click **run_jarvis.bat**. First launch downloads the speech recognition model (~150 MB), so the Voice light takes a minute to go green.

Want it on boot? `Win+R`, type `shell:startup`, drop a shortcut to `run_jarvis.bat` in there.

No mic? `run_jarvis.bat --no-voice`. Plain terminal instead of the app? `run_jarvis.bat --console`. Leave the black console window open; it shows what he hears and why he ignored it, which is how you debug him.

## Speech recognition

Two passes. A fast model hears everything just to catch his name. The moment you talk *to* him, a much better model re-transcribes that sentence carefully. You only pay CPU for accuracy when it counts.

- **NVIDIA GPU?** Run `enable_gpu.bat` once. Recognition then runs on the GPU with a far bigger model (large-v3-turbo) and is both faster and more accurate. He tests the GPU in a separate process at startup, so if the NVIDIA setup is broken he just stays on the CPU instead of crashing.
- **He stopped hearing you after a GPU change?** Close him and run `fix_gpu.bat`. He also checks for this at startup and says so in the conversation panel.
- **Words he keeps getting wrong** (games, apps, friends' names): add them to `JARVIS_VOCAB` in `.env`, comma separated.
- Pick models yourself with `JARVIS_WHISPER` (accurate pass; default `distil-small.en` on CPU, `large-v3-turbo` on GPU; also `small.en`, `medium.en`, `distil-large-v3`) and `JARVIS_WHISPER_FAST` (screening, default `tiny.en`; try `base.en` if he misses his name a lot).

## Cloud speech recognition (optional, best fix for slower PCs)

Turning your voice into text runs on your own CPU, and on a slower or older PC that can take several seconds a sentence. Groq can do it on their servers in a fraction of a second, and more accurately than anything that fits on a normal CPU.

**Setup (2 minutes):**
1. Make a free account at **console.groq.com** and create an API key (API Keys > Create).
2. Open your `.env` file and add a line: `GROQ_API_KEY=` followed by the key. **Never paste the key anywhere else**, including chats.
3. Restart Jarvis. The startup log says `CLOUD SPEECH RECOGNITION ON`.

**What gets sent, normally:** only sentences aimed at him (he checks for his name on your PC first, while you're still talking). Background talk, videos and calls never leave your PC, and neither does anything said by a voice that isn't yours.

**Why it's faster than it sounds:** that name check runs *while you talk*, so by the time you pause he already knows it's for him. The "are you done?" check then goes to Groq the moment you stop (about 0.5 s of silence) instead of waiting out the full pause. On a slower PC that takes "you stopped talking → he starts thinking" from about 2.5 s to about 1.2 s, with the accurate transcript included.

**Cost:** $0.04 per hour of audio, with each sentence billed as at least 10 seconds, so about a cent per hundred requests. Groq has had a free tier with rate limits.

**If anything goes wrong** (no internet, Groq down, rate limit, bad key) he quietly falls back to local recognition and says so in the console.

Without Groq, he still adapts to your PC: he measures how fast your CPU runs the speech models from the very first sentence, and skips or swaps out whatever would take too long, so you're never waiting 10+ seconds.

## Voices

Set in `.env`:

- `JARVIS_VOICE` (default `bm_lewis`). Other British voices: `bm_fable`, `bm_george`, `bm_daniel`.
- `ULTRON_VOICE` (default `bm_lewis`, pitched down with a metallic effect). Also good: `am_onyx`, `am_fenrir`.

Other engines with `JARVIS_TTS` (falls back down the list if one fails):

| Engine | Sounds | Cost | Notes |
|---|---|---|---|
| `kokoro` (default) | Natural | Free | Runs on your PC |
| `elevenlabs` | The most human by a mile | Paid | Needs `ELEVENLABS_API_KEY`; voices via `ELEVENLABS_VOICE_ID` / `ULTRON_ELEVENLABS_VOICE_ID` |
| `edge` | Decent, a bit flat | Free | Needs internet |
| `sapi` | Robot | Free | Built into Windows, last resort |

Kokoro runs on your CPU. On a weak laptop you may hear short pauses between sentences; if so try `JARVIS_TTS=edge`.

## Speed: what makes him fast, and what to do if he isn't

Where the time actually goes when you ask something: working out that you've finished talking, a careful re-listen to what you said, Claude thinking (1 to 4 seconds), then the first sentence being turned into speech. What's built in to shrink that:

- **Transcribes while you talk:** the careful re-listen runs on each finished stretch of your sentence during your natural pauses, so when you stop, only the last couple of words are left to do. Only kicks in for speech aimed at him (it checks for his name first), so the TV doesn't cost CPU.
- **A faster careful-listening model:** `distil-small.en` instead of `small.en` on CPU, about twice as fast with nearly the same accuracy (downloads once, ~170 MB, on first launch).
- **Smart end-of-sentence:** after just over half a second of quiet he takes a quick look at what you said. If it's clearly finished ("Jarvis, open Spotify." / "what's the weather tomorrow?"), he goes right then instead of waiting out the full pause. If you trailed off ("Jarvis, open the..."), he waits like before. Together with transcribing while you talk and the faster model, simulated tests went from about 4 s to 1.2 s between you finishing a question and him starting on it, and from 2.6 s to 1.1 s for quick commands.
- **He won't talk over you:** if you keep going after a pause ("what's the weather tomorrow? ... and should I bring an umbrella?"), he holds his answer, then answers both halves together.
- **Connection kept warm:** the moment you start talking, he makes sure the line to Claude is already open, so the request doesn't pay for a fresh connection.
- **Conversation caching:** the conversation so far is cached on Anthropic's side between messages, so Claude doesn't re-read the whole thing every time. Faster first word, cheaper too.
- **Instant "On it.":** for anything that takes a few seconds (web searches, looking at your screen, Blender, files), a pre-recorded acknowledgement plays the moment he starts, so there's no dead air. Quick chat doesn't get one.
- **Pre-recorded common lines:** short things he says a lot ("Opening Spotify.", "Volume 30.", "Timer set for 5 minutes.", "On it.") are generated once and replayed instantly, for both voices. The first launch spends about a minute doing this in the background; after that they load from disk.
- **Several things at once:** "open Steam and Discord and set the volume to 30" runs all three together instead of one after another. Anything that depends on order (typing, clicking, files) still goes one at a time.
- **Smaller screenshots for quick looks:** "what game is this?" sends a smaller picture than "what does this error say?", which uploads and processes faster.
- **Learns words he gets wrong:** correct him ("no, I said Valorant") and he saves the spelling; speech recognition listens for it from then on. They're in `Documents\Jarvis\vocab.json` if you want to edit them.
- **Faster startup:** the voice loads at the same time as everything else instead of after it.
- **Voice model picked for your PC:** setup.bat times the full and the compressed voice models on your machine and uses whichever is faster. (On some CPUs the compressed one is quicker; on others it's 3x slower, so it's measured, not assumed.)
- **Lighter careful pass on CPU:** the accurate re-listen searches a little less widely on CPU (3 options instead of 5). Barely any accuracy difference, noticeably quicker. Quick commands skip it entirely.
- **First words sooner:** the first phrase is sent to the voice at the first comma instead of waiting for a whole sentence.

- **Instant commands, no AI at all (under a tenth of a second):** pause/play, next/previous song, "volume 30", "turn it up", mute the sound, "open Spotify", "close Discord", "what time is it", "what's the date", "lock the PC", "take a screenshot", "show desktop", "brightness 60", dark/light mode, "set a timer for 5 minutes". Only short, exact phrasings count; anything longer ("open Spotify and play something chill") still goes to Claude, so nothing gets misread. Turn off with `JARVIS_INSTANT=false`.
- **A faster model for simple stuff:** short, everyday requests and chat go to Claude Haiku; anything involving your screen, files, Blender, code, or real explaining stays on the main model. In a duo, the second one's quick reaction uses Haiku too. `JARVIS_FAST_MODEL=` (empty) turns this off.
- **Fewer, broader tools:** 44 tools merged into 20 with nothing lost, so Claude picks the right one quicker and more reliably.
- **Speaks as he thinks:** the first sentence is spoken while the rest is still being written.

**Making it faster from the outside (honest list, biggest win first):**
1. **An NVIDIA graphics card + `enable_gpu.bat`:** speech recognition moves to the GPU, which is the biggest local speed-up there is.
2. **Lower the pause** if you're a quick talker: `JARVIS_PAUSE=1.0`. With smart end-of-sentence on, this mostly affects sentences he can't tell are finished, so the gain is smaller than it used to be.
3. **Haiku for everything:** `JARVIS_MODEL=claude-haiku-5-5`. Noticeably snappier, noticeably less clever on hard stuff.
4. **Wired internet or a closer Wi-Fi spot:** helps a little, since every Claude call is a round trip.
5. **ElevenLabs voice** (`JARVIS_TTS=elevenlabs`): runs in the cloud, so a weak PC isn't doing the voice work. Costs money.

What *won't* help, so you don't waste time: a faster CPU won't speed up Claude's thinking (that happens on Anthropic's servers), more RAM changes nothing, and there's no setting that makes Claude itself respond faster other than picking a smaller model.

## Performance

The HUD draws at about 30fps while something's happening, about 12 at rest, and stops drawing entirely when minimized. Speech recognition is capped at 4 CPU threads (`JARVIS_WHISPER_THREADS`). Still too heavy on an older PC? `JARVIS_WHISPER=distil-small.en` and turning on Windows' "reduce animations" setting (the HUD respects it) both help.

## Speed and cost

The only thing you pay for is Claude API usage: pennies a day for normal use. Web searches and "look at my screen" cost a little extra. Listening, transcription and the default voice all run on your PC for free.

- `JARVIS_SHOW_REASONING=false` gets the first word out a bit sooner on the main model (steps still show).
- Instant commands cost nothing at all; Haiku requests cost a fraction of the main model.

## Tuning (config.py)

| Problem | Fix |
|---|---|
| Still cuts you off when you pause | `JARVIS_PAUSE=2.0` in `.env` (default 1.5 seconds); if it's the quick finish doing it, `JARVIS_EARLY_PAUSE=0.8` or `JARVIS_SMART_PAUSE=false` |
| Feels slow to respond after you stop | `JARVIS_PAUSE=1.0`, and/or lower `HOLD_SECONDS` |
| Background noise keeps it busy | raise `JARVIS_VAD` (default 0.5; try 0.7) |
| Misses you when you speak quietly | lower `JARVIS_VAD` to 0.35 |
| Echo cancelling makes your voice sound odd to him | `JARVIS_ECHO_CANCEL=false` (and use headphones) |
| An instant command does the wrong thing | `JARVIS_INSTANT=false`, and tell me which phrase so it can be fixed |
| Quick answers feel too dumb | `JARVIS_FAST_MODEL=` (empty) to always use the main model |
| Mishears you more than before | `JARVIS_WHISPER=small.en` (the old, slower careful model) |
| Live transcription causes oddities at the joins | `JARVIS_LIVE_TRANSCRIBE=false` |
| The instant "On it." gets annoying | `JARVIS_INSTANT_ACK=false` |
| Voice model choice | `JARVIS_KOKORO=full` or `lite` to override what setup picked |
| Slow to start thinking on an older PC | add a Groq key (see Cloud speech recognition); check the console's `[timing]` lines to see which step is slow |
| He skips the careful pass and mishears more | that's on purpose on slow PCs; `JARVIS_CAREFUL_BUDGET=4` lets him take longer, or use Groq |
| Mishears you a lot | `JARVIS_WHISPER=medium.en` (CPU) or run `enable_gpu.bat` (NVIDIA); `JARVIS_WHISPER_BEAM=5` for the old, slower careful pass |
| Misses his name | add your accent's spelling to `aliases` in personas.py; check the console's "heard" lines |
| CPU usage too high | `JARVIS_WHISPER_FAST=tiny.en` |
| Mute hotkey clashes with something | `JARVIS_MUTE_HOTKEY=ctrl+alt+f12` |
| Wants to read out more / less | `MAX_SPOKEN_WORDS` in config.py |
| The second one in a duo talks too long / too little | `DUO_SECOND_WORDS` in config.py (default 45) |
| Don't want the corner widget | `JARVIS_MINI=false` |
| Want things he opens to always come to the front | `JARVIS_KEEP_FOCUS=false` |
| An app still steals focus after a slow start | raise `KEEP_FOCUS_SECONDS` in config.py (default 12) |

## Honest limitations

- **Always listening costs some CPU.** Speech detection is tiny, but every real sentence gets transcribed locally so he can catch his name, including a video or call the mic picks up. Nothing is sent to Claude unless you address him.
- **Echo cancelling needs a few seconds to learn your room** each time he starts up, and works best when nothing else (music, a game) is playing through the same speakers, since it only knows what *he* played. Headphones still beat it.
- **His name has to be at the start or end** of what you say. "I told my friend about Jarvis" is ignored on purpose.
- **Reminders only fire while he's running.** Missed ones get announced on next launch.
- **"Sleep" may hibernate** if hibernation is enabled. That's a Windows thing.
- **Brightness only works on laptops** and some monitors.
- **He can't text people, buy things or log into your accounts.**
- **File access:** reading works on every local drive (`JARVIS_READ_ANYWHERE=false` limits it to your user folder). Writing outside `Documents\Jarvis` asks first unless you've set "Edit files anywhere" to always allow.

## Adding your own abilities

Every ability is a plain Python function in `tools.py`. Write the function, add a `_spec(...)` entry describing it to `TOOL_SPECS`, add it to `FUNCS`. Claude figures out when to use it from the description. Prefer adding an action to an existing tool over a brand-new tool; fewer tools keep him fast. For something that should happen instantly without Claude, add a pattern to `intents.py`.

## Files

- `jarvis.py` launches the app (or console mode)
- `core.py` the engine: listening rules, interruptions, approvals, persona switching, telemetry
- `brain.py` Claude streaming + tool-calling loop
- `personas.py` Jarvis and Ultron: personality, voice, wake reply
- `speech.py` always-on listening, two-pass speech-to-text, mic mute
- `enable_gpu.bat` optional: GPU speech recognition on NVIDIA cards
- `voice.py` voices, the Ultron effect, and the speak-as-he-thinks pipeline
- `download_models.py` fetches the Kokoro voice
- `vad.py` neural speech detection
- `aec.py` echo cancellation
- `intents.py` instant commands that skip the AI
- `spotify.py` Spotify Web API control
- `youtube.py` finds YouTube videos and plays them
- `autostart.py` start with Windows, and the one-copy-at-a-time lock
- `briefing.py` the morning briefing
- `notifications.py` Discord messages from Windows notifications
- `email_reader.py` reading email (read-only, IMAP with an app password)
- `netflix.py` opening Netflix (web or app) and the watch log
- `apple_music.py` finding songs in Apple's catalog and opening them in the app or on the web
- `settings.py`, `secretbox.py` the Settings panel and encrypted key storage
- `voice_settings.py` changing their voices live; `changelog.py` + `CHANGELOG.md` the What's new pop-up
- `discord_bot.py` the optional Discord bot (chatting, reading channels, sending when allowed)
- `app_main.py`, `app_update.py` the installed app's entry point and self-updating (Velopack)
- `jarvis.spec`, `build.ps1`, `.github/workflows/release.yml` building and publishing the installer (RELEASING.md)
- `updater.py` updating himself from a new zip in Downloads, and undo
- `history.py` conversation memory
- `connectors.py` app connectors (MCP)
- `jobs.py` background jobs
- `usage.py` the cost tracker and daily limit
- `phone.py` the phone remote
- `cloud_stt.py` optional cloud speech recognition (Groq)
- `fix_gpu.bat` repairs the speech libraries if a GPU experiment broke them
- `health.py` startup checks for broken installs
- `tools.py` everything they can do
- `permissions.py` what runs freely, what asks, and "always allow"
- `ui/index.html` the HUD
- `mini.py` + `ui/mini.html` the corner widget shown while he's minimized
- `jarvis_blender_bridge.py` the Blender add-on (and the background runner for 3D modelling)
- `config.py` settings
