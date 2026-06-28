"""
Fetches FIFA World Cup 2026 live data from football-data.org free API.
Saves to data/wc_data.json — read by dashboard.html on page load.

Requires env: FOOTBALL_DATA_API_KEY
Register free at: https://www.football-data.org/client/register
"""

import json
import os
import time
from datetime import datetime, timezone

import requests

API_KEY = os.environ.get("FOOTBALL_DATA_API_KEY", "")
BASE = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY}
WC_CODE = "WC"  # football-data.org competition code for World Cup


def get(endpoint):
    time.sleep(7)  # respect free-tier 10 req/min limit
    r = requests.get(f"{BASE}{endpoint}", headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_wc():
    data = {"updated": datetime.now(timezone.utc).isoformat()}

    # Group standings
    try:
        standings = get(f"/competitions/{WC_CODE}/standings")
        data["standings"] = standings
        print(f"  Standings: {len(standings.get('standings', []))} groups")
    except Exception as e:
        print(f"  Standings failed: {e}")

    # All matches (results + upcoming)
    try:
        matches = get(f"/competitions/{WC_CODE}/matches")
        data["matches"] = matches
        played = [m for m in matches.get("matches", []) if m["status"] == "FINISHED"]
        print(f"  Matches: {len(matches.get('matches', []))} total, {len(played)} played")
    except Exception as e:
        print(f"  Matches failed: {e}")

    # Top scorers
    try:
        scorers = get(f"/competitions/{WC_CODE}/scorers?limit=20")
        data["scorers"] = scorers
        print(f"  Scorers: {len(scorers.get('scorers', []))} entries")
    except Exception as e:
        print(f"  Scorers failed: {e}")

    return data


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    print("Fetching WC 2026 data...")
    result = fetch_wc()
    with open("data/wc_data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"  Saved data/wc_data.json ({os.path.getsize('data/wc_data.json')//1024}KB)")
