import os, re, json, time, requests
from playwright.sync_api import sync_playwright

CHARACTER_NAME = os.getenv("CHARACTER_NAME", "Snadius")
SERVER_SLUG = os.getenv("SERVER_SLUG", "proudmoore")
REGION = os.getenv("SERVER_REGION", "us")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
CHECK_EVERY_SECONDS = int(os.getenv("CHECK_EVERY_SECONDS", "300"))

SEEN_FILE = "seen_reports.json"
CHARACTER_URL = f"https://www.warcraftlogs.com/character/{REGION}/{SERVER_SLUG}/{CHARACTER_NAME.lower()}"


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
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(CHARACTER_URL, wait_until="networkidle", timeout=60000)

        html = page.content()
        browser.close()

    matches = re.findall(r"/reports/[A-Za-z0-9]+", html)

    for match in matches:
        links.add("https://www.warcraftlogs.com" + match)

    return links


def send_to_discord(link):
    message = {
        "content": f"New public Warcraft Logs report found for **{CHARACTER_NAME}-{SERVER_SLUG}**:\n{link}"
    }

    r = requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=20)
    r.raise_for_status()
    print("Posted:", link)


def main():
    print("Watching:", CHARACTER_URL)

    seen = load_seen()

    if len(seen) == 0:
        current_links = get_report_links()
        seen.update(current_links)
        save_seen(seen)
        print(f"First run complete. Marked {len(current_links)} existing links as seen.")

    while True:
        try:
            links = get_report_links()
            print(f"Found {len(links)} report links.")

            for link in links:
                if link not in seen:
                    send_to_discord(link)
                    seen.add(link)
                    save_seen(seen)

        except Exception as e:
            print("Error:", e)

        time.sleep(CHECK_EVERY_SECONDS)


if __name__ == "__main__":
    main()