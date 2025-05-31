#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup

# ─── DEBUGGING: Marker so we know this is the updated script ───────────────
print("### DEBUG: check_schengen.py is running the updated version! ###")
# ──────────────────────────────────────────────────────────────────────────────

# ─── CONFIGURATION via environment variables ──────────────────────────────────
CITY_SLUG      = os.getenv("CITY_SLUG", "dubai")
VISA_TYPE      = os.getenv("VISA_TYPE", "tourism")
TARGET_COUNTRY = os.getenv("TARGET_COUNTRY", "Luxembourg")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID        = os.getenv("CHAT_ID", "")
STATE_FILE     = os.getenv("STATE_FILE", os.path.expanduser("last_state.json"))
# ───────────────────────────────────────────────────────────────────────────────

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
        raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID environment variable")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
    }
    resp = requests.post(url, data=payload, timeout=10)
    resp.raise_for_status()

def normalize_country_name(raw_name: str) -> str:
    """
    Strip out any non-letter characters (e.g., emojis, punctuation) from raw_name,
    returning only letters (A–Z, a–z) and spaces.
    Example: "Luxembourg 🇱🇺" → "Luxembourg"
    """
    return "".join(ch for ch in raw_name if ch.isalpha() or ch.isspace()).strip()

def get_soup():
    """
    If 'rendered.html' (produced by Playwright) exists, parse that.
    Otherwise, do a normal HTTP GET (useful for local testing).
    """
    if os.path.exists("rendered.html"):
        print("### DEBUG: using rendered.html instead of HTTP GET ###")
        with open("rendered.html", "r", encoding="utf-8") as f:
            html = f.read()
    else:
        print("### DEBUG: performing HTTP GET to fetch HTML ###")
        url = f"https://schengenappointments.com/in/{CITY_SLUG}/{VISA_TYPE}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        html = resp.text

    return BeautifulSoup(html, "html.parser")

def check_slot():
    soup = get_soup()

    # ─── DEBUG: Collect all <tr> rows ─────────────────────────────────────────────
    all_rows = soup.find_all("tr")
    print(f"### DEBUG: Found {len(all_rows)} <tr> rows in the rendered HTML ###")
    # ────────────────────────────────────────────────────────────────────────────────

    # ─── DEBUG: Print out every row's <td> contents as a list ───────────────────
    print("### DEBUG: Listing all <tr> rows with their <td> cell texts ###")
    for idx, row in enumerate(all_rows, start=1):
        cells = row.find_all("td")
        # Extract the visible text from each <td>, stripping whitespace/newlines
        cell_texts = [cell.get_text(strip=True) for cell in cells]
        print(f"Row {idx:>2}: cells={cell_texts}")
    print("### DEBUG: End of <tr> list ###")
    # ────────────────────────────────────────────────────────────────────────────────

    last_state = load_last_state()
    prev_value = last_state.get(TARGET_COUNTRY, "")

    found_country = False
    # Attempt to match on the first column (index 0). If needed, change to another index.
    for row in all_rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        country_raw = cells[0].get_text(strip=True)
        country_norm = normalize_country_name(country_raw)

        if country_norm.lower() == TARGET_COUNTRY.lower():
            found_country = True
            earliest_text = cells[1].get_text(strip=True)

            if earliest_text != prev_value:
                # Only notify if it's not empty/No availability/Waitlist Open
                if earliest_text and earliest_text not in ("No availability", "Waitlist Open"):
                    message = (
                        f"🎉 *{TARGET_COUNTRY}* slot opened in *{CITY_SLUG.title()}*!  \n"
                        f"🗓  *Earliest Available:* `{earliest_text}`  \n"
                        f"🔗 https://schengenappointments.com/in/{CITY_SLUG}/{VISA_TYPE}"
                    )
                    send_telegram(message)
                last_state[TARGET_COUNTRY] = earliest_text
                save_last_state(last_state)
            break

    if not found_country:
        raise RuntimeError(f"Country '{TARGET_COUNTRY}' not found in rendered HTML")

if __name__ == "__main__":
    try:
        check_slot()
    except Exception as e:
        print(f"[Error] {e}")
        exit(1)
