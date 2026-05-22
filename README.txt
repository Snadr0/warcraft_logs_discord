# Warcraft Logs M+ Run Watcher v5

Webhook-only version. No Discord bot token needed.

Watches:
- Snadius-Proudmoore
- Tinysnad-Proudmoore

Posts:
- Initial existing stats once per character
- Pretty update embeds when Runs increases
- Startup heartbeat
- Automatic heartbeat every X hours
- Immediate error alerts if a check breaks

## Railway variables

CHARACTERS=Snadius,Tinysnad
SERVER_SLUG=proudmoore
SERVER_REGION=us
DISCORD_WEBHOOK_URL=your_discord_webhook_url
CHECK_EVERY_SECONDS=300
TIMEZONE=America/New_York
HEARTBEAT_ENABLED=true
HEARTBEAT_HOURS=6
POST_STARTUP_HEARTBEAT=true

## Files

- main.py
- requirements.txt
- Dockerfile

## Notes

If you want the bot to post initial stats again, clear/delete:
- seen_runs.json
- initial_stats_posted.json

On Railway without a persistent volume, redeploying may reset these files.

## v6 update

Class-themed initial stat titles:
- Tinysnad: 🟫🛡️ Existing M+ Stats ... ⚔️🟫
- Snadius: 🟥🩸 Existing M+ Stats ... ❤️ 🟥
