import os
import re
import json
import time
import requests

CHARACTER_NAME = os.getenv("CHARACTER_NAME", "Snadius")
SERVER_SLUG = os.getenv("SERVER_SLUG", "proudmoore")
REGION = os.getenv("SERVER_REGION", "us")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CHECK_EVERY_SECONDS = int(os.getenv("CHECK_EVERY_SECONDS", "300"))

SEEN_FILE = "seen_reports.json"

CHARACTER_URL = (
    f"https://www.warcraftlogs.com/character/"
    f"{REGION}/{SERVER_SLUG}/{CHARACTER_NAME.lower()}?zone=47"
)


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()

    with open(SEEN_FILE, "r") as f:
        return set(json.load(f))


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def get_report_links():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    r = requests.get(
        CHARACTER_URL,
        headers=headers,
        timeout=30
    )

    r.raise_for_status()

    html = r.text

    matches = re.findall(
        r'/reports/([A-Za-z0-9]+)',
        html
    )

    links = set()

    for code in matches:
        links.add(
            f"https://www.warcraftlogs.com/reports/{code}"
        )

    return links


def send_to_discord(link):
    payload = {
        "content":
        f"New M+ public log for **{CHARACTER_NAME}-{SERVER_SLUG}**\n{link}"
    }

    r = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload,
        timeout=20
    )

    r.raise_for_status()
    print("Posted:", link)


def main():
    print("Watching:", CHARACTER_URL)

    seen = load_seen()

    if len(seen) == 0:
        links = get_report_links()

        seen.update(links)
        save_seen(seen)

        print(
            f"First run complete. Marked {len(links)} existing links as seen."
        )

    while True:
        try:
            links = get_report_links()

            print(
                f"Found {len(links)} links."
            )

            for link in links:
                if link not in seen:
                    send_to_discord(link)

                    seen.add(link)
                    save_seen(seen)

        except Exception as e:
            print("ERROR:", e)

        time.sleep(CHECK_EVERY_SECONDS)


if __name__ == "__main__":
    main()