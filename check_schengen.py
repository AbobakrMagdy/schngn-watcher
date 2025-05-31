#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup

# ─── DEBUGGING: Marker so we know this is the updated script ─────────────────
print("### DEBUG: check_schengen.py is running the updated version! ###")
# ────────────────────────────────────────────────────────────────────────────────

# ─── CONFIGURATION via environment variables ──────────────────────────────────
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
    """
    Send a Telegram message. 
    Uses parse_mode="Markdown" to reduce escaping issues.
    Wrap in try/except to log any errors Telegram returns.
    """
    if not TELEGRAM_TOKEN or not CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID environment variable")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",  # switched from MarkdownV2 to Markdown
    }
    try:
        resp = requests.post(url, data=payload, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        # Print the exact payload and response for debugging
        print("### ERROR: Telegram rejected the message ###")
        print(f"Payload was: {json.dumps(payload, ensure_ascii=False)}")
        print(f"Response: {e.response.status_code} → {e.response.text}")
        raise

def normalize_country_name(raw_name: str) -> str:
    """
    Strip out any non-letter characters (e.g., emojis, punctuation) from raw_name,
    returning only letters (A–Z, a–z) and spaces.
    Example: "Cyprus 🇨🇾" → "Cyprus"
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

    # ─── DEBUG: Collect all <tr> rows ───────────────────────────────────────────
    all_rows = soup.find_all("tr")
    print(f"### DEBUG: Found {len(all_rows)} <tr> rows in the rendered HTML ###")
    # ─────────────────────────────────────────────────────────────────────────────

    # ─── DEBUG: Print all normalized country names from <th> ────────────────────
    print("### DEBUG: Listing all normalized country names from <th> ###")
    for idx, row in enumerate(all_rows, start=1):
        th = row.find("th")
        if th:
            country_raw = th.get_text(strip=True)
            country_norm = normalize_country_name(country_raw)
            print(f"Row {idx:>2}: RAW-TH = '{country_raw}' → NORM = '{country_norm}'")
        else:
            print(f"Row {idx:>2}: <no <th> in this row>")
    print("### DEBUG: End of country list ###")
    # ─────────────────────────────────────────────────────────────────────────────

    last_state = load_last_state()
    prev_value = last_state.get(TARGET_COUNTRY, "")

    # Search for the specific country in the <th> cells
    found_country = False
    for row in all_rows:
        th = row.find("th")
        if not th:
            continue

        country_raw = th.get_text(strip=True)
        country_norm = normalize_country_name(country_raw)

        if country_norm.lower() == TARGET_COUNTRY.lower():
            found_country = True

            # Extract the earliest-available date f
