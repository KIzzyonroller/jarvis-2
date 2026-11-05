"""
Her Discord bot on its own, for a small always-on server (so she stays in Discord when your PC is off).

Same bot as the one inside the app, chat-only: web search, no access to any PC, none of your memory or routines.
Run it from the repo folder:   python server/run_bot.py
Settings come from a plain .env next to jarvis.py on the server (the PC's .env can't be copied: its keys are
encrypted to your Windows account). See server/README.md.

Important: only ONE copy of the bot may run. On your PC turn on "Discord bot runs on my server" in Settings
(or DISCORD_BOT_ON_SERVER=true), or both will answer every message twice.
"""
import os
import signal
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402

if not config.DISCORD_BOT_TOKEN or not config.ANTHROPIC_API_KEY:
    sys.exit("Need DISCORD_BOT_TOKEN and ANTHROPIC_API_KEY in the .env next to jarvis.py.")

from brain import Brain  # noqa: E402
import discord_bot  # noqa: E402

PERSONA = os.environ.get("BOT_PERSONA", "juno").lower()
stop = threading.Event()
signal.signal(signal.SIGTERM, lambda *_: stop.set())
signal.signal(signal.SIGINT, lambda *_: stop.set())

bot = discord_bot.DiscordBot(make_brain=lambda p: Brain(p), persona_key=lambda: PERSONA,
                             on_chat=lambda i: print(f"[{i['where']}] {i['who']}: {i['text'][:80]!r} -> {i['reply'][:80]!r}", flush=True))
bot.start()
print(f"Discord bot starting as {PERSONA}...", flush=True)
last = None
while not stop.wait(5):
    v = bot.view()
    if v["status"] != last:
        last = v["status"]
        print(f"status: {last}" + (f" ({v['error']})" if v.get("error") else "") + (f" as {v['name']}" if v.get("name") else ""), flush=True)
print("stopping", flush=True)
