# Warcraft Logs M+ Run Watcher v3

This watches:

https://www.warcraftlogs.com/character/us/proudmoore/snadius?zone=47&metric=playerscore

It posts an initial existing-stats snapshot to Discord once, then posts updates when any dungeon's Runs number increases.

Discord messages include:
- Pretty embeds
- Dungeon names
- Time/date detected
- Runs old -> new
- Med old -> new
- Emojis/arrows for clarity

## Railway variables

CHARACTER_NAME=Snadius
SERVER_SLUG=proudmoore
SERVER_REGION=us
DISCORD_WEBHOOK_URL=your_discord_webhook_url
CHECK_EVERY_SECONDS=300
TIMEZONE=America/New_York

## Reset initial post

If you want the bot to post the initial stats again, delete initial_stats_posted.json from the running environment or redeploy with no persistent volume/state.
