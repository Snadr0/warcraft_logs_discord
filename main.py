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

CHARACTER_URL = (
    f"https://www.warcraftlogs.com/character/"
    f"{REGION}/{SERVER_SLUG}/{CHARACTER_NAME.lower()}?zone=47&metric=playerscore"
)


def now_string():
    tz = ZoneInfo(TIMEZONE)
    return datetime.now(tz).strftime("%m/%d/%Y %I:%M %p %Z")


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return {}

    with open(SEEN_FILE, "r") as f:
        return json.load(f)


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=2)


def extract_number(text):
    match = re.search(r"\d+", text or "")
    if match:
        return int(match.group())
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
                runs_text = cells[3].inner_text().strip()
                med_text = cells[5].inner_text().strip()

                runs = extract_number(runs_text)
                med = extract_number(med_text)

                if dungeon and runs is not None:
                    dungeon_stats[dungeon] = {
                        "runs": runs,
                        "med": med
                    }

            except Exception as e:
                print("Row parse error:", e)

        browser.close()

    print("Dungeon stats:", dungeon_stats)
    return dungeon_stats


def med_direction(old_med, new_med):
    if old_med is None or new_med is None:
        return "unknown"

    if new_med > old_med:
        return "went up"

    if new_med < old_med:
        return "went down"

    return "stayed the same"


def send_to_discord(changes):
    if not DISCORD_WEBHOOK_URL:
        print("No DISCORD_WEBHOOK_URL set.")
        return

    found_time = now_string()

    lines = [
        f"New M+ log detected for **{CHARACTER_NAME}-{SERVER_SLUG}**",
        f"Found at: **{found_time}**",
        "",
        "**Dungeon updates:**"
    ]

    for change in changes:
        dungeon = change["dungeon"]
        old_runs = change["old_runs"]
        new_runs = change["new_runs"]
        old_med = change["old_med"]
        new_med = change["new_med"]
        direction = med_direction(old_med, new_med)

        old_med_text = "N/A" if old_med is None else str(old_med)
        new_med_text = "N/A" if new_med is None else str(new_med)

        lines.append(
            f"- **{dungeon}** | Runs: **{old_runs} → {new_runs}** | Med: **{old_med_text} → {new_med_text}** ({direction})"
        )

    lines.append("")
    lines.append(CHARACTER_URL)

    payload = {
        "content": "\n".join(lines)
    }

    r = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        timeout=20
    )

    r.raise_for_status()

    print("Posted Discord update.")


def main():
    print("Watching:", CHARACTER_URL)

    seen = load_seen()

    if not seen:
        current = get_dungeon_stats()
        save_seen(current)
        print(f"First run complete. Saved {len(current)} dungeon rows.")
        seen = current

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
                send_to_discord(changes)
                save_seen(current)
                seen = current
            else:
                print("No new runs detected.")

        except Exception as e:
            print("ERROR:", e)

        time.sleep(CHECK_EVERY_SECONDS)


if __name__ == "__main__":
    main()
