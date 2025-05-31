#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup

# ─── DEBUG: Mark that this is the updated script ────────────────────────────────
print("### DEBUG: check_schengen.py is running the updated version! ###")
# ────────────────────────────────────────────────────────────────────────────────

# ─── CONFIGURATION (from environment) ────────────────────────────────────────────
CITY_SLUG      = os.getenv("CITY_SLUG", "dubai")
VISA_TYPE      = os.getenv("VISA_TYPE", "tourism")
TARGET_COUNTRY = os.getenv("TARGET_COUNTRY", "Cyprus")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID        = os.getenv("CHAT_ID", "")
STATE_FILE     = os.getenv("STATE_FILE", os.path.expanduser("last_state.json"))
# ────────────────────────────────────────────────────────────────────────────────

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
    keeping only letters (A–Z, a–z) and spaces.
    E.g., "Luxembourg 🇱🇺" → "Luxembourg"
    """
    return "".join(ch for ch in raw_name if ch.isalpha() or ch.isspace()).strip()

def get_soup():
    """
    If 'rendered.html' (from Playwright) exists, parse that. Otherwise, do a normal requests.get().
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

    # ─── DEBUG: find any <td> that contains the target country (case-insensitive) ───
    td_matches = []
    for td in soup.find_all("td"):
        text = td.get_text(strip=True)
        if TARGET_COUNTRY.lower() in text.lower():
            td_matches.append((td, text))
    print(f"### DEBUG: Found {len(td_matches)} <td> cells containing '{TARGET_COUNTRY}' ###")
    for idx, (td, raw) in enumerate(td_matches, start=1):
        norm = normalize_country_name(raw)
        print(f"Match {idx}: RAW = '{raw}' → NORM = '{norm}'")
    # ───────────────────────────────────────────────────────────────────────────────

    if not td_matches:
        raise RuntimeError(f"No <td> cell containing '{TARGET_COUNTRY}' found in rendered HTML")

    # Load previous state to compare
    last_state = load_last_state()
    prev_value = last_state.get(TARGET_COUNTRY, "")

    # We allow multiple matches, but typically there should be exactly one
    for td, raw_text in td_matches:
        # Climb up to the parent <tr>
        tr = td.find_parent("tr")
        if not tr:
            print("### DEBUG: <td> has no parent <tr>—skipping ###")
            continue

        cells = tr.find_all("td")
        # DEBUG: print the entire list of cells for this row
        cell_texts = [c.get_text(strip=True).replace("\n", " ") for c in cells]
        print(f"### DEBUG: Row cells = {cell_texts} ###")

        # Normalize the country name for matching
        country_norm = normalize_country_name(raw_text)
        if country_norm.lower() != TARGET_COUNTRY.lower():
            print(f"### DEBUG: Normalized '{country_norm}' != TARGET_COUNTRY '{TARGET_COUNTRY}'—skipping ###")
            continue

        # Determine which cell index holds the "Earliest Available" info.
        # Often, the second cell (index 1) is the "Earliest Available" date.
        # But let's print and then pick index 1 if it exists.
        if len(cells) < 2:
            print(f"### DEBUG: Not enough cells ({len(cells)}) in this <tr> to extract availability ###")
            continue

        earliest_text = cells[1].get_text(strip=True)
        print(f"### DEBUG: Earliest available for '{TARGET_COUNTRY}' = '{earliest_text}' ###")

        # Compare to previous value
        if earliest_text != prev_value:
            if earliest_text and earliest_text not in ("No availability", "Waitlist Open"):
                message = (
                    f"🎉 *{TARGET_COUNTRY}* slot opened in *{CITY_SLUG.title()}*!  \n"
                    f"🗓  *Earliest Available:* `{earliest_text}`  \n"
                    f"🔗 https://schengenappointments.com/in/{CITY_SLUG}/{VISA_TYPE}"
                )
                send_telegram(message)

            # Update state and save
            last_state[TARGET_COUNTRY] = earliest_text
            save_last_state(last_state)
        return

    # If we fell out of the loop without finding a valid match:
    raise RuntimeError(f"Country '{TARGET_COUNTRY}' not matched after normalization in rendered HTML")

if __name__ == "__main__":
    try:
        check_slot()
    except Exception as e:
        print(f"[Error] {e}")
        exit(1)
