#!/usr/bin/env python3
"""One-time fetch: career award counts for every player in data/nba_salaries_2025_26.csv.

Regenerates data/nba_player_awards.csv from the NBA Stats API's PlayerAwards endpoint.
One request per player (~475 requests, ~3-5 minutes with rate-limiting delays).

Usage:
    python scripts/fetch_awards.py
"""

import re
import time
import unicodedata
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import playerawards
from nba_api.stats.static import players as static_players

DATA_DIR = Path(__file__).parent.parent / "data"
SALARY_PATH = DATA_DIR / "nba_salaries_2025_26.csv"
OUTPUT_PATH = DATA_DIR / "nba_player_awards.csv"

AWARD_COLUMNS = {
    "NBA Most Valuable Player": "MVP",
    "NBA Defensive Player of the Year": "DPOY",
    "NBA Rookie of the Year": "ROY",
    "NBA Most Improved Player": "MIP",
    "NBA Finals Most Valuable Player": "FINALS_MVP",
    "NBA Champion": "CHAMPION",
    "NBA All-Star": "ALL_STAR",
    "All-NBA": "ALL_NBA",
    "All-Defensive Team": "ALL_DEFENSIVE",
    "All-Rookie Team": "ALL_ROOKIE",
}


def _exact_key(name: str) -> str:
    """Accent/period/case normalization WITHOUT stripping suffixes.

    Deliberately does NOT strip Jr./II/III like analysis._name_key does elsewhere.
    nba_api's static player list spans NBA history and contains real father/son pairs
    under the same base name (Gary Payton vs Gary Payton II, Larry Nance vs Larry Nance
    Jr., Tim Hardaway vs Tim Hardaway Jr., ...). Stripping suffixes here would collide
    an active player with a retired same-named relative and silently pull the wrong
    person's awards. The static list carries suffixes as part of the exact full name,
    so matching on the exact name is both correct and sufficient.
    """
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.replace(".", "").strip().lower()
    return re.sub(r"\s+", " ", name)


def build_id_lookup() -> dict:
    all_players = static_players.get_players()
    lookup = {}
    for p in sorted(all_players, key=lambda p: p["is_active"]):  # active entries win ties
        lookup[_exact_key(p["full_name"])] = p["id"]
    return lookup


def main():
    salary = pd.read_csv(SALARY_PATH)
    lookup = build_id_lookup()
    salary["_key"] = salary["PLAYER"].map(_exact_key)
    salary["PLAYER_ID"] = salary["_key"].map(lookup)

    unmatched = salary[salary["PLAYER_ID"].isna()]["PLAYER"].tolist()
    if unmatched:
        print(f"No player ID found for: {unmatched} (will get zero awards)")

    total = int(salary["PLAYER_ID"].notna().sum())
    done = 0
    rows = []
    for _, row in salary.iterrows():
        rec = {"PLAYER": row["PLAYER"], **{col: 0 for col in AWARD_COLUMNS.values()}}
        pid = row["PLAYER_ID"]
        if pd.notna(pid):
            try:
                df = playerawards.PlayerAwards(player_id=int(pid), timeout=20).get_data_frames()[0]
                for desc, col in AWARD_COLUMNS.items():
                    rec[col] = int((df["DESCRIPTION"] == desc).sum())
            except Exception as exc:
                print(f"  FAILED {row['PLAYER']}: {exc}")
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{total} fetched...")
            time.sleep(0.35)  # be polite to the API
        rows.append(rec)

    awards_df = pd.DataFrame(rows)
    awards_df["MAJOR_AWARDS"] = awards_df[list(AWARD_COLUMNS.values())].sum(axis=1)
    awards_df.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(awards_df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
