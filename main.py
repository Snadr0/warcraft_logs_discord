import os
import re
import json
import time
import requests
from playwright.sync_api import sync_playwright

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
    links = set()

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        api_data = []

        def capture_response(response):
            try:
                url = response.url

                if "warcraftlogs" in url:
                    text = response.text()

                    api_data.append(text)

            except:
                pass

        page.on(
            "response",
            capture_response
        )

        page.goto(
            CHARACTER_URL,
            wait_until="networkidle",
            timeout=60000
        )

        page.wait_for_timeout(8000)

        html = page.content()

        browser.close()

        all_content = html + "\n".join(api_data)

        print(
            "Combined content length:",
            len(all_content)
        )

        matches = re.findall(
            r"/reports/([A-Za-z0-9]+)",
            all_content
        )

        for code in matches:
            links.add(
                f"https://www.warcraftlogs.com/reports/{code}"
            )

        print(
            f"Found {len(links)} links"
        )

    return links


def send_to_discord(link):

    payload = {
        "content":
        f"New M+ public log for **{CHARACTER_NAME}-{SERVER_SLUG}**\n{link}"
    }

    r = requests.post(
        DISCORD_WEBHOOK_URL,
        json=payload
    )

    r.raise_for_status()

    print(
        "Posted:",
        link
    )


def main():

    print(
        "Watching:",
        CHARACTER_URL
    )

    seen = load_seen()

    if len(seen) == 0:

        current_links = get_report_links()

        seen.update(
            current_links
        )

        save_seen(
            seen
        )

        print(
            f"First run complete. Marked {len(current_links)} existing links as seen."
        )

    while True:

        try:

            links = get_report_links()

            for link in links:

                if link not in seen:

                    send_to_discord(
                        link
                    )

                    seen.add(
                        link
                    )

                    save_seen(
                        seen
                    )

        except Exception as e:

            print(
                "ERROR:",
                e
            )

        time.sleep(
            CHECK_EVERY_SECONDS
        )


if __name__ == "__main__":
    main()