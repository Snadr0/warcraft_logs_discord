import os
import time
import json
import requests

WCL_CLIENT_ID = os.getenv("WCL_CLIENT_ID")
WCL_CLIENT_SECRET = os.getenv("WCL_CLIENT_SECRET")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

CHARACTER_NAME = os.getenv("CHARACTER_NAME")
SERVER_SLUG = os.getenv("SERVER_SLUG", "proudmoore")
SERVER_REGION = os.getenv("SERVER_REGION", "us")

CHECK_EVERY_SECONDS = int(os.getenv("CHECK_EVERY_SECONDS", "300"))
SEEN_FILE = "seen_reports.json"

WCL_TOKEN_URL = "https://www.warcraftlogs.com/oauth/token"
WCL_API_URL = "https://www.warcraftlogs.com/api/v2/client"


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()

    with open(SEEN_FILE, "r") as file:
        return set(json.load(file))


def save_seen(seen):
    with open(SEEN_FILE, "w") as file:
        json.dump(list(seen), file)


def get_token():
    response = requests.post(
        WCL_TOKEN_URL,
        data={"grant_type": "client_credentials"},
        auth=(WCL_CLIENT_ID, WCL_CLIENT_SECRET),
        timeout=20
    )

    response.raise_for_status()
    return response.json()["access_token"]


def graphql(query, variables):
    token = get_token()

    response = requests.post(
        WCL_API_URL,
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "variables": variables},
        timeout=30
    )

    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        print("GRAPHQL ERRORS:")
        print(json.dumps(data["errors"], indent=2))
        raise Exception(data["errors"])

    return data["data"]


def get_character_report_codes():
    query = """
    query($name: String!, $serverSlug: String!, $serverRegion: String!) {
      characterData {
        character(name: $name, serverSlug: $serverSlug, serverRegion: $serverRegion) {
          id
          canonicalID
          name
          server {
            name
            slug
            region {
              name
              compactName
            }
          }
          zoneRankings
        }
      }
    }
    """

    variables = {
        "name": CHARACTER_NAME,
        "serverSlug": SERVER_SLUG,
        "serverRegion": SERVER_REGION
    }

    print("Checking character with variables:")
    print(json.dumps(variables, indent=2))

    data = graphql(query, variables)

    print("DEBUG characterData:")
    print(json.dumps(data, indent=2)[:4000])

    character = data["characterData"]["character"]

    if character is None:
        print("Character not found.")
        return []

    rankings = character.get("zoneRankings")
    report_codes = set()

    def find_report_codes(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "report" and isinstance(value, dict):
                    print("Found report field:")
                    print(value)

                    code = value.get("code")
                    if code:
                        report_codes.add(code)
                else:
                    find_report_codes(value)

        elif isinstance(obj, list):
            for item in obj:
                find_report_codes(item)

    find_report_codes(rankings)

    print("DEBUG report codes found:", report_codes)
    return list(report_codes)


def get_report_title(report_code):
    query = """
    query($code: String!) {
      reportData {
        report(code: $code) {
          title
          startTime
        }
      }
    }
    """

    data = graphql(query, {"code": report_code})
    report = data["reportData"]["report"]

    if report:
        return report["title"]

    return "Warcraft Logs Report"


def send_to_discord(report_code):
    title = get_report_title(report_code)
    link = f"https://www.warcraftlogs.com/reports/{report_code}"

    message = {
        "content": (
            f"New Warcraft Logs report found for **{CHARACTER_NAME}-{SERVER_SLUG}**\n"
            f"**{title}**\n"
            f"{link}"
        )
    }

    response = requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=20)
    response.raise_for_status()

    print("Posted to Discord:", link)


def first_run_setup(seen):
    report_codes = get_character_report_codes()

    for code in report_codes:
        seen.add(code)

    save_seen(seen)
    print(f"First run complete. Marked {len(report_codes)} existing reports as seen.")


def main():
    print("Bot started.")
    print("Character:", CHARACTER_NAME)
    print("Server:", SERVER_SLUG)
    print("Region:", SERVER_REGION)

    seen = load_seen()

    if len(seen) == 0:
        first_run_setup(seen)

    while True:
        try:
            report_codes = get_character_report_codes()

            for code in report_codes:
                if code not in seen:
                    send_to_discord(code)
                    seen.add(code)
                    save_seen(seen)

        except Exception as error:
            print("Error:", error)

        time.sleep(CHECK_EVERY_SECONDS)


if __name__ == "__main__":
    main()