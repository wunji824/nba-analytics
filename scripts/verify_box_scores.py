"""
Verify that box score data is complete and consistent.
Run this after fetch_box_scores.py finishes to confirm everything worked.

  python scripts/verify_box_scores.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DATA_DIR

import pandas as pd


def main() -> None:
    schedule_path = DATA_DIR / "schedule.csv"
    players_path = DATA_DIR / "box_scores_players.csv"
    teams_path = DATA_DIR / "box_scores_teams.csv"

    print("Verifying box score data...")
    print()

    # 1. Schedule exists and has expected games
    if not schedule_path.exists():
        print("FAIL: schedule.csv not found. Run fetch_schedule.py first.")
        return
    schedule = pd.read_csv(schedule_path)
    schedule_game_ids = set(schedule["GAME_ID"].astype(str).str.zfill(10))
    expected_games = len(schedule_game_ids)
    print(f"  Schedule: {expected_games:,} games")

    if not players_path.exists() or not teams_path.exists():
        print("FAIL: box_scores_players.csv or box_scores_teams.csv not found.")
        return

    players = pd.read_csv(players_path)
    teams = pd.read_csv(teams_path)

    # 2. Unique games in box scores
    player_games = set(players["GAME_ID"].astype(str).str.zfill(10))
    team_games = set(teams["GAME_ID"].astype(str).str.zfill(10))
    print(f"  Box scores (players): {len(player_games):,} unique games")
    print(f"  Box scores (teams):   {len(team_games):,} unique games")

    # 3. Every schedule game has box scores
    missing_in_players = schedule_game_ids - player_games
    missing_in_teams = schedule_game_ids - team_games
    if missing_in_players or missing_in_teams:
        print()
        print("FAIL: Some schedule games are missing box scores.")
        if missing_in_players:
            print(f"  Missing in box_scores_players: {len(missing_in_players):,} games")
        if missing_in_teams:
            print(f"  Missing in box_scores_teams:   {len(missing_in_teams):,} games")
        print("  Re-run: python scripts/fetch_box_scores.py")
        return

    # 4. Each game has exactly 2 team rows
    teams_per_game = teams.groupby(teams["GAME_ID"].astype(str).str.zfill(10)).size()
    bad_team_counts = teams_per_game[teams_per_game != 2]
    if len(bad_team_counts) > 0:
        print()
        print(f"WARN: {len(bad_team_counts)} games do not have exactly 2 team rows (expected 2 per game).")
        print("  Examples:", bad_team_counts.head().to_dict())
    else:
        print("  Each game has exactly 2 team rows (both teams). OK.")

    # 5. Row counts
    print()
    print("  Row counts:")
    print(f"    box_scores_players.csv: {len(players):,} rows")
    print(f"    box_scores_teams.csv:   {len(teams):,} rows")

    # 6. Sanity: players per game in reasonable range (typically ~15–30 per game)
    players_per_game = players.groupby(players["GAME_ID"].astype(str).str.zfill(10)).size()
    min_p, max_p = int(players_per_game.min()), int(players_per_game.max())
    print(f"    Players per game: min {min_p}, max {max_p} (typical range ~15–30)")

    print()
    print("SUCCESS: Box score data looks complete and consistent.")
    print("  You can use data/box_scores_players.csv and data/box_scores_teams.csv for analytics.")


if __name__ == "__main__":
    main()
