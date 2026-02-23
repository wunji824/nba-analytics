"""
Fetch missing box scores using BoxScoreTraditionalV3 (works for 2025-26 season).
Maps V3 column names to match the V2 format already in box_scores_players.csv
and box_scores_teams.csv, then appends.

Usage:
  python scripts/fetch_box_scores_v3.py           # all missing games
  python scripts/fetch_box_scores_v3.py --limit 5  # test with 5 games
"""

import argparse
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", message=".*DataFrame concatenation with empty or all-NA.*", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DATA_DIR, REQUEST_DELAY_SECONDS
from nba_api.stats.endpoints import boxscoretraditionalv3

REQUEST_TIMEOUT_SECONDS = 45
WRITE_EVERY_N = 25

# V3 → V2 column mapping for PlayerStats
PLAYER_COL_MAP = {
    "gameId": "GAME_ID",
    "teamId": "TEAM_ID",
    "teamTricode": "TEAM_ABBREVIATION",
    "teamCity": "TEAM_CITY",
    "personId": "PLAYER_ID",
    "nameI": "PLAYER_NAME",
    "firstName": "NICKNAME",
    "position": "START_POSITION",
    "comment": "COMMENT",
    "minutes": "MIN",
    "fieldGoalsMade": "FGM",
    "fieldGoalsAttempted": "FGA",
    "fieldGoalsPercentage": "FG_PCT",
    "threePointersMade": "FG3M",
    "threePointersAttempted": "FG3A",
    "threePointersPercentage": "FG3_PCT",
    "freeThrowsMade": "FTM",
    "freeThrowsAttempted": "FTA",
    "freeThrowsPercentage": "FT_PCT",
    "reboundsOffensive": "OREB",
    "reboundsDefensive": "DREB",
    "reboundsTotal": "REB",
    "assists": "AST",
    "steals": "STL",
    "blocks": "BLK",
    "turnovers": "TO",
    "foulsPersonal": "PF",
    "points": "PTS",
    "plusMinusPoints": "PLUS_MINUS",
}

# V3 → V2 column mapping for TeamStats
TEAM_COL_MAP = {
    "gameId": "GAME_ID",
    "teamId": "TEAM_ID",
    "teamName": "TEAM_NAME",
    "teamTricode": "TEAM_ABBREVIATION",
    "teamCity": "TEAM_CITY",
    "minutes": "MIN",
    "fieldGoalsMade": "FGM",
    "fieldGoalsAttempted": "FGA",
    "fieldGoalsPercentage": "FG_PCT",
    "threePointersMade": "FG3M",
    "threePointersAttempted": "FG3A",
    "threePointersPercentage": "FG3_PCT",
    "freeThrowsMade": "FTM",
    "freeThrowsAttempted": "FTA",
    "freeThrowsPercentage": "FT_PCT",
    "reboundsOffensive": "OREB",
    "reboundsDefensive": "DREB",
    "reboundsTotal": "REB",
    "assists": "AST",
    "steals": "STL",
    "blocks": "BLK",
    "turnovers": "TO",
    "foulsPersonal": "PF",
    "points": "PTS",
    "plusMinusPoints": "PLUS_MINUS",
}


def map_v3_to_v2(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Rename V3 columns to V2 names, keeping only mapped columns."""
    available = {k: v for k, v in col_map.items() if k in df.columns}
    return df.rename(columns=available)[list(available.values())]


def fetch_one(game_id: str):
    box = boxscoretraditionalv3.BoxScoreTraditionalV3(
        game_id=game_id,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    frames = box.get_data_frames()  # [0]=PlayerStats, [1]=TeamStarterBench, [2]=TeamStats
    player_df = map_v3_to_v2(frames[0].copy(), PLAYER_COL_MAP)
    team_df = map_v3_to_v2(frames[2].copy(), TEAM_COL_MAP)
    return player_df, team_df


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch missing box scores via V3 endpoint.")
    parser.add_argument("--limit", type=int, default=None, help="Max games to fetch")
    args = parser.parse_args()

    players_path = (DATA_DIR / "box_scores_players.csv").resolve()
    teams_path = (DATA_DIR / "box_scores_teams.csv").resolve()
    schedule_path = DATA_DIR / "schedule.csv"

    if not schedule_path.exists():
        print("Run fetch_schedule.py first.")
        return

    schedule = pd.read_csv(schedule_path)
    all_game_ids = schedule["GAME_ID"].astype(str).str.zfill(10).unique().tolist()

    done_ids = set()
    if teams_path.exists():
        existing_teams = pd.read_csv(teams_path, usecols=["GAME_ID"])
        team_counts = existing_teams["GAME_ID"].astype(str).str.zfill(10).value_counts()
        done_ids = set(team_counts[team_counts >= 2].index)
        print(f"Already have complete box scores for {len(done_ids)} games.")

    to_fetch = [g for g in all_game_ids if g not in done_ids]
    if args.limit is not None:
        to_fetch = to_fetch[: args.limit]
        print(f"Limited to {len(to_fetch)} games (--limit {args.limit}).")
    if not to_fetch:
        print("Nothing to fetch.")
        return

    print(f"Fetching {len(to_fetch)} missing games via V3 endpoint (writing every {WRITE_EVERY_N}, {REQUEST_TIMEOUT_SECONDS}s timeout)...")
    sys.stdout.flush()

    batch_players = []
    batch_teams = []

    with ThreadPoolExecutor(max_workers=1) as executor:
        for i, game_id in enumerate(to_fetch):
            try:
                future = executor.submit(fetch_one, game_id)
                player_df, team_df = future.result(timeout=REQUEST_TIMEOUT_SECONDS + 5)
                if len(player_df) > 0 and len(team_df) > 0:
                    batch_players.append(player_df)
                    batch_teams.append(team_df)
                else:
                    print(f"  Empty box score for game {game_id}, skipping.", flush=True)
            except FuturesTimeoutError:
                print(f"  Timeout for game {game_id}, skipping.", flush=True)
            except Exception as e:
                print(f"  Error for game {game_id}: {e}", flush=True)

            n_done = i + 1
            if n_done % WRITE_EVERY_N == 0 and batch_players:
                _append_and_save(batch_players, batch_teams, players_path, teams_path)
                n_games_total = pd.read_csv(teams_path, usecols=["GAME_ID"])["GAME_ID"].nunique()
                print(f"  {n_done}/{len(to_fetch)} — saved (total games in CSVs: {n_games_total})", flush=True)
                batch_players = []
                batch_teams = []
            if n_done > 0 and n_done % 500 == 0:
                print(f"  Cooldown 90s after {n_done} games...", flush=True)
                time.sleep(90)
            time.sleep(REQUEST_DELAY_SECONDS)

    if batch_players:
        _append_and_save(batch_players, batch_teams, players_path, teams_path)
        print(f"  {len(to_fetch)}/{len(to_fetch)} — saved", flush=True)

    if players_path.exists():
        total_p = len(pd.read_csv(players_path))
        total_t = len(pd.read_csv(teams_path))
        total_g = pd.read_csv(teams_path, usecols=["GAME_ID"])["GAME_ID"].nunique()
        print(f"Done. players: {total_p} rows, teams: {total_t} rows, {total_g} unique games.")


def _append_and_save(batch_players, batch_teams, players_path, teams_path):
    new_players = pd.concat(batch_players, ignore_index=True)
    new_teams = pd.concat(batch_teams, ignore_index=True)
    if players_path.exists():
        existing_p = pd.read_csv(players_path)
        existing_t = pd.read_csv(teams_path)
        new_players = pd.concat([existing_p, new_players], ignore_index=True)
        new_teams = pd.concat([existing_t, new_teams], ignore_index=True)
    new_players.to_csv(players_path, index=False)
    new_teams.to_csv(teams_path, index=False)


if __name__ == "__main__":
    main()
