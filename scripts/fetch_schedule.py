"""
Fetch NBA game schedule for configured seasons using nba_api LeagueGameFinder.
Writes one row per game to data/schedule.csv (deduplicated from team-level results).
"""

import sys
import time
from pathlib import Path

import pandas as pd

# Project root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DATA_DIR, SEASONS, SEASON_TYPE

from nba_api.stats.endpoints import leaguegamefinder


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / "schedule.csv"

    all_frames = []
    for season in SEASONS:
        print(f"Fetching schedule for {season} ({SEASON_TYPE})...")
        try:
            finder = leaguegamefinder.LeagueGameFinder(
                season_nullable=season,
                season_type_nullable=SEASON_TYPE,
                player_or_team_abbreviation="T",  # Team level = one row per team per game
            )
            df = finder.get_data_frames()[0]
            if df.empty:
                print(f"  No games found for {season}.")
                continue
            df["SEASON"] = season
            all_frames.append(df)
            print(f"  Got {len(df)} team-games ({len(df['GAME_ID'].unique())} unique games).")
        except Exception as e:
            print(f"  Error: {e}")
            raise
        time.sleep(0.6)  # be nice to the API

    if not all_frames:
        print("No data fetched. Exiting.")
        return

    combined = pd.concat(all_frames, ignore_index=True)
    # One row per game: keep key columns, take first row per GAME_ID
    schedule_cols = [
        "GAME_ID", "GAME_DATE", "SEASON", "SEASON_ID",
        "MATCHUP", "WL", "TEAM_ID", "TEAM_ABBREVIATION", "TEAM_NAME",
        "PTS", "MIN", "FGM", "FGA", "FG_PCT", "FG3M", "FG3A", "FG3_PCT",
        "FTM", "FTA", "FT_PCT", "OREB", "DREB", "REB", "AST", "STL", "BLK", "TOV", "PF", "PLUS_MINUS",
    ]
    # Keep all columns that exist
    schedule_cols = [c for c in schedule_cols if c in combined.columns]
    schedule = combined.drop_duplicates(subset=["GAME_ID"], keep="first")[schedule_cols]
    schedule = schedule.sort_values(["GAME_DATE", "GAME_ID"]).reset_index(drop=True)

    schedule.to_csv(out_path, index=False)
    print(f"Wrote {len(schedule)} games to {out_path}")


if __name__ == "__main__":
    main()
