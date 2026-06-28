"""
Fetches Big 5 league standings from football-data.org free API.
Computes Attack Strength and Defense Strength (same formula as LOOKOUT_BIG5_v3.xlsx).
Saves to data/league_data.json — read by dashboard.html on page load.

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

# football-data.org competition codes
LEAGUES = {
    "PL":  {"name": "Premier League", "country": "England", "code": "PL"},
    "PD":  {"name": "La Liga",         "country": "Spain",   "code": "PD"},
    "BL1": {"name": "Bundesliga",      "country": "Germany", "code": "BL1"},
    "SA":  {"name": "Serie A",         "country": "Italy",   "code": "SA"},
    "FL1": {"name": "Ligue 1",         "country": "France",  "code": "FL1"},
}


def get(endpoint):
    time.sleep(7)  # free tier: 10 requests/min
    r = requests.get(f"{BASE}{endpoint}", headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def compute_strength(table):
    """Att Str = (GF/G) / avg(GF/G), Def Str = (GA/G) / avg(GA/G) — same as the Excel model."""
    rows = [t for t in table if t["playedGames"] > 0]
    if not rows:
        return []
    avg_gf = sum(t["goalsFor"] / t["playedGames"] for t in rows) / len(rows)
    avg_ga = sum(t["goalsAgainst"] / t["playedGames"] for t in rows) / len(rows)

    result = []
    for t in rows:
        pld = t["playedGames"]
        gf_pg = t["goalsFor"] / pld
        ga_pg = t["goalsAgainst"] / pld
        result.append({
            "team":    t["team"]["name"],
            "tla":     t["team"].get("tla", ""),
            "crest":   t["team"].get("crest", ""),
            "pos":     t["position"],
            "pld":     pld,
            "w":       t["won"],
            "d":       t["draw"],
            "l":       t["lost"],
            "gf":      t["goalsFor"],
            "ga":      t["goalsAgainst"],
            "gd":      t["goalDifference"],
            "pts":     t["points"],
            "gf_pg":   round(gf_pg, 4),
            "ga_pg":   round(ga_pg, 4),
            "att_str": round(gf_pg / avg_gf, 6) if avg_gf > 0 else 1.0,
            "def_str": round(ga_pg / avg_ga, 6) if avg_ga > 0 else 1.0,
        })
    return result


def fetch_leagues():
    all_data = {"updated": datetime.now(timezone.utc).isoformat()}

    for key, meta in LEAGUES.items():
        print(f"  Fetching {meta['name']}...")
        try:
            resp = get(f"/competitions/{meta['code']}/standings")
            season_obj = resp.get("season", {})
            # e.g. "2026-08-21" → "2026" → "2026-27"
            start_year = season_obj.get("startDate", "")[:4]
            season_str = f"{start_year}-{str(int(start_year)+1)[2:]}" if start_year else "—"

            # standings list: take the TOTAL type (full table, not home/away split)
            standings_list = resp.get("standings", [])
            total = next((s for s in standings_list if s.get("type") == "TOTAL"), {})
            table = total.get("table", [])

            all_data[key] = {
                "name":    meta["name"],
                "country": meta["country"],
                "season":  season_str,
                "table":   compute_strength(table),
            }
            print(f"    {len(all_data[key]['table'])} teams, season {season_str}")

        except Exception as e:
            print(f"    Failed: {e}")

        # Top scorers (best effort)
        try:
            sc = get(f"/competitions/{meta['code']}/scorers?limit=10")
            if key in all_data:
                all_data[key]["scorers"] = [
                    {
                        "name":       s["player"]["name"],
                        "team":       s["team"]["name"],
                        "goals":      s["goals"],
                        "assists":    s.get("assists") or 0,
                        "penalties":  s.get("penalties") or 0,
                        "playedGames": s.get("playedGames") or 0,
                    }
                    for s in sc.get("scorers", [])
                ]
        except Exception as e:
            print(f"    Scorers failed: {e}")

    return all_data


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    print("Fetching Big 5 league data...")
    result = fetch_leagues()
    with open("data/league_data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"  Saved data/league_data.json ({os.path.getsize('data/league_data.json')//1024}KB)")
