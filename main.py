import os
import re
import json
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright

CHARACTER_NAME = os.getenv("CHARACTER_NAME", "Snadius")
SERVER_SLUG = os.getenv("SERVER_SLUG", "proudmoore")
REGION = os.getenv("SERVER_REGION", "us")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CHECK_EVERY_SECONDS = int(os.getenv("CHECK_EVERY_SECONDS", "300"))
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")

SEEN_FILE = "seen_runs.json"
INITIAL_POST_FILE = "initial_stats_posted.json"

CHARACTER_URL = (
    f"https://www.warcraftlogs.com/character/"
    f"{REGION}/{SERVER_SLUG}/{CHARACTER_NAME.lower()}?zone=47&metric=playerscore"
)


def now_string():
    tz = ZoneInfo(TIMEZONE)
    return datetime.now(tz).strftime("%m/%d/%Y %I:%M %p %Z")


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


def get_dungeon_stats():
    dungeon_stats = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Opening:", CHARACTER_URL)

        page.goto(
            CHARACTER_URL,
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
                    dungeon_stats[dungeon] = {
                        "best": best,
                        "points": points,
                        "runs": runs,
                        "fastest": fastest_text,
                        "med": med
                    }

            except Exception as e:
                print("Row parse error:", e)

        browser.close()

    print("Dungeon stats:", dungeon_stats)
    return dungeon_stats


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

    r = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        timeout=20
    )

    r.raise_for_status()
    print("Posted Discord update.")


def send_initial_stats(stats):
    found_time = now_string()

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

    # Discord embed descriptions max at 4096 chars.
    if len(description) > 3900:
        description = description[:3900] + "\n\n...trimmed"

    payload = {
        "embeds": [
            {
                "title": f"📋 Existing M+ Stats: {CHARACTER_NAME}-{SERVER_SLUG}",
                "description": description if description else "No dungeon stats found yet.",
                "url": CHARACTER_URL,
                "color": 5814783,
                "footer": {
                    "text": f"Initial snapshot posted once • Found at {found_time}"
                }
            }
        ]
    }

    send_webhook(payload)


def send_run_changes(changes):
    found_time = now_string()

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
                "title": f"🆕 New M+ Log Detected: {CHARACTER_NAME}-{SERVER_SLUG}",
                "description": "\n\n".join(lines),
                "url": CHARACTER_URL,
                "color": 16753920,
                "footer": {
                    "text": f"Found at {found_time}"
                }
            }
        ]
    }

    send_webhook(payload)


def main():
    print("Watching:", CHARACTER_URL)

    seen = load_json_file(SEEN_FILE, {})
    initial_status = load_json_file(INITIAL_POST_FILE, {"posted": False})

    if not seen:
        current = get_dungeon_stats()

        if not initial_status.get("posted", False):
            send_initial_stats(current)
            save_json_file(INITIAL_POST_FILE, {
                "posted": True,
                "posted_at": now_string()
            })

        save_json_file(SEEN_FILE, current)
        print(f"First run complete. Saved {len(current)} dungeon rows.")
        seen = current

    elif not initial_status.get("posted", False):
        current = get_dungeon_stats()
        send_initial_stats(current)
        save_json_file(INITIAL_POST_FILE, {
            "posted": True,
            "posted_at": now_string()
        })

    while True:
        try:
            current = get_dungeon_stats()
            changes = []

            for dungeon, stats in current.items():
                new_runs = int(stats.get("runs", 0))
                new_med = stats.get("med")

                old_stats = seen.get(dungeon)

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
                send_run_changes(changes)
                save_json_file(SEEN_FILE, current)
                seen = current
            else:
                print("No new runs detected.")

        except Exception as e:
            print("ERROR:", e)

        time.sleep(CHECK_EVERY_SECONDS)


if __name__ == "__main__":
    main()
