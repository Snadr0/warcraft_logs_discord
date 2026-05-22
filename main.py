import os
import re
import json
import time
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

CHARACTERS = [
    name.strip()
    for name in os.getenv("CHARACTERS", "Snadius,Tinysnad").split(",")
    if name.strip()
]

SERVER_SLUG = os.getenv("SERVER_SLUG", "proudmoore")
REGION = os.getenv("SERVER_REGION", "us")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

CHECK_EVERY_SECONDS = int(os.getenv("CHECK_EVERY_SECONDS", "300"))
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")

HEARTBEAT_ENABLED = os.getenv("HEARTBEAT_ENABLED", "true").lower() == "true"
HEARTBEAT_HOURS = float(os.getenv("HEARTBEAT_HOURS", "6"))
POST_STARTUP_HEARTBEAT = os.getenv("POST_STARTUP_HEARTBEAT", "true").lower() == "true"

STATE_FILE = "seen_runs.json"
INITIAL_POST_FILE = "initial_stats_posted.json"
ERROR_STATE_FILE = "error_state.json"


bot_status = {
    "started_at": None,
    "last_check_at": None,
    "last_success_at": None,
    "last_error": None,
    "last_error_at": None,
    "characters": {}
}


def now_dt():
    return datetime.now(ZoneInfo(TIMEZONE))


def now_string():
    return now_dt().strftime("%m/%d/%Y %I:%M %p %Z")


def character_url(character_name):
    return (
        f"https://www.warcraftlogs.com/character/"
        f"{REGION}/{SERVER_SLUG}/{character_name.lower()}?zone=47&metric=playerscore"
    )


def load_json_file(path, default):
    if not os.path.exists(path):
        return default

    with open(path, "r") as f:
        return json.load(f)


def save_json_file(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def extract_number(text):
    match = re.search(r"\d+", text or "")
    if match:
        return int(match.group())
    return None


def extract_float(text):
    match = re.search(r"\d+(?:\.\d+)?", text or "")
    if match:
        return float(match.group())
    return None


def get_dungeon_stats(character_name):
    stats = {}
    url = character_url(character_name)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"Opening {character_name}: {url}")

        page.goto(
            url,
            wait_until="networkidle",
            timeout=60000
        )

        page.wait_for_timeout(8000)

        rows = page.locator("table tr").all()

        for row in rows:
            try:
                cells = row.locator("td").all()

                # Expected columns:
                # 0 Dungeon
                # 1 Best %
                # 2 Highest Points
                # 3 Runs
                # 4 Fastest
                # 5 Med
                if len(cells) < 6:
                    continue

                dungeon = cells[0].inner_text().strip()
                best_text = cells[1].inner_text().strip()
                points_text = cells[2].inner_text().strip()
                runs_text = cells[3].inner_text().strip()
                fastest_text = cells[4].inner_text().strip()
                med_text = cells[5].inner_text().strip()

                best = extract_number(best_text)
                points = extract_float(points_text)
                runs = extract_number(runs_text)
                med = extract_number(med_text)

                if dungeon and runs is not None:
                    stats[dungeon] = {
                        "best": best,
                        "points": points,
                        "runs": runs,
                        "fastest": fastest_text,
                        "med": med
                    }

            except Exception as e:
                print(f"Row parse error for {character_name}:", e)

        browser.close()

    print(f"Dungeon stats for {character_name}:", stats)

    bot_status["characters"][character_name] = {
        "last_rows_found": len(stats),
        "last_url": url,
        "last_seen_at": now_string()
    }

    return stats


def med_arrow(old_med, new_med):
    if old_med is None or new_med is None:
        return "❔"

    if new_med > old_med:
        return "📈"

    if new_med < old_med:
        return "📉"

    return "➡️"


def med_text(old_med, new_med):
    if old_med is None or new_med is None:
        return "unknown"

    if new_med > old_med:
        return "went up"

    if new_med < old_med:
        return "went down"

    return "stayed the same"


def format_points(points):
    if points is None:
        return "N/A"
    return f"{points:.1f}"


def format_stat(value):
    if value is None:
        return "N/A"
    return str(value)


def send_webhook(payload):
    if not DISCORD_WEBHOOK_URL:
        print("No DISCORD_WEBHOOK_URL set.")
        return

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        timeout=20
    )

    response.raise_for_status()
    print("Posted Discord webhook.")


def send_initial_stats(character_name, stats):
    found_time = now_string()
    url = character_url(character_name)

    sorted_stats = sorted(
        stats.items(),
        key=lambda item: item[1].get("points") or 0,
        reverse=True
    )

    lines = []

    for dungeon, data in sorted_stats:
        lines.append(
            f"**{dungeon}**\n"
            f"🏃 Runs: **{data.get('runs', 'N/A')}** | "
            f"📊 Med: **{format_stat(data.get('med'))}** | "
            f"⭐ Best: **{format_stat(data.get('best'))}%** | "
            f"💠 Points: **{format_points(data.get('points'))}** | "
            f"⏱ Fastest: **{data.get('fastest') or 'N/A'}**"
        )

    description = "\n\n".join(lines)

    if len(description) > 3900:
        description = description[:3900] + "\n\n...trimmed"

    payload = {
        "embeds": [
            {
                "title": f"📋 Existing M+ Stats: {character_name}-{SERVER_SLUG}",
                "description": description if description else "No dungeon stats found yet.",
                "url": url,
                "color": 5814783,
                "footer": {
                    "text": f"Initial snapshot posted once • Found at {found_time}"
                }
            }
        ]
    }

    send_webhook(payload)


def send_run_changes(character_name, changes):
    found_time = now_string()
    url = character_url(character_name)

    lines = []

    for change in changes:
        dungeon = change["dungeon"]
        old_runs = change["old_runs"]
        new_runs = change["new_runs"]
        old_med = change["old_med"]
        new_med = change["new_med"]
        arrow = med_arrow(old_med, new_med)
        direction = med_text(old_med, new_med)

        lines.append(
            f"**{dungeon}**\n"
            f"🏃 Runs: **{old_runs} → {new_runs}**\n"
            f"{arrow} Med: **{format_stat(old_med)} → {format_stat(new_med)}** ({direction})"
        )

    payload = {
        "embeds": [
            {
                "title": f"🆕 New M+ Log Detected: {character_name}-{SERVER_SLUG}",
                "description": "\n\n".join(lines),
                "url": url,
                "color": 16753920,
                "footer": {
                    "text": f"Found at {found_time}"
                }
            }
        ]
    }

    send_webhook(payload)


def build_heartbeat_description():
    lines = [
        f"🕒 Started: **{bot_status.get('started_at') or 'N/A'}**",
        f"🔎 Last check: **{bot_status.get('last_check_at') or 'N/A'}**",
        f"✅ Last success: **{bot_status.get('last_success_at') or 'N/A'}**",
        f"🔄 Check interval: **{CHECK_EVERY_SECONDS} seconds**",
        "",
        "👤 **Watching:**"
    ]

    for character_name in CHARACTERS:
        info = bot_status["characters"].get(character_name, {})
        rows = info.get("last_rows_found", "N/A")
        last_seen = info.get("last_seen_at", "N/A")

        lines.append(
            f"• **{character_name}-{SERVER_SLUG}** — {rows} dungeon rows loaded, last seen {last_seen}"
        )

    lines.append("")

    if bot_status.get("last_error"):
        lines.append(f"❤️‍🩹 Last error: `{bot_status['last_error']}`")
        lines.append(f"🕒 Error time: **{bot_status.get('last_error_at') or 'N/A'}**")
    else:
        lines.append("💚 Last error: **None**")

    return "\n".join(lines)


def send_startup_heartbeat():
    payload = {
        "embeds": [
            {
                "title": "🚀 Warcraft Logs Watcher Started",
                "description": build_heartbeat_description(),
                "color": 5814783,
                "footer": {
                    "text": f"Startup heartbeat • {now_string()}"
                }
            }
        ]
    }

    send_webhook(payload)


def send_regular_heartbeat():
    title = "💚 Warcraft Logs Watcher Alive"

    color = 5814783

    if bot_status.get("last_error"):
        title = "❤️‍🩹 Warcraft Logs Watcher Alive, But Last Check Had An Error"
        color = 16753920

    payload = {
        "embeds": [
            {
                "title": title,
                "description": build_heartbeat_description(),
                "color": color,
                "footer": {
                    "text": f"Automatic heartbeat • {now_string()}"
                }
            }
        ]
    }

    send_webhook(payload)


def send_error_alert(error_message):
    bot_status["last_error"] = error_message
    bot_status["last_error_at"] = now_string()

    payload = {
        "embeds": [
            {
                "title": "🚨 Warcraft Logs Watcher Error",
                "description": (
                    f"Something broke during a check.\n\n"
                    f"❌ Error:\n`{error_message[:900]}`\n\n"
                    f"🕒 Time: **{bot_status['last_error_at']}**\n"
                    f"✅ Last success: **{bot_status.get('last_success_at') or 'N/A'}**"
                ),
                "color": 15158332,
                "footer": {
                    "text": "Immediate error alert"
                }
            }
        ]
    }

    send_webhook(payload)


def check_all_characters_once():
    state = load_json_file(STATE_FILE, {})
    initial_status = load_json_file(INITIAL_POST_FILE, {})

    bot_status["last_check_at"] = now_string()

    for character_name in CHARACTERS:
        if character_name not in state:
            state[character_name] = {}

        if character_name not in initial_status:
            initial_status[character_name] = {
                "posted": False
            }

        current = get_dungeon_stats(character_name)

        if not initial_status[character_name].get("posted", False):
            send_initial_stats(character_name, current)
            initial_status[character_name] = {
                "posted": True,
                "posted_at": now_string()
            }

        if not state[character_name]:
            state[character_name] = current
            print(f"First run for {character_name}. Saved {len(current)} dungeon rows.")
            continue

        changes = []

        for dungeon, stats in current.items():
            new_runs = int(stats.get("runs", 0))
            new_med = stats.get("med")

            old_stats = state[character_name].get(dungeon)

            if old_stats is None:
                old_runs = 0
                old_med = None
            else:
                old_runs = int(old_stats.get("runs", new_runs))
                old_med = old_stats.get("med")

            if new_runs > old_runs:
                changes.append({
                    "dungeon": dungeon,
                    "old_runs": old_runs,
                    "new_runs": new_runs,
                    "old_med": old_med,
                    "new_med": new_med
                })

        if changes:
            send_run_changes(character_name, changes)
            state[character_name] = current
        else:
            print(f"No new runs detected for {character_name}.")

    save_json_file(STATE_FILE, state)
    save_json_file(INITIAL_POST_FILE, initial_status)

    bot_status["last_success_at"] = now_string()
    bot_status["last_error"] = None
    bot_status["last_error_at"] = None


def main():
    bot_status["started_at"] = now_string()
    print("Watching characters:", ", ".join(CHARACTERS))

    last_heartbeat_at = None

    try:
        check_all_characters_once()

        if POST_STARTUP_HEARTBEAT and HEARTBEAT_ENABLED:
            send_startup_heartbeat()
            last_heartbeat_at = now_dt()

    except Exception as e:
        error_message = str(e)
        print("STARTUP ERROR:", error_message)

        try:
            send_error_alert(error_message)
        except Exception as alert_error:
            print("Failed to send startup error alert:", alert_error)

    while True:
        try:
            check_all_characters_once()

            if HEARTBEAT_ENABLED:
                should_send_heartbeat = False

                if last_heartbeat_at is None:
                    should_send_heartbeat = True
                else:
                    next_heartbeat_at = last_heartbeat_at + timedelta(hours=HEARTBEAT_HOURS)
                    should_send_heartbeat = now_dt() >= next_heartbeat_at

                if should_send_heartbeat:
                    send_regular_heartbeat()
                    last_heartbeat_at = now_dt()

        except Exception as e:
            error_message = str(e)
            print("ERROR:", error_message)

            error_state = load_json_file(ERROR_STATE_FILE, {
                "last_error": None,
                "last_alert_at": None
            })

            # Avoid spamming the same exact error every 5 minutes.
            # If the error text changes, send immediately.
            # If same error repeats, alert once per heartbeat interval.
            send_alert = False

            if error_state.get("last_error") != error_message:
                send_alert = True
            else:
                last_alert_at_text = error_state.get("last_alert_at")

                if not last_alert_at_text:
                    send_alert = True
                else:
                    try:
                        last_alert_at = datetime.fromisoformat(last_alert_at_text)
                        send_alert = now_dt() >= last_alert_at + timedelta(hours=HEARTBEAT_HOURS)
                    except Exception:
                        send_alert = True

            if send_alert:
                try:
                    send_error_alert(error_message)
                    error_state = {
                        "last_error": error_message,
                        "last_alert_at": now_dt().isoformat()
                    }
                    save_json_file(ERROR_STATE_FILE, error_state)
                except Exception as alert_error:
                    print("Failed to send error alert:", alert_error)

        time.sleep(CHECK_EVERY_SECONDS)


if __name__ == "__main__":
    main()
