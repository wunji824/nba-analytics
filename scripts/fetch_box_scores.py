"""
Fetch box scores (player and team stats) for each game in data/schedule.csv.
Uses nba_api BoxScoreTraditionalV2. Appends to data/box_scores_players.csv and
data/box_scores_teams.csv; skips games already present (safe to re-run).

Usage:
  python scripts/fetch_box_scores.py           # all games not yet fetched
  python scripts/fetch_box_scores.py --limit 5 # test with first 5 missing games
"""

import argparse
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path

import pandas as pd

# Silence pandas FutureWarning about concat with empty/all-NA columns (box score data can have NA)
warnings.filterwarnings("ignore", message=".*DataFrame concatenation with empty or all-NA.*", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DATA_DIR, REQUEST_DELAY_SECONDS

from nba_api.stats.endpoints import boxscoretraditionalv2

# Hard timeout per game: if the API doesn't respond in this many seconds, skip and continue
REQUEST_TIMEOUT_SECONDS = 45


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch box scores for games in schedule.")
    parser.add_argument("--limit", type=int, default=None, help="Max number of games to fetch (default: all)")
    args = parser.parse_args()
    schedule_path = DATA_DIR / "schedule.csv"
    if not schedule_path.exists():
        print("Run fetch_schedule.py first to create data/schedule.csv")
        return

    schedule = pd.read_csv(schedule_path)
    game_ids = schedule["GAME_ID"].astype(str).str.zfill(10).unique().tolist()
    print(f"Schedule has {len(game_ids)} unique games.")

    # Use resolved absolute paths so writes always go to the same place
    players_path = (DATA_DIR / "box_scores_players.csv").resolve()
    teams_path = (DATA_DIR / "box_scores_teams.csv").resolve()

    # Remove any leftover .tmp/.temp files (from old script runs or editor)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for f in DATA_DIR.iterdir():
        if f.suffix in (".tmp", ".temp") or f.name.endswith(".csv.tmp"):
            try:
                f.unlink()
            except OSError:
                pass

    # Already-fetched game IDs (if we're appending)
    done_ids = set()
    if players_path.exists():
        existing = pd.read_csv(players_path, usecols=["GAME_ID"])
        done_ids = set(existing["GAME_ID"].astype(str).str.zfill(10))
        print(f"Already have box scores for {len(done_ids)} games.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    to_fetch = [g for g in game_ids if g not in done_ids]
    if args.limit is not None:
        to_fetch = to_fetch[: args.limit]
        print(f"Limited to {len(to_fetch)} games (--limit {args.limit}).")
    if not to_fetch:
        print("Nothing to fetch.")
        return

    # Write to CSV every N games so you can monitor progress (e.g. wc -l or check_box_score_progress.py)
    WRITE_EVERY_N = 25

    def fetch_one(game_id: str):
        box = boxscoretraditionalv2.BoxScoreTraditionalV2(
            game_id=game_id,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        frames = box.get_data_frames()  # [0]=PlayerStats, [1]=TeamStats, [2]=TeamStarterBenchStats
        player_df = frames[0].copy()
        team_df = frames[1].copy()
        player_df["GAME_ID"] = game_id
        team_df["GAME_ID"] = game_id
        return player_df, team_df

    print(f"Fetching box scores for {len(to_fetch)} games (writing every {WRITE_EVERY_N} games, {REQUEST_TIMEOUT_SECONDS}s timeout)...")
    sys.stdout.flush()
    batch_players = []
    batch_teams = []

    with ThreadPoolExecutor(max_workers=1) as executor:
        for i, game_id in enumerate(to_fetch):
            try:
                future = executor.submit(fetch_one, game_id)
                player_df, team_df = future.result(timeout=REQUEST_TIMEOUT_SECONDS + 5)
                # Only add to batch if API returned data (some games return empty box scores)
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
                batch_only_players = pd.concat(batch_players, ignore_index=True)
                batch_only_teams = pd.concat(batch_teams, ignore_index=True)
                if players_path.exists():
                    existing_players = pd.read_csv(players_path)
                    existing_teams = pd.read_csv(teams_path)
                    new_players = pd.concat([existing_players, batch_only_players], ignore_index=True)
                    new_teams = pd.concat([existing_teams, batch_only_teams], ignore_index=True)
                else:
                    new_players = batch_only_players
                    new_teams = batch_only_teams
                new_players.to_csv(players_path, index=False)
                new_teams.to_csv(teams_path, index=False)
                batch_players = []
                batch_teams = []
                n_games = new_teams["GAME_ID"].nunique()
                print(f"  {n_done}/{len(to_fetch)} — saved to CSV (players: {len(new_players)} rows, teams: {len(new_teams)} rows, {n_games} games)", flush=True)
            # Cooldown every 500 games to reduce rate limiting (timeouts often start after ~600)
            if n_done > 0 and n_done % 500 == 0:
                print(f"  Cooldown 90s after {n_done} games...", flush=True)
                time.sleep(90)
            time.sleep(REQUEST_DELAY_SECONDS)

    # Write any remaining games
    if batch_players:
        batch_only_players = pd.concat(batch_players, ignore_index=True)
        batch_only_teams = pd.concat(batch_teams, ignore_index=True)
        if players_path.exists():
            existing_players = pd.read_csv(players_path)
            existing_teams = pd.read_csv(teams_path)
            new_players = pd.concat([existing_players, batch_only_players], ignore_index=True)
            new_teams = pd.concat([existing_teams, batch_only_teams], ignore_index=True)
        else:
            new_players = batch_only_players
            new_teams = batch_only_teams
        new_players.to_csv(players_path, index=False)
        new_teams.to_csv(teams_path, index=False)
        print(f"  {len(to_fetch)}/{len(to_fetch)} — saved to CSV (players: {len(new_players)} rows, teams: {len(new_teams)} rows)", flush=True)

    if players_path.exists():
        total_players = len(pd.read_csv(players_path))
        total_teams = len(pd.read_csv(teams_path))
        print(f"Done. {players_path}: {total_players} rows. {teams_path}: {total_teams} rows.")


if __name__ == "__main__":
    main()
