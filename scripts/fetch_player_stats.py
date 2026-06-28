"""
Fetches Big 5 player stats from FBref via the soccerdata library (free, no API key).
Includes goals, assists, shots, cards per 90, and xG.
Saves to data/player_stats.json — read by dashboard.html to update Player Props cards.

Run:  pip install soccerdata
Docs: https://soccerdata.readthedocs.io
"""

import json
import os
from datetime import datetime, timezone

# soccerdata may not be installed in all environments — catch ImportError gracefully
try:
    import soccerdata as sd
    HAS_SD = True
except ImportError:
    HAS_SD = False
    print("soccerdata not installed — skipping FBref scrape")

LEAGUE_MAP = {
    "ENG-Premier League": "Premier League",
    "ESP-La Liga":        "La Liga",
    "GER-Bundesliga":     "Bundesliga",
    "ITA-Serie A":        "Serie A",
    "FRA-Ligue 1":        "Ligue 1",
}

# Use the most recently completed season (2025-26). Switch to 2026-27 once data is available.
SEASON = "2025-2026"


def safe_float(val):
    try:
        return round(float(val), 4) if val is not None and str(val) not in ("", "nan") else 0.0
    except (TypeError, ValueError):
        return 0.0


def safe_int(val):
    try:
        return int(val) if val is not None and str(val) not in ("", "nan") else 0
    except (TypeError, ValueError):
        return 0


def fetch_players():
    if not HAS_SD:
        return {"players": [], "updated": datetime.now(timezone.utc).isoformat(), "note": "soccerdata not available"}

    all_players = []

    for league_key, league_display in LEAGUE_MAP.items():
        print(f"  Scraping {league_display} ({SEASON})...")
        try:
            fbref = sd.FBref(leagues=[league_key], seasons=[SEASON])

            # Standard stats: goals, assists, position, games
            std = fbref.read_player_season_stats(stat_type="standard")
            # Shooting stats: shots/90, SoT/90, xG
            shoot = fbref.read_player_season_stats(stat_type="shooting")
            # Misc stats: yellow cards, red cards per 90
            misc = fbref.read_player_season_stats(stat_type="misc")

            # Flatten MultiIndex columns to simple strings
            def flat_cols(df):
                df.columns = [
                    "_".join([str(c) for c in col]).strip("_") if isinstance(col, tuple) else str(col)
                    for col in df.columns
                ]
                return df

            std   = flat_cols(std.reset_index())
            shoot = flat_cols(shoot.reset_index())
            misc  = flat_cols(misc.reset_index())

            # Find relevant column names (FBref column names can shift slightly by version)
            def find_col(df, keywords):
                for kw in keywords:
                    matches = [c for c in df.columns if kw.lower() in c.lower()]
                    if matches:
                        return matches[0]
                return None

            std_cols = {
                "player": find_col(std, ["player"]),
                "team":   find_col(std, ["team", "squad"]),
                "pos":    find_col(std, ["pos", "position"]),
                "mp":     find_col(std, ["MP", "matches"]),
                "goals":  find_col(std, ["Gls", "goals"]),
                "assists":find_col(std, ["Ast", "assists"]),
                "nation": find_col(std, ["nation", "nationality"]),
            }

            for _, row in std.iterrows():
                player_name = str(row.get(std_cols["player"], "")).strip()
                if not player_name or player_name.lower() == "nan":
                    continue

                mp = safe_int(row.get(std_cols["mp"]))
                goals = safe_float(row.get(std_cols["goals"]))
                assists = safe_float(row.get(std_cols["assists"]))

                # Look up shooting row
                sh_row = shoot[shoot.apply(
                    lambda r: str(r.get(find_col(shoot, ["player"]) or "", "")).strip() == player_name, axis=1
                )].head(1)
                shots_90 = safe_float(sh_row[find_col(shoot, ["Sh/90", "shots_90"])].values[0]) if not sh_row.empty and find_col(shoot, ["Sh/90", "shots_90"]) else 0.0
                sot_90   = safe_float(sh_row[find_col(shoot, ["SoT/90", "sot_90"])].values[0])  if not sh_row.empty and find_col(shoot, ["SoT/90", "sot_90"])  else 0.0
                xg       = safe_float(sh_row[find_col(shoot, ["xG", "expected_goals"])].values[0]) if not sh_row.empty and find_col(shoot, ["xG", "expected_goals"]) else 0.0

                # Look up misc row for cards
                ms_row = misc[misc.apply(
                    lambda r: str(r.get(find_col(misc, ["player"]) or "", "")).strip() == player_name, axis=1
                )].head(1)
                yellow_90 = safe_float(ms_row[find_col(misc, ["CrdY", "yellow"])].values[0]) if not ms_row.empty and find_col(misc, ["CrdY", "yellow"]) else 0.0
                red_90    = safe_float(ms_row[find_col(misc, ["CrdR", "red"])].values[0])    if not ms_row.empty and find_col(misc, ["CrdR", "red"])    else 0.0

                all_players.append({
                    "name":       player_name,
                    "team":       str(row.get(std_cols["team"], "")).strip(),
                    "league":     league_display,
                    "pos":        str(row.get(std_cols["pos"], "")).strip(),
                    "nation":     str(row.get(std_cols["nation"], "")).strip(),
                    "season":     SEASON,
                    "games":      mp,
                    "goals":      goals,
                    "assists":    assists,
                    "goals_pg":   round(goals / mp, 4) if mp > 0 else 0.0,
                    "assists_pg": round(assists / mp, 4) if mp > 0 else 0.0,
                    "shots_90":   shots_90,
                    "sot_90":     sot_90,
                    "xg":         xg,
                    "yellow_90":  yellow_90,
                    "red_90":     red_90,
                })

            print(f"    {sum(1 for p in all_players if p['league']==league_display)} players scraped")

        except Exception as e:
            print(f"    Failed ({league_key}): {e}")

    return {
        "players": all_players,
        "season":  SEASON,
        "updated": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    print("Scraping player stats from FBref...")
    result = fetch_players()
    with open("data/player_stats.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    total = len(result["players"])
    print(f"  Saved data/player_stats.json — {total} players")
