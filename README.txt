# Warcraft Logs M+ Run Watcher v2

This watches:

https://www.warcraftlogs.com/character/us/proudmoore/snadius?zone=47&metric=playerscore

It posts to Discord when any dungeon's Runs number increases.

Discord message includes:
- Dungeon name
- Time/date the new dungeon run was found
- Runs old -> new
- Med old -> new
- Whether Med went up, down, or stayed the same

## Railway variables

CHARACTER_NAME=Snadius
SERVER_SLUG=proudmoore
SERVER_REGION=us
DISCORD_WEBHOOK_URL=your_discord_webhook_url
CHECK_EVERY_SECONDS=300
TIMEZONE=America/New_York

## Files

- main.py
- requirements.txt
- Dockerfile
