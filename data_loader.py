"""
Shared data loading. Returns empty DataFrames with correct columns when data/ is missing (e.g. on Streamlit Cloud).
"""
import pandas as pd
from pathlib import Path

# Repo root = directory containing app.py. Streamlit Cloud runs with cwd = repo root.
# Use cwd so data/ is found when app is run from repo root (local or cloud).
DATA_DIR = Path.cwd() / "data"

SCHEDULE_COLS = "GAME_ID,GAME_DATE,SEASON,SEASON_ID,MATCHUP,WL,TEAM_ID,TEAM_ABBREVIATION,TEAM_NAME,PTS,MIN,FGM,FGA,FG_PCT,FG3M,FG3A,FG3_PCT,FTM,FTA,FT_PCT,OREB,DREB,REB,AST,STL,BLK,TOV,PF,PLUS_MINUS".split(",")
TEAMS_COLS = "GAME_ID,TEAM_ID,TEAM_NAME,TEAM_ABBREVIATION,TEAM_CITY,MIN,FGM,FGA,FG_PCT,FG3M,FG3A,FG3_PCT,FTM,FTA,FT_PCT,OREB,DREB,REB,AST,STL,BLK,TO,PF,PTS,PLUS_MINUS".split(",")
PLAYERS_COLS = "GAME_ID,TEAM_ID,TEAM_ABBREVIATION,TEAM_CITY,PLAYER_ID,PLAYER_NAME,NICKNAME,START_POSITION,COMMENT,MIN,FGM,FGA,FG_PCT,FG3M,FG3A,FG3_PCT,FTM,FTA,FT_PCT,OREB,DREB,REB,AST,STL,BLK,TO,PF,PTS,PLUS_MINUS".split(",")


def data_available():
    return (DATA_DIR / "schedule.csv").exists()


def load_data():
    if not (DATA_DIR / "schedule.csv").exists():
        schedule = pd.DataFrame(columns=SCHEDULE_COLS)
        schedule["GAME_DATE"] = pd.to_datetime(schedule["GAME_DATE"])
        teams = pd.DataFrame(columns=TEAMS_COLS)
        players = pd.DataFrame(columns=PLAYERS_COLS)
    else:
        schedule = pd.read_csv(DATA_DIR / "schedule.csv")
        teams = pd.read_csv(DATA_DIR / "box_scores_teams.csv")
        players = pd.read_csv(DATA_DIR / "box_scores_players.csv")
        schedule["GAME_DATE"] = pd.to_datetime(schedule["GAME_DATE"])
    schedule["GAME_ID"] = schedule["GAME_ID"].astype(str).str.zfill(10)
    teams["GAME_ID"] = teams["GAME_ID"].astype(str).str.zfill(10)
    players["GAME_ID"] = players["GAME_ID"].astype(str).str.zfill(10)
    return schedule, teams, players
