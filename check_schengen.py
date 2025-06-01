#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup

# ─── DEBUGGING: Marker so we know this version is running ─────────────────────
print("### DEBUG: check_schengen.py (multi-country, strict availability) ###")
# ────────────────────────────────────────────────────────────────────────────────

# ─── CONFIGURATION via environment variables ──────────────────────────────────
CITY_SLUG        = os.getenv("CITY_SLUG", "dubai")
VISA_TYPE        = os.getenv("VISA_TYPE", "tourism")
TARGET_COUNTRIES = os.getenv("TARGET_COUNTRIES", "Cyprus,Italy,Luxembourg")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID          = os.getenv("CHAT_ID", "")
STATE_FILE       = os.getenv("STATE_FILE", os.path.expanduser("last_state.json"))
# ────────────────────────────────────────────────────────────────────────────────

def send_telegram(text: str):
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
    return "".join(ch for ch in raw_name if ch.isalpha() or ch.isspace()).strip()

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

def get_soup():
    rendered_filename = f"rendered_{CITY_SLUG}.html"
    if os.path.exists(rendered_filename):
        print(f"### DEBUG: using {rendered_filename} instead of HTTP GET ###")
        with open(rendered_filename, "r", encoding="utf-8") as f:
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
    # Build a lowercase list of target countries
    raw_list = [c.strip() for c in TARGET_COUNTRIES.split(",") if c.strip()]
    targets = [normalize_country_name(rc).lower() for rc in raw_list]
    if not targets:
        raise RuntimeError("TARGET_COUNTRIES is empty or invalid. Provide e.g. 'Cyprus,Italy'")

    print(f"### DEBUG: Monitoring these countries: {targets} ###")

    soup = get_soup()
    all_rows = soup.find_all("tr")
    print(f"### DEBUG: Found {len(all_rows)} <tr> rows in rendered_{CITY_SLUG}.html ###")

    # Debug: list out each <th> → normalized country
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

    last_state = load_last_state()
    found_any = False

    for row in all_rows:
        th = row.find("th")
        if not th:
            continue

        raw_country = th.get_text(strip=True)
        norm_country = normalize_country_name(raw_country).lower()

        if norm_country in targets:
            found_any = True

            # Look only for <span class="font-bold">…</span>
            span = row.find("span", class_="font-bold")
            if not span:
                # No <span class="font-bold"> means “No availability” or tooltip-only
                print(f"### DEBUG: {raw_country} has NO <span class='font-bold'> => no availability ###")
                earliest_text = ""  # treat as no availability
            else:
                earliest_text = span.get_text(strip=True)
                print(f"### DEBUG: {norm_country} earliest_text = '{earliest_text}' ###")

            # Notify strictly when we saw a <span class="font-bold">—
            # that covers both dates (e.g. "03 Jun") and "Waitlist Open".
            if span and earliest_text:
                message = (
                    f"🎉 *{raw_country}* slot status in *{CITY_SLUG.title()}*!  \n"
                    f"🗓 *Status:* {earliest_text}  \n"
                    f"🔗 https://schengenappointments.com/in/{CITY_SLUG}/{VISA_TYPE}"
                )
                send_telegram(message)
            else:
                print(f"### DEBUG: {raw_country} has no availability (no <span class='font-bold'>) ###")

            # Update state (for record; we’re not gating on it)
            last_state[norm_country] = earliest_text

    if not found_any:
        print(f"### DEBUG: None of the monitored countries ({targets}) were found on the page. ###")

    save_last_state(last_state)

if __name__ == "__main__":
    try:
        check_slot()
    except Exception as e:
        print(f"[Error] {e}")
        exit(1)
