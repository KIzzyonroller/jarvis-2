# What's new

Newest first. After an update, Jarvis shows everything added since the version you had before.
Each release starts with a "## version" line: the same number you type when you run the Release workflow (1.0.12, 1.0.13...).

## 1.0.43

- **A new icon.** His dial: the ring of ticks you see on the desktop, with the amber arc it shows while he's thinking. A simpler version for the tiny sizes so it stays crisp in the taskbar and tray.
- **Search your settings.** Press Ctrl+F (or /) in Settings and type: every setting that mentions it shows up, and you can change it right there.
- **Settings say when a restart is needed.** Only the ones that actually need it are marked, and the button just says "Save" when nothing does.
- **Back to default.** Changed something and regret it? "Default" next to a setting puts it back to how he came.
- **Widgets dressed for each world.** The desktop widgets now match his pop-up panels: blueprint type on the bench, serif cards in the archive and greenhouse, and so on. They also have a solid backing now, so the scene behind them never makes them hard to read.
- **Docs.** A proper guide: installing, talking to him, instant commands, his desktop, settings, costs, privacy, guests, gaming, plugins, updates and what to do when something's wrong.
- **The website is live on GitHub Pages,** with the greenhouse, the new icon and the docs.
- Fixed: the plugin help pointed to a settings page that doesn't exist (it's Settings > What he knows > Plugins). A Discord channel no longer shows as "##channel" on the Messages widget.

## 1.0.42

- **His world moves now.** Small things live in each scene: stars twinkle and the odd shooting star crosses the station window, dust drifts through the archive's moonlight while the desk lamp breathes, the listening post's waterfall scrolls, glints catch the sea on the chart while a little ship works along the route. It runs at 10 frames a second, stops completely while a game or anything fullscreen is up, and is off in performance mode. Settings > His desktop > Living scene turns it off if you'd rather have a still picture.
- **A new world: the greenhouse.** A glasshouse at night with rain running down the glass and warm bulbs overhead. The slate by the door counts the days you've kept him, the temperature outside and when he was "planted", and the plant tags are named after the apps you tend most. "Switch your desktop to the greenhouse."
- **The light follows your day.** Every scene lifts a little in daylight, warms at golden hour and sinks in the small hours, timed to your real sunrise and sunset. When it's actually raining or snowing where you are, it rains or snows in his world (not on the station: space has no weather). A few days of the year have a little something extra.
- **His orb.** Settings > His desktop > How he looks > Orb: a soft ball of light instead of the dial. It breathes while he listens, sparks circle it while he thinks, and its edge moves with his voice.
- **Screensaver.** Settings > His desktop > Screensaver (5 to 30 minutes): his world fills the screen, drifting slowly, with the clock, your next event and the weather. Touch anything and it's gone. It won't come up during a game, a video, anything fullscreen or while he's talking. "Start your screensaver" shows it now.
- **Lights that match his world.** Settings > His desktop > Lights match his world: switch scenes and your RGB (OpenRGB, SignalRGB, iCUE, Synapse, G HUB) and smart lights take that world's colour. Discord can't be themed by another app, and the main window keeps your persona's colours.

## 1.0.41

- **Post-match stats.** For Steam games that publish stats (Dead by Daylight, CS2 and lots more), he notes your Steam stats when the game opens and, a minute or two after it closes, tells you what changed: escapes, generators, kills, wins. "How did that go?" asks mid-session. Needs your Steam key and ID and Steam's "Game details" set to public.
- **Valorant matches.** Valorant isn't on Steam, so with a free HenrikDev key (api.henrikdev.xyz) and your Riot ID (Settings > Games and alerts) he reads your last match: map, agent, K/D/A, win or loss, and counts the result toward your record.
- **"Clip that."** He presses your recorder's save-replay shortcut (NVIDIA Instant Replay's Alt+F10, or Xbox Game Bar's Win+Alt+G), then checks a new video actually appeared, and tells you if it didn't (and why that usually is). It's an instant command, so it's fast mid-game, and he lets go of every key straight after.
- **Sales radar.** Once a week (late in the week, when sales start) he checks what's on sale on Steam and tells you about games like the ones you actually play, matched by their Steam tags. Games you already own are left out. "Anything on sale I'd like?" checks now.
- **Monthly gaming report.** On the 1st: hours per game, sessions, longest sitting, busiest day of the week, the wins and losses you told him about, and the change from the month before. "How was my gaming month?" any time.

## 1.0.40

- **See everything he knows about you.** Settings > What he knows (or "what do you know about me?") lists every single thing he keeps: memories, your words, inside jokes, birthdays, routines, triggers, price watches, voiceprints, and how much conversation history, activity memory, screenshot text and play time he has. Change or delete any item, or wipe a whole section. It all lives on your PC in Documents\Jarvis and is never sent anywhere.
- **"What was I doing on this day last year?"** Also "last Tuesday", "March 3rd", "three weeks ago". He pieces the day together from what you talked about, which apps you used, games you played and your journal, and says plainly when he has nothing for that day instead of inventing it.
- **He learns your habits and offers to automate them.** If you ask for the same thing at about the same time on 4+ days ("market and weather" around 8), or always ask for the same thing right after opening a game, he offers once to do it by himself. Yes makes it a trigger; no means he never asks about that one again. At most one offer a day, never mid-game.
- **Plugins.** Drop a .py file in Documents\Jarvis\plugins to give him new skills (there's an example and a README in that folder). New plugins are off until you approve them, and a plugin that changes is switched off until you approve it again, because plugins are real code. A plugin that crashes can't take him down with it. Settings > What he knows > Plugins.

## 1.0.39

- **Cut in like you would with a person.** Start talking while he's mid-answer and he gets quieter straight away. "Wait, no...", "actually...", "hold on" or "I meant..." stops him, and he answers the new thing, knowing what he was in the middle of. Once he knows your voice, anything you say over him counts; other people and the TV can't cut him off. A cough or his own echo doesn't trigger it.
- **Guests.** "Learn my friend Leo's voice" (Leo talks for about 20 seconds). After that Leo can ask him things, play music, check scores and so on, but can't change settings, touch files, send messages, see your personal stuff or approve anything. Anyone he doesn't know is still ignored. "Forget Leo's voice" removes it.
- **Emotion in his voice.** A little brighter and quicker for good news ("we won!"), slower and softer for bad news or late at night, steadier for serious things. Subtle on purpose: same voice, different mood.
- **Spanish and English, mixed.** Settings > Languages > "Spanish and English, mixed". Talk in either, or both in one sentence; he answers in the language you mostly used, in natural Latin American Spanish, and his voice switches to match. He also catches "Jarvis" said with a Spanish accent ("Yarvis").
- **Your slang.** Tell him once that "the squad" means you, Leo and Ana, or that "the spot" is the taco place, and he understands it from then on and uses it back.
- **Second opinions.** "Am I wrong?", "be honest", "devil's advocate", "roast my plan": he makes the strongest honest case against you first, then gives his real verdict and how sure he is. No flattery, no fence-sitting.
- **"Why did you say that?"** He keeps a receipt of how each answer was made (what he searched, which sources, what each tool returned, his own reasoning) and walks you through it, including which parts were his own judgment.

## 1.0.38

- **Clipboard history.** "What did I copy ten minutes ago?", "put the link I copied before this one back". He remembers your last 60 copies while he's running (in memory only, gone when he closes). Passwords never get in: anything a password manager marks private, and anything that looks like a key or password, is skipped.
- **Search your screenshots by what was on them.** "Find the screenshot with the error message", "the one with the Amazon receipt". He reads the text in your screenshots on this PC (Windows' own text recognition), a few at a time when you're not busy, and shows matches with thumbnails. Only the words are saved, never the pictures.
- **Duplicate finder.** "Find duplicate files" checks Downloads, Desktop, Documents, Pictures, Videos, Music and OneDrive for exact copies (by content, not name) and photos that look the same, and shows how much space they waste. "Clean them up" sends the extra copies to the Recycle Bin after one approval; the copy in the best place is kept. "Undo that" puts them all back.
- **Maths and conversions, instantly.** "What's 15% of 240", "18 percent tip on 64.50", "5 miles in km", "350 fahrenheit in celsius", "200 grams of flour in cups", "100 dollars in quetzales" (live exchange rates). Answered on your PC in a blink, with the working on your desktop.
- **Price watcher.** "Tell me when that GPU drops under $400", "watch Elden Ring for a sale", "tell me if Bitcoin goes over 120k". Works with most store pages (Best Buy, Newegg, Walmart, B&H; Amazon usually blocks it, and he says so), Steam games, stocks and crypto. He tells you once, with a little price history on your desktop.
- **Wind-down.** Set a bedtime ("my bedtime is 11:30"). Half an hour before, he tells you the first thing tomorrow and the weather, goes into whisper mode, and slowly dims and warms your lights. At bedtime, one offer to say goodnight. Never mid-game or mid-call.
- **Fixed: "whisper mode off" didn't turn it off.**

## 1.0.37

- **Fixed: learning your voice never stuck.** He saved your voiceprint to a file his own start-up clean-up deleted every time he launched. It now lives in its own file. Say "Jarvis, learn my voice" once more after updating and it stays learned.
- **Fixed: triggers firing for the wrong app.** A trigger for "SteamVR" also fired when Steam opened. App names now have to really match.
- **"Undo that."** He takes back his last change: a file he moved, renamed, made, edited or deleted (he keeps a copy before deleting anything under 200 MB), or a setting he changed by voice, like his world or a widget. "What can you undo?" lists the recent ones. It works after a restart too.
- **First-time tour.** New installs get a short guided setup after the key: check the mic (with a live level bar), what he should call you, learning your voice, and picking his world. "Run the setup again", or Settings > General > Help, shows it any time.
- **Crash reports, only if you want them.** When something breaks, the details are saved on your PC. "Send a crash report" (or Settings > General > Help > Report a problem) opens a GitHub issue in your browser, already filled in and cleaned of your keys, names and email, for you to check and submit yourself. Nothing is ever sent by itself.
- **Performance mode.** Settings > General > Starting up: Lite uses a lighter speech model, runs the desktop at 15 frames a second with no effects, and skips the ambient lines. Auto turns it on for PCs with under 8 GB of RAM or 4 or fewer CPU threads.
- **A test suite.** 60 automatic checks now run before every release (tests folder). If any fail, the release stops, so a bug like 1.0.34's "every request crashes" can't reach you again. It already caught the two bugs above.

## 1.0.36

- **Fixed: "something broke on my end" on every request (KeyError: 'automation').** The new automation tools from 1.0.34 were missing from the list he uses to offer extra tools, so every question crashed before reaching Claude. Fixed, and that list can no longer crash on a group it doesn't know.

## 1.0.35

- **Fixed: your keyboard acting up and Chrome downloading pages instead of opening them.** When he handed focus back to your window he briefly pressed Alt, and if an admin window (a UAC prompt, Task Manager, Memory Diagnostics) was in front, Windows threw away the "let go of Alt" half. Alt stayed held down, so every click in Chrome became Alt+click, which downloads the link as an .html file, and typing set off menu shortcuts. He now presses and releases Alt before switching, never fights admin windows for focus, and lets go of every modifier after any key press of his own.
- **Fixed: "run your diagnostics" opened Windows Memory Diagnostics.** It now runs his own check, instantly.
- **Fixed: learning your voice failed if you talked in one long go.** Long speech now counts as several samples.
- His spending estimate uses Sonnet 5.5's lower cache price (cut in October), so it no longer over-counts.

## 1.0.34

- **He checks himself.** "Run diagnostics" tests every part of him (mic, speech, Claude, voice, internet, live prices, scores, flights, weather, Steam, lights, Discord, desktop, screen reading, documents, disk, settings, voice ID, file search, triggers) in a few seconds and puts a pass / warn / fail list on your desktop (also saved as diagnostics.txt). "Fix it" repairs what he can: restarts his hearing or voice, the live price stream or the Discord bot, finds your lights again, picks a working mic, fixes a broken settings file (asks first). When a tool fails mid-answer, he now tries the matching fix once before giving up.
- **He only answers your voice.** Say "Jarvis, learn my voice" and talk for about 20 seconds. After that, anyone else saying his name is ignored. It's checked on your PC (nothing uploaded) and slowly adapts to your mic. Settings > Microphone > Who he listens to, with how strict it is.
- **Conversation mode.** After he answers, keep talking for 45 seconds without saying his name (20 s, 45 s or 2 minutes, or off).
- **Private mode.** "Private mode on": every word is recognised on your PC, never sent to Groq. (What you ask him still goes to Claude to answer.)
- **Whisper mode.** Late at night (11pm to 7am by default) or whenever Discord, Zoom, Teams etc. is using your mic, he talks quietly and keeps it short. "Whisper mode on/off" any time.
- **Triggers.** "When I open Dead by Daylight, turn the lights red, open Discord and play my DBD playlist." "Every weekday at 8, tell me the market and the weather." "When I get back to my PC, tell me what I missed on Discord." Anything he can do, on an app or game opening, a time and days, or you coming back. "What triggers do I have", "pause the DBD one".
- **Play time.** He keeps track of how long you play each game. "How long have I played today?" gives the time per game and the wins and losses you've told him. After 3 hours in one sitting (you choose) he suggests a break, right after a match, never mid-game.
- **Patch heads-up.** Launch a game that updated in the last two days and he gives you the gist while it loads.
- **Instant file finder.** "Find that PDF from my landlord last month", "where's the budget spreadsheet": searches Windows' own index (names and words inside documents) across your user folder in under a second, numbered on your desktop. "Open number two."
- **Where did I leave off.** Back after 20+ minutes away, he tells you what you were in, the last thing you asked him and what's coming up.
- **"What's this?"** looks at the window in front of you and tells you.
- **Cooking.** "What can I make with eggs, rice and spinach?" One or two real dishes, then the recipe up on your desktop with what you're missing highlighted.
- **Gift ideas.** A week before a birthday he offers ideas built from what he actually knows about that person. "Gift ideas for Kai" any time.
- **Inside jokes.** When something gets a real laugh he remembers it, and brings it back now and then. Rarely.
- **Little lines from his world.** Every so often (rarely by default) one line that fits his scene. Never mid-game or mid-call.
- **A letter every Sunday.** Sunday evening he writes you a letter about your week (a Word file on your desktop): what you did, what he noticed, and a couple of honest observations. "Write my weekly letter" does it now.

## 1.0.33

- **The corner widget can be closed.** It now has a ×. Now that his desktop shows what he's doing, you can close it for good: it only comes back, briefly, when he needs you to approve something while his window is minimized (you can still answer those by voice or hotkey). Turn it back on in Settings or say "bring back the corner widget".

## 1.0.30

- **Picking a microphone works again.** Choosing a mic in Settings > Microphone crashed the save, so it quietly stayed on Windows' default. Fixed.
- **He pulls things up on Google for you.** "Google the best budget gaming mouse", "pull up pictures of Lake Atitlán", "open a bunch of tabs on building a PC": he opens them in your own browser, one tab each (up to 15). Works for Google web, images, news, videos, shopping and Maps, plus YouTube, Reddit, Wikipedia and Amazon, or any sites you name.
- **Arrange your widgets however you want.** Settings > Arrange the desktop shows your monitors with the widgets on them: drag any widget anywhere (either monitor), × hides it, the buttons underneath bring it back, double-click puts it back in the column. Arrow keys nudge the selected one. It changes on your desktop as you go. The same page sets where each kind of pulled-up panel appears. By voice: "move the weather to the top left", "put the stocks on my second monitor", "hide the messages", "bring all the widgets back", "put the widgets back in a column".
- **Closing him actually closes him.** A hidden helper window or a background task (the Discord bot, the live price stream) could keep him running after his window was gone, so you had to end him in Task Manager. Now he puts everything away and the whole app ends within a few seconds of closing, whatever is still hanging on.
- **He tells you when he can't hear you.** The log and his window now say which microphone he's listening on at startup, and if it sends nothing but silence for 20 seconds he says so ("MIC IS SILENT") instead of just ignoring you.

## 1.0.29

(1.0.28's changes, released as 1.0.29.)

## 1.0.28

- **It's just Jarvis now.** Juno and Ultron are retired: no switcher, no "both of you", one voice, one name to say. He keeps the moods, his opinions and starting conversations. "Switch to Juno" gets a polite no.
- **A new desktop, his world.** Pick a scene in Settings > His desktop (or say "switch your desktop to the archive"): the drafting bench (his blueprints at night), an orbital station above a planet, his private archive, a listening post, or a map of your digital island. Each is a still picture with a bit of lore he knows about and can bring up.
- **Calm by default.** No start-up intro, no drifting shards, nothing animating in the background. His voice ring sits still and only moves while you two are talking. Panels and widgets just appear, without sweep-ins or scanning effects (Settings > His desktop > Calm panels). When he's idle the desktop isn't drawing anything at all, so it's lighter on your PC too.
- **Stocks.** Ask for a price ("what's Nvidia at?"), how something's done this month or year, why it moved (recent headlines), when it reports earnings, or to compare two. "What do you think of AMD?" gets his real read: the bull case, the bear case and what he'd watch. He's not a financial advisor and he says so; he never tells you to buy or sell, and he can't trade. Data is from Yahoo Finance: free, no account, can be up to 15 minutes behind.
- **Your watchlist.** "Add AMD to my watchlist" (or Settings > Connected apps > Stocks). It shows as a widget on your desktop, the morning briefing gets a one-line market check, and if something on it moves big in a day (4% by default) he gives you a heads-up, never mid-game.
- **He just knows things.** Real questions ("who won last night", "how tall is Everest", "what's the capital of Peru") now go to his main brain instead of the quick one, and he looks up anything that could have changed (prices, news, scores, releases) without being asked to.
- **The scene uses your real stuff.** It's still a still picture, but its details are real and update every few minutes: the station counts down to your actual sunset, the bench shows his real version and when he was last updated, the archive's plaque counts what he remembers about you, the listening post shows the temperature outside and your internet latency, and the map's places are named after the apps you use most (with activity memory on).
- **Paper portfolio.** "Log that on paper": when he gives a take on a stock, he can record it as a pretend position with the price and his reason. "How are your calls doing?" shows the score, so you can see whether his opinions actually hold up. No money is involved.
- **Earnings the night before.** The evening before a company on your watchlist reports, he mentions it and offers what he'd watch.
- **Sunday recap.** Sunday evening: how the S&P, your watchlist and his paper calls did that week, in a sentence.
- **Faster and cheaper answers.** He used to send all ~55 tools with every question, and a detail that changed every turn (the app in front) sat where it threw away the saved part of the conversation, so almost every question was paid for in full. Now he gets the everyday tools plus what your request needs (and loads more himself when he needs them), the changing detail rides along with your message, and old web search pages are dropped once they're a few turns old. If he ever says he can't do something he should, turn off Settings > Answering > "Load tools as needed".
- **All five scenes, rebuilt at 4K.** Far more detail in each: the bench has a full engineering drawing (gears, bearing, exploded view, parts list, revision table), the station looks out over a planet with city lights, aurora and a moon, the archive is a real library in perspective with a moonlit window, the listening post is a wall of instruments and a patch bay, and the chart is a proper sea chart with contour bands, rivers and a compass rose.
- **He pulls things up while he talks.** Ask about a stock and its live chart builds in beside him; the sources he searched appear as he answers; "how's my day" lays it out as a timeline; "show me my PC" opens your PC up with live load and temperatures; a file he makes shows as a preview; "what's the weather" brings radar. Each scene draws them in its own style.
- **Actually live prices.** Stock panels and the watchlist widget stream every price change as it happens (Yahoo Finance's live feed, the one its website uses): the price flashes green or red on each tick, the chart grows, and a tape shows the last few trades. US stocks tick in real time during market hours, crypto around the clock. If the stream can't connect it falls back to checking every 15 seconds, and the LIVE badge greys out when nothing's come in for a while.
- **Everything else he pulls up is live too.** Scores update every 10 seconds and flash when someone scores (with the last play, where ESPN gives it). Flights redraw every 5 seconds on a little map with the route so far. Downloads show speed every second with a graph. The radar plays the last 80 minutes of rain on a loop and fetches new frames every 10 minutes. Your PC's panel graphs processor and graphics load. The network map keeps watching while it's up and shows anything that joins.
- **Focus.** "Show me", "pull up" or "let me see" puts that panel in the middle and dims the rest. "Back" undoes it, "clear that" puts everything away (both instant).
- **Network sweep.** "Anything weird on my network?" maps every device on your Wi-Fi round the router and flags anything new since last time. Read-only.
- **Pre-game briefing.** When a game starts: friends playing, Dead by Daylight queue times, the latest patch notes and how your games have gone, on the desktop while it loads.
- **Trackers.** "Track the Lakers game" (live score until full time), "watch my download", "track flight UA123". Packages aren't possible: carriers want paid accounts, so he offers a web lookup instead.
- **Put panels where you want.** "Put the stocks on my second monitor", "weather on the left", "move the widgets to the left". He remembers.
- **He makes real files.** "Make me a budget spreadsheet", "put a cover letter on my desktop", "turn this into slides", "make a PDF of that": he writes Word, Excel (with working formulas), PowerPoint and PDF files, plus any text, Markdown, CSV or code file, and whole project folders at once. He can also read Word, Excel, PowerPoint and PDF files, change part of a text file (keeping a .bak of the old one), search inside files ("which of my notes mention the lease?"), and zip or unzip.
- **Less asking for new things.** Creating new files and folders on your desktop and in Documents, Downloads, Pictures, Music and Videos no longer asks first. Changing, moving or deleting anything that's already yours still asks (and "Always allow" on that prompt still works). Windows and program folders always ask. Set it back to "only his own folder" in Settings > Application access.
- **Journal renamed.** It's "Jarvis Journal.txt" on your desktop now; an old "Juno Journal.txt" is renamed for you, nothing lost.
- **Personality settings reworked for him:** Classic, Warm, Sharp, Focused or Theatrical, plus humor, length and your own notes.

## 1.0.27

- **Glass mode on the desktop gets the camera now.** It was being blocked, so it kept falling back to its own window. If the camera still can't start there, the cards stay on your desktop to look at and she tells you how to get your hands back, instead of a window popping up.
- **Cards on your desktop without glass mode.** "Put that list on my desktop" shows it as a card on her wallpaper for a while (10 minutes by default, up to 2 hours).
- **"Open glass mode" opens glass mode.** It was being mistaken for an app name and opened something else.
- **Changing where the desktop visualizers go no longer restarts her.**

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
  - **Glass mode on your desktop** (Settings > Appearance & animations > Glass mode, or tell her "put glass mode on my desktop"). Instead of its own window with your camera behind the cards, the cards float over her world on your main monitor. Your windows minimize so you can see it and come back when you close it. The desktop can't take clicks, so it's hands only there; say "line up my hand" if the dots are off. If the camera can't be used there, it opens in its own window instead. Needs "Her world as your desktop" on.
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
