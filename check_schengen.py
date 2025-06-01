#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup

# ─── DEBUGGING: Marker so we know this version is running ─────────────────────
print("### DEBUG: check_schengen.py (multi-country, uncapped) is running the updated version! ###")
# ────────────────────────────────────────────────────────────────────────────────

# ─── CONFIGURATION via environment variables ──────────────────────────────────
CITY_SLUG        = os.getenv("CITY_SLUG", "dubai")          # e.g. "dubai"
VISA_TYPE        = os.getenv("VISA_TYPE", "tourism")
# Instead of a single TARGET_COUNTRY, read multiple comma-separated:
TARGET_COUNTRIES = os.getenv("TARGET_COUNTRIES", "Cyprus,Italy")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID          = os.getenv("CHAT_ID", "")
# We keep STATE_FILE to preserve per-run history if you like:
STATE_FILE       = os.getenv("STATE_FILE", os.path.expanduser("last_state.json"))
# ────────────────────────────────────────────────────────────────────────────────

def send_telegram(text: str):
    """
    Send a Telegram message with parse_mode='Markdown'.
    """
    if not TELEGRAM_TOKEN or not CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID environment variable")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    resp = requests.post(url, data=payload, timeout=10)
    resp.raise_for_status()

def normalize_country_name(raw_name: str) -> str:
    """
    Strip out any non-letter characters (emojis, punctuation) so:
    "Cyprus 🇨🇾" → "Cyprus", "Luxembourg" → "Luxembourg"
    """
    return "".join(ch for ch in raw_name if ch.isalpha() or ch.isspace()).strip()

def load_last_state():
    """
    Load a JSON file mapping country→last-seen date. If missing/invalid, return {}.
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
    Save the mapping country→last-seen date back to STATE_FILE.
    """
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def get_soup():
    """
    If 'rendered.html' exists (from Playwright), parse that. Otherwise do a simple HTTP GET.
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
    # Build a list of lowercase normalized target countries
    raw_list = [c.strip() for c in TARGET_COUNTRIES.split(",") if c.strip()]
    targets = [normalize_country_name(rc).lower() for rc in raw_list]

    if not targets:
        raise RuntimeError("TARGET_COUNTRIES is empty or invalid. Provide e.g. 'Cyprus,Italy'")

    print(f"### DEBUG: Monitoring these countries: {targets} ###")

    soup = get_soup()
    all_rows = soup.find_all("tr")
    print(f"### DEBUG: Found {len(all_rows)} <tr> rows in the rendered HTML ###")

    # Debug: list out each <th> row so you see what names appear
    print("### DEBUG: Listing all normalized country names from <th> ###")
    for idx, row in enumerate(all_rows, start=1):
        th = row.find("th")
        if th:
            raw_th = th.get_text(strip=True)
            norm_th = normalize_country_name(raw_th)
            print(f"Row {idx:>2}: RAW-TH = '{raw_th}' → NORM = '{norm_th}'")
        else:
            print(f"Row {idx:>2}: <no <th> in this row>")
    print("### DEBUG: End of country list ###")

    # Load previous state (country→last date)
    last_state = load_last_state()

    # Track if we found any of the targets at all:
    found_any = False

    for row in all_rows:
        th = row.find("th")
        if not th:
            continue

        raw_country = th.get_text(strip=True)
        norm_country = normalize_country_name(raw_country).lower()

        if norm_country in targets:
            found_any = True

            # Extract “Earliest Available” from <span class="font-bold">
            span = row.find("span", class_="font-bold")
            earliest_text = span.get_text(strip=True) if span else ""

            print(f"### DEBUG: {norm_country} earliest_text = '{earliest_text}' ###")

            # Uncapped: if earliest_text is non-empty and not “No availability”/“Waitlist Open”, send a message.
            if earliest_text and earliest_text not in ("No availability", "Waitlist Open"):
                message = (
                    f"🎉 *{raw_country}* slot detected in *{CITY_SLUG.title()}*!  \n"
                    f"🗓 *Earliest Available:* {earliest_text}  \n"
                    f"🔗 https://schengenappointments.com/in/{CITY_SLUG}/{VISA_TYPE}"
                )
                send_telegram(message)
            else:
                print(f"### DEBUG: No availability or waitlist for {raw_country}. No Telegram sent. ###")

            # Update our state (in case you want to inspect it later)
            last_state[norm_country] = earliest_text

    if not found_any:
        print(f"### DEBUG: None of the monitored countries ({targets}) were found in the table. ###")

    # Save state back to JSON
    save_last_state(last_state)

if __name__ == "__main__":
    try:
        check_slot()
    except Exception as e:
        print(f"[Error] {e}")
        exit(1)
