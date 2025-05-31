#!/usr/bin/env python3
import os
import json
import requests
from bs4 import BeautifulSoup

# ─── DEBUGGING: Signal that this file is the new version ──────────────────────
print("### DEBUG: check_schengen.py is running the updated version! ###")
# ────────────────────────────────────────────────────────────────────────────────

# ─── CONFIGURATION ────────────────────────────────────────────────────────────────
CITY_SLUG      = os.getenv("CITY_SLUG", "dubai")
VISA_TYPE      = os.getenv("VISA_TYPE", "tourism")
TARGET_COUNTRY = os.getenv("TARGET_COUNTRY", "Luxembourg")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID        = os.getenv("CHAT_ID", "")
STATE_FILE     = os.getenv("STATE_FILE", os.path.expanduser("last_state.json"))
# ───────────────────────────────────────────────────────────────────────────────────

def load_last_state():
    …
def save_last_state(state: dict):
    …
def send_telegram(text: str):
    …
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
    …
