"""
List games that are in schedule.csv but don't have exactly 2 rows in
box_scores_teams.csv (one per team). Cross-references schedule vs teams CSV.

Output: data/missing_box_scores.csv (game_id, game_date, season, matchup, team_rows).
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DATA_DIR
import pandas as pd

ROWS_PER_GAME = 2


def main() -> None:
    schedule_path = DATA_DIR / "schedule.csv"
    teams_path = DATA_DIR / "box_scores_teams.csv"

    if not schedule_path.exists():
        print("No schedule.csv found.")
        return
    schedule = pd.read_csv(schedule_path)
    schedule["GAME_ID_STR"] = schedule["GAME_ID"].astype(str).str.zfill(10)
    schedule_games = schedule.drop_duplicates(subset=["GAME_ID_STR"], keep="first").set_index(
        "GAME_ID_STR"
    )

    if not teams_path.exists():
        team_counts = pd.Series(dtype=int)
    else:
        teams = pd.read_csv(teams_path, usecols=["GAME_ID"])
        teams["GAME_ID_STR"] = teams["GAME_ID"].astype(str).str.zfill(10)
        team_counts = teams.groupby("GAME_ID_STR").size()

    # Missing = in schedule but not exactly ROWS_PER_GAME in teams
    missing_gids = []
    team_rows_list = []
    for gid in schedule_games.index:
        n = int(team_counts.get(gid, 0))
        if n != ROWS_PER_GAME:
            missing_gids.append(gid)
            team_rows_list.append(n)

    missing_schedule = schedule_games.loc[missing_gids].reset_index()
    missing = missing_schedule[["GAME_ID", "GAME_DATE", "SEASON", "MATCHUP"]].copy()
    missing["team_rows"] = team_rows_list  # 0 = no data, 1 = incomplete

    out = DATA_DIR / "missing_box_scores.csv"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    missing = missing.sort_values(["GAME_DATE", "GAME_ID"]).reset_index(drop=True)
    missing.to_csv(out, index=False)
    print(f"Schedule games: {len(schedule_games)}")
    print(f"Expected team rows per game: {ROWS_PER_GAME}")
    print(f"Missing/incomplete box scores: {len(missing)} games.")
    print(f"Wrote {out}")
    if len(missing) > 0:
        print("By season:", missing["SEASON"].value_counts().sort_index().to_dict())
        if missing["team_rows"].eq(0).any():
            print("Games with 0 team rows:", missing["team_rows"].eq(0).sum())
        if missing["team_rows"].eq(1).any():
            print("Games with 1 team row (incomplete):", missing["team_rows"].eq(1).sum())
        print("Re-run: python scripts/fetch_box_scores.py  (when API has data, rows will be appended)")


if __name__ == "__main__":
    main()
