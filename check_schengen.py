import os
import json
import requests
from bs4 import BeautifulSoup

# … (configuration as before) …

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

    # Previously: find all <tr> and compare…
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
            # … (same logic) …
            break

    if not found_country:
        raise RuntimeError(f"Country '{TARGET_COUNTRY}' not found at {url}")