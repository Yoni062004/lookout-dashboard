"""
Fetches FIFA World Cup 2026 live data from football-data.org free API.
Saves to data/wc_data.json — read by dashboard.html on page load.

Also computes live Att/Def Strength from actual WC match performances,
blended with qualifying stats so predictions improve as the tournament progresses.

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
WC_CODE = "WC"

# Maps football-data.org team names → WC26 array names in dashboard.html
# Only entries that differ need to be listed here.
API_NAME_TO_WC26 = {
    "United States":          "USA",
    "Korea Republic":         "South Korea",
    "IR Iran":                "Iran",
    "Bosnia-Herzegovina":     "Bosnia and Herz.",
    "Bosnia and Herzegovina": "Bosnia and Herz.",
    "Democratic Republic of Congo": "Congo DR",
    "Congo":                  "Congo DR",
    "Ivory Coast":            "Côte d'Ivoire",
    "Curacao":                "Curaçao",
    "New Zealand":            "New Zealand",
}


def get(endpoint):
    time.sleep(7)  # respect free-tier 10 req/min limit
    r = requests.get(f"{BASE}{endpoint}", headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def compute_wc_strength(standings_data):
    """
    Compute Att/Def Str from actual WC goals scored.
    Formula: same as the Excel model — (GF/game) / avg(GF/game across all teams).

    Returns dict keyed by WC26 team name:
      { 'Argentina': { att_str, def_str, pld, gf, ga }, ... }
    """
    all_teams = []
    for group in standings_data.get("standings", []):
        if group.get("type") != "TOTAL":
            continue
        for entry in group.get("table", []):
            pld = entry["playedGames"]
            if pld == 0:
                continue
            raw_name = entry["team"]["name"]
            name = API_NAME_TO_WC26.get(raw_name, raw_name)
            all_teams.append({
                "name": name,
                "pld":  pld,
                "gf":   entry["goalsFor"],
                "ga":   entry["goalsAgainst"],
            })

    if not all_teams:
        return {}

    avg_gf = sum(t["gf"] / t["pld"] for t in all_teams) / len(all_teams)
    avg_ga = sum(t["ga"] / t["pld"] for t in all_teams) / len(all_teams)

    strengths = {}
    for t in all_teams:
        gf_pg = t["gf"] / t["pld"]
        ga_pg = t["ga"] / t["pld"]
        strengths[t["name"]] = {
            "att_str": round(gf_pg / avg_gf, 6) if avg_gf > 0 else 1.0,
            "def_str": round(ga_pg / avg_ga, 6) if avg_ga > 0 else 1.0,
            "pld": t["pld"],
            "gf":  t["gf"],
            "ga":  t["ga"],
        }

    print(f"  WC strength computed for {len(strengths)} teams (avg GF/g={avg_gf:.3f}, GA/g={avg_ga:.3f})")
    return strengths


def fetch_wc():
    data = {"updated": datetime.now(timezone.utc).isoformat()}

    # Group standings + live Att/Def Str
    try:
        standings = get(f"/competitions/{WC_CODE}/standings")
        data["standings"] = standings
        data["team_strengths"] = compute_wc_strength(standings)
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
