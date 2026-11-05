# Her Discord bot on a server (24/7)

The app's brain, voice and desktop stay on your PC. This only moves the **Discord bot** to a small always-on
Linux server, so she answers in Discord while your PC is off.

## What you need
- The cheapest Linux server from any host (Hetzner, DigitalOcean, Vultr, Oracle's free tier...). 1 CPU and 1 GB of
  memory is plenty. Pick Ubuntu.
- Your Discord bot token and Anthropic API key.

## Setup (about 15 minutes)
1. Log in to the server (the host shows you how) and run:
   ```
   sudo adduser --disabled-password juno
   sudo apt update && sudo apt install -y git python3-venv
   sudo -iu juno
   git clone https://github.com/KIzzyonroller/jarvis-2.git && cd jarvis-2
   python3 -m venv .venv && .venv/bin/pip install -r server/requirements.txt
   ```
   (If the repository is private, clone it with a GitHub access token, or copy the folder over.)
2. Make a `.env` next to `jarvis.py` with **plain** values (keys saved from the PC's Settings are encrypted to your
   Windows account and won't work here):
   ```
   ANTHROPIC_API_KEY=...
   DISCORD_BOT_TOKEN=...
   DISCORD_OWNER_ID=your Discord user id
   DISCORD_BOT_REPLY=everyone        # or owner, or off
   BOT_PERSONA=juno                  # or jarvis / ultron
   JARVIS_DAILY_BUDGET=3             # dollars a day the bot may spend
   ```
   Then `chmod 600 .env` so only this user can read it.
3. Try it: `.venv/bin/python server/run_bot.py`. It should say `status: online as ...`. Ctrl+C to stop.
4. Keep it running forever: as your normal (sudo) user, copy `server/juno-bot.service` to
   `/etc/systemd/system/`, fix the paths if you used a different user, then
   `sudo systemctl daemon-reload && sudo systemctl enable --now juno-bot`.
5. **On your PC**: Settings > What she can use > turn on **"Discord bot runs on my server"**, so the PC doesn't
   start a second copy (two copies answer everything twice).

## Updating
`sudo -iu juno`, `cd jarvis-2 && git pull`, then `sudo systemctl restart juno-bot`.

## What it can't do
Same as on the PC: chat and web search only. No access to your PC, files, memory or routines, never pings
@everyone, and sending messages for you still only happens from the PC app with your approval.
