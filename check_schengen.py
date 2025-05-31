#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup

# ─── CONFIGURATION ────────────────────────────────────────────────────────────────
# These defaults can be overridden via environment variables (e.g., set in GitHub Actions).

CITY_SLUG      = os.getenv("CITY_SLUG", "dubai")         # e.g. "dubai", "abu-dhabi", "new-york"
VISA_TYPE      = os.getenv("VISA_TYPE", "tourism")       # "tourism" or "business"
TARGET_COUNTRY = os.getenv("TARGET_COUNTRY", "Luxembourg")  # Country you want to monitor

# Telegram Bot configuration (must be provided as environment variables / GitHub Secrets)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID        = os.getenv("CHAT_ID", "")

# Path to store “last seen” availability. By default, “last_state.json” in the repo root.
STATE_FILE = os.getenv("STATE_FILE", os.path.expanduser("last_state.json"))
# ────────────────────────────────────────────────────────────────────────────────────

def load_last_state():
    """
    Read the JSON file at STATE_FILE (if it exists) and return a dict.
    Returns {} if the file does not exist or cannot be parsed.
    """
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_last_state(state: dict):
    """
    Write the given dict to STATE_FILE as JSON, creating directories as needed.
    """
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def send_telegram(text: str):
    """
    Send a message via the Telegram Bot API.
    Requires TELEGRAM_TOKEN and CHAT_ID to be set in the environment.
    """
    if not TELEGRAM_TOKEN or not CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID in environment")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
    }
    resp = requests.post(url, data=payload, timeout=10)
    resp.raise_for_status()

def check_slot():
    """
    1) Fetch the SchengenAppointments page for CITY_SLUG + VISA_TYPE (e.g. dubai/tourism),
       using a realistic User-Agent so we get the actual table HTML.
    2) Grab every <tr> (table row) on the page and look for TARGET_COUNTRY in the first <td>.
    3) Read the “Earliest Available” text from the second <td> of that row.
    4) If that text changed from the last run—and is not “No availability” or “Waitlist Open”—send a Telegram alert.
    5) Update STATE_FILE with the new “Earliest Available” text.
    """

    url = f"https://schengenappointments.com/in/{CITY_SLUG}/{VISA_TYPE}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Load the previous run’s state
    last_state = load_last_state()
    prev_value = last_state.get(TARGET_COUNTRY, "")

    found_country = False

    # Iterate through every <tr> on the page
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        # We expect at least two <td> cells: [0]=Country, [1]=Earliest Available
        if len(cells) < 2:
            continue

        country_name = cells[0].get_text(strip=True)
        # Compare case-insensitive
        if country_name.lower() == TARGET_COUNTRY.lower():
            found_country = True
            earliest_text = cells[1].get_text(strip=True)

            # If the “Earliest Available” text changed:
            if earliest_text != prev_value:
                # Only alert when there's a real date/slot (not “No availability” or “Waitlist Open”)
                if earliest_text and earliest_text not in ("No availability", "Waitlist Open"):
                    message = (
                        f"🎉 *{TARGET_COUNTRY}* slot opened in *{CITY_SLUG.title()}*!  \n"
                        f"🗓  *Earliest Available:* `{earliest_text}`  \n"
                        f"🔗 {url}"
                    )
                    send_telegram(message)

                # Update state (even if it changed back to “No availability”)
                last_state[TARGET_COUNTRY] = earliest_text
                save_last_state(last_state)
            break

    if not found_country:
        raise RuntimeError(f"Country '{TARGET_COUNTRY}' not found at {url}")

if __name__ == "__main__":
    try:
        check_slot()
    except Exception as e:
        print(f"[Error] {e}")
        exit(1)
