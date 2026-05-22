# Warcraft Logs M+ Run Watcher v4

Watches multiple characters:
- Snadius-Proudmoore
- Tinysnad-Proudmoore

Posts:
- Initial existing stats once per character
- Pretty update embeds when Runs increases
- Med old -> new with arrows
- Dungeon name and detected time/date

Also supports Discord commands:
- !status
- !wclstatus
- !logs

## Railway variables

CHARACTERS=Snadius,Tinysnad
SERVER_SLUG=proudmoore
SERVER_REGION=us
DISCORD_WEBHOOK_URL=your_discord_webhook_url
CHECK_EVERY_SECONDS=300
TIMEZONE=America/New_York

Optional, for Discord status command:
DISCORD_BOT_TOKEN=your_discord_bot_token
COMMAND_PREFIX=!

## Discord bot setup for !status

1. Go to Discord Developer Portal.
2. Create an application.
3. Add a bot.
4. Copy the bot token into Railway as DISCORD_BOT_TOKEN.
5. Enable MESSAGE CONTENT INTENT for the bot.
6. Invite bot to your server with Send Messages and Read Message History permissions.
7. Type !status in Discord.

If DISCORD_BOT_TOKEN is not set, the watcher still runs normally and posts webhook updates.
