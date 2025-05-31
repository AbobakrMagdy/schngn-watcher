#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup

# ─── CONFIGURATION ────────────────────────────────────────────────────────────────
CITY_SLUG      = os.getenv("CITY_SLUG", "dubai")
VISA_TYPE      = os.getenv("VISA_TYPE", "tourism")
TARGET_COUNTRY = os.getenv("TARGET_COUNTRY", "Luxembourg")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID        = os.getenv("CHAT_ID", "")
STATE_FILE     = os.getenv("STATE_FILE", os.path.expanduser("last_state.json"))
# ────────────────────────────────────────────────────────────────────────────────────

def load_last_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_last_state(state: dict):
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def send_telegram(text: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
    }
    resp = requests.post(url, data=payload, timeout=10)
    resp.raise_for_status()

def check_slot():
    url = f"https://schengenappointments.com/in/{CITY_SLUG}/{VISA_TYPE}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    # ─── DEBUGGING: Print out the first 2000 characters of the HTML to logs ───
    print("\n\n========== HTML received (first 2000 chars) ==========\n")
    print(resp.text[:2000])
    print("\n\n========== End of snippet ==========\n")
    # ───────────────────────────────────────────────────────────────────────────

    soup = BeautifulSoup(resp.text, "html.parser")
    last_state = load_last_state()
    prev_value = last_state.get(TARGET_COUNTRY, "")

    found_country = False
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        country_name = cells[0].get_text(strip=True)
        if country_name.lower() == TARGET_COUNTRY.lower():
            found_country = True
            earliest_text = cells[1].get_text(strip=True)
            if earliest_text != prev_value:
                if earliest_text and earliest_text not in ("No availability", "Waitlist Open"):
                    message = (
                        f"🎉 *{TARGET_COUNTRY}* slot opened in *{CITY_SLUG.title()}*!  \n"
                        f"🗓  *Earliest Available:* `{earliest_text}`  \n"
                        f"🔗 {url}"
                    )
                    send_telegram(message)
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
