#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup

# ─── DEBUGGING: Marker so we know this version is running ─────────────────────
print("### DEBUG: check_schengen.py (multi-country, uncapped) is running ###")
# ───────────────────────────────────────────────────────────────────────────────

# ─── CONFIGURATION via environment variables ──────────────────────────────────
CITY_SLUG        = os.getenv("CITY_SLUG", "dubai")           # e.g. "dubai" or "abu-dhabi"
VISA_TYPE        = os.getenv("VISA_TYPE", "tourism")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID          = os.getenv("CHAT_ID", "")
STATE_FILE       = os.getenv("STATE_FILE", "last_state.json")
TARGET_COUNTRIES = os.getenv("TARGET_COUNTRIES", "")         # e.g. "Cyprus,Italy,Luxembourg"
# ────────────────────────────────────────────────────────────────────────────────

def normalize_country_name(raw_name: str) -> str:
    """
    Strip out any non-letter characters (e.g., emojis, punctuation) from raw_name,
    returning only letters (A–Z, a–z) and spaces.
    Examples:
      "Cyprus 🇨🇾"       → "Cyprus"
      "Luxembourg"      → "Luxembourg"
      "United Kingdom🇬🇧" → "United Kingdom"
    """
    return "".join(ch for ch in raw_name if ch.isalpha() or ch.isspace()).strip()

def send_telegram(text: str):
    """
    Send a Telegram message using parse_mode='Markdown' for simplicity.
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

def load_last_state():
    """
    Load the city-specific JSON state file (mapping country → last date).
    If it doesn’t exist or is invalid JSON, return an empty dict.
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
    Save the dictionary state (country → last date) back to STATE_FILE.
    """
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def get_soup():
    """
    If “rendered_<city>.html” exists, parse that. Otherwise, fall back to HTTP GET.
    """
    rendered_filename = f"rendered_{CITY_SLUG}.html"
    if os.path.exists(rendered_filename):
        print(f"### DEBUG: using {rendered_filename} instead of HTTP GET ###")
        with open(rendered_filename, "r", encoding="utf-8") as f:
            html = f.read()
    else:
        print("### DEBUG: performing HTTP GET (local test) ###")
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
    # Build the list of target countries, normalized to lowercase
    countries = [
        normalize_country_name(raw).lower()
        for raw in TARGET_COUNTRIES.split(",")
        if raw.strip()
    ]
    if not countries:
        raise RuntimeError("TARGET_COUNTRIES is empty or invalid. Provide a comma-separated list.")

    print(f"### DEBUG: Monitoring these countries (normalized): {countries} ###")

    soup = get_soup()
    all_rows = soup.find_all("tr")
    print(f"### DEBUG: Found {len(all_rows)} <tr> rows in rendered_{CITY_SLUG}.html ###")

    # Debug: list every normalized country in <th> so we can see what’s on the page
    print("### DEBUG: Listing all <th> → normalized country names ###")
    for idx, row in enumerate(all_rows, start=1):
        th = row.find("th")
        if th:
            raw_th = th.get_text(strip=True)
            norm_th = normalize_country_name(raw_th)
            print(f"Row {idx:>2}: RAW-TH = '{raw_th}' → NORM = '{norm_th}'")
        else:
            print(f"Row {idx:>2}: <no <th> in this row>")
    print("### DEBUG: End of country list ###")

    # Load or create the state dictionary (country → last date)
    last_state = load_last_state()

    # Track whether we found at least one monitored country
    found_any = False

    for row in all_rows:
        th = row.find("th")
        if not th:
            continue

        raw_country = th.get_text(strip=True)
        norm_country = normalize_country_name(raw_country).lower()

        if norm_country in countries:
            found_any = True
            # Extract "Earliest Available" from <span class="font-bold">
            span = row.find("span", class_="font-bold")
            earliest_text = span.get_text(strip=True) if span else ""

            print(f"### DEBUG: For city={CITY_SLUG}, country='{norm_country}', earliest_text = '{earliest_text}' ###")

            # Uncapped: if earliest_text is non-empty and not "No availability"/"Waitlist Open", send Telegram
            if earliest_text and earliest_text not in ("No availability", "Waitlist Open"):
                message = (
                    f"🎉 *{raw_country}* slot detected in *{CITY_SLUG.title()}*!  \n"
                    f"🗓 *Earliest Available:* {earliest_text}  \n"
                    f"🔗 https://schengenappointments.com/in/{CITY_SLUG}/{VISA_TYPE}"
                )
                send_telegram(message)
            else:
                print(f"### DEBUG: {CITY_SLUG} → '{raw_country}' has no availability or is waitlisted.# No Telegram sent.")

            # Update the state file (if you want to keep a history)
            last_state[norm_country] = earliest_text

    if not found_any:
        print(f"### DEBUG: None of the monitored countries {countries} were found on the page. ###")

    # Save the updated state (even if it’s identical or empty)
    save_last_state(last_state)

if __name__ == "__main__":
    try:
        check_slot()
    except Exception as e:
        print(f"[Error] {e}")
        exit(1)
