#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup

# ─── CONFIGURATION ────────────────────────────────────────────────────────────────
# These can be overridden via environment variables (e.g., in GitHub Actions).
CITY_SLUG      = os.getenv("CITY_SLUG", "dubai")         # e.g. "dubai", "abu-dhabi", "new-york"
VISA_TYPE      = os.getenv("VISA_TYPE", "tourism")       # "tourism" or "business"
TARGET_COUNTRY = os.getenv("TARGET_COUNTRY", "Luxembourg")  # Country to watch

# Telegram Bot configuration (these must be set via environment variables/secrets)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID        = os.getenv("CHAT_ID", "")

# Where to store “last seen” availability state. Normally "last_state.json" in the repo root.
STATE_FILE = os.getenv("STATE_FILE", os.path.expanduser("last_state.json"))
# ────────────────────────────────────────────────────────────────────────────────────

def load_last_state():
    """
    Reads the JSON file at STATE_FILE (if it exists) and returns a dict.
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
    Writes the given dict to STATE_FILE as JSON, creating directories as needed.
    """
    os.makedirs(os.path.dirname(STATE_FILE) or ".", exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def send_telegram(text: str):
    """
    Sends a message via the Telegram Bot API.
    Requires TELEGRAM_TOKEN and CHAT_ID to be non-empty strings.
    """
    if not TELEGRAM_TOKEN or not CHAT_ID:
        raise RuntimeError("Missing TELEGRAM_TOKEN or CHAT_ID in environment")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    resp = requests.post(url, data=payload, timeout=10)
    resp.raise_for_status()

def check_slot():
    """
    1) Fetches the SchengenAppointments page for CITY_SLUG + VISA_TYPE
    2) Locates the table row for TARGET_COUNTRY
    3) Reads the “Earliest Available” column text
    4) If it has changed from the last run and is not “No availability”/“Waitlist Open”,
       sends a Telegram alert
    5) Updates STATE_FI_
