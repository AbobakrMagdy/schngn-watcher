#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup

# ─── CONFIGURATION ────────────────────────────────────────────────────────────────
# These can be overridden via environment variables, especially in GitHub Actions.

CITY_SLUG      = os.getenv("CITY_SLUG", "dubai")         # e.g. "dubai", "abu-dhabi", "new-york"
VISA_TYPE      = os.getenv("VISA_TYPE", "tourism")       # "tourism" or "business"
TARGET_COUNTRY = os.getenv("TARGET_COUNTRY", "Luxembourg")  # Country to monitor

# Telegram Bot configuration (must be set via environment variables / GitHub Secrets)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID        = os.getenv("CHAT_ID", "")

# Where to store “last seen” availability. By default, “last_state.json” in the repo root.
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
        "parse_mode": "MarkdownV2",  # Use MarkdownV2 in case you want to bold or escape characters
    }
    resp = requests.post(url, data=payload, timeout=10)
    resp.raise_for_status()

def check_slot():
    """
    1) Fetch the SchengenAppointments page for CITY_SLUG + VISA_TYPE (e.g. dubai/tourism),
       using a User-Agent header so the site returns the actual table.
    2) Locate the <table> that lists “Destination Country” vs “Earliest Available”.
    3) Find the row where the country==TARGET_COUNTRY.
    4) Read the “Earliest Available” text from that row.
    5) If it changed from the last run AND is not “No availability”/“Waitlist Open”,
       send a Telegram alert.
    6) Update STATE_FILE with the new “Earliest Available” text.
    """

    # Build the URL strictly as: https://schengenappointments.com/in/{CITY_SLUG}/{VISA_TYPE}
    url = f"https://schengenappointments.com/in/{CITY_SLUG}/{VISA_TYPE}"

    # Use a real-browser User-Agent to avoid any bot-detection or fallback pages
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Find the first <table> on the page whose header row contains "Destination" or "Country"
    # (This covers cases where the site may have more than one <table> element.)
    table = None
    for tbl in soup.find_all("table"):
        header_row = tbl.find("tr")
        if not header_row:
            continue
        header_cells = [th.get_text(strip=True).lower() for th in header_row.find_all(("th", "td"))]
        # We expect a header row that includes “Destination” or “Country”
        if any("country" in h for h in header_cells) or any("destination" in h for h in header_cells):
            table = tbl
            break

    if not table:
        raise RuntimeError("Could not find the appointments table on the page.")

    # Load the previous run’s state: { "Luxembourg": "No availability", ... }
    last_state = load_last_state()
    last_value = last_state.get(TARGET_COUNTRY, "")

    found_country = False
    # Skip the header row. Start searching from the second <tr> onward:
    for row in table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if not cells or len(cells) < 2:
            continue
        country_name = cells[0].get_text(strip=True)
        # Compare case-insensitive
        if country_name.lower() == TARGET_COUNTRY.lower():
            found_country = True
            earliest_text = cells[1].get_text(strip=True)  # “Earliest Available”

            # If the “Earliest Available” text changed from last run:
            if earliest_text != last_value:
                # Only fire alert when there’s a real date/slot, not “No availability” or “Waitlist Open”
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
        # If the site removed that country row or spelled it differently, inform us
        raise RuntimeError(f"Country '{TARGET_COUNTRY}' not found at {url}")

if __name__ == "__main__":
    try:
        check_slot()
    except Exception as e:
        # Print errors so they show up in the GitHub Actions logs (or your local terminal)
        print(f"[Error] {e}")
        exit(1)
