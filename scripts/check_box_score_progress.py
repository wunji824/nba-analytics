"""
Print how many games have box scores vs schedule total.
Run this in another terminal while fetch_box_scores.py is running to monitor progress.

  python scripts/check_box_score_progress.py
  watch -n 10 'python scripts/check_box_score_progress.py'   # every 10 sec (if you have watch)
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

    if not schedule_path.exists():
        print("No schedule.csv found. Run fetch_schedule.py first.")
        return

    schedule = pd.read_csv(schedule_path)
    total_games = schedule["GAME_ID"].nunique()

    if not players_path.exists():
        print(f"Box scores: 0 / {total_games} games (box_scores_players.csv not created yet)")
        return

    players = pd.read_csv(players_path, usecols=["GAME_ID"])
    done_games = players["GAME_ID"].nunique()
    pct = 100.0 * done_games / total_games if total_games else 0

    print(f"Box scores: {done_games:,} / {total_games:,} games ({pct:.1f}%)")
    if done_games >= total_games:
        print("  Complete. Run: python scripts/verify_box_scores.py")
    else:
        print(f"  Remaining: {total_games - done_games:,} games")


if __name__ == "__main__":
    main()
