#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup

# ─── CONFIGURATION ────────────────────────────────────────────────────────────────
# You can override these via environment variables in GitHub Actions.
CITY_SLUG      = os.getenv("CITY_SLUG", "dubai")         # e.g. "dubai", "abu-dhabi", "new-york"
VISA_TYPE      = os.getenv("VISA_TYPE", "tourism")       # "tourism" or "business"
TARGET_COUNTRY = os.getenv("TARGET_COUNTRY", "Luxembourg")  # Country to monitor

# Telegram Bot config (must be set as GitHub Secrets)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID        = os.getenv("CHAT_ID", "")

# Path to remember “last seen” availability. We’ll version this via GitHub Actions.
STATE_FILE = os.getenv("STATE_FILE", os.path.expanduser("last_state.json"))
# ────────────────────────────────────────────────────────────────────────────────────

def load_last_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_last_state(state: dict):
    # Ensure parent folder exists
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def send_telegram(text: str):
    """
    Uses the Telegram Bot API to send a message.
    Requires TELEGRAM_TOKEN & CHAT_ID to be non-empty.
    """
    if not TELEGRAM_TOKEN or not CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID in environment")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    resp = requests.post(url, data=payload, timeout=10)
    resp.raise_for_status()

def check_slot():
    """
    1) Fetch SchengenAppointments.com for CITY_SLUG + VISA_TYPE
    2) Find the row for TARGET_COUNTRY
    3) Read the “Earliest Available” column
    4) If it changed from last run to a real date/slot, send a Telegram alert
    5) Commit the new state
    """
    url = f"https://schengenappointments.com/in/{CITY_SLUG}/{VISA_TYPE}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        raise RuntimeError("Cannot find the appointments table on the page.")

    last_state = load_last_state()
    last_value = last_state.get(TARGET_COUNTRY, "")

    found = False
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        country = cells[0].get_text(strip=True)
        if country.lower() == TARGET_COUNTRY.lower():
            found = True
            earliest_text = cells[1].get_text(strip=True)  # “Earliest Available”
            # Notify only if it changed AND isn’t “No availability”/“Waitlist Open”
            if earliest_text != last_value:
                if earliest_text and earliest_text not in ("No availability", "Waitlist Open"):
                    message = (
                        f"🎉 *{TARGET_COUNTRY}* slot opened in *{CITY_SLUG.title()}*!  \n"
                        f"🗓  *Earliest Available:* `{earliest_text}`  \n"
                        f"🔗 https://schengenappointments.com/in/{CITY_SLUG}/{VISA_TYPE}"
                    )
                    send_telegram(message)
                # Update state (even if it went back to “No availability”)
                last_state[TARGET_COUNTRY] = earliest_text
                save_last_state(last_state)
            break

    if not found:
        raise RuntimeError(f"Country '{TARGET_COUNTRY}' not found at {url}")

if __name__ == "__main__":
    try:
        check_slot()
    except Exception as e:
        print(f"[Error] {e}")
        exit(1)

