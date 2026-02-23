import streamlit as st
import pandas as pd

from data_loader import load_data, data_available


@st.cache_data
def get_data():
    return load_data()


schedule, teams_bs, players_bs = get_data()

if not data_available() or schedule.empty:
    st.info("No data loaded. Add the `data/` folder (schedule.csv, box_scores_teams.csv, box_scores_players.csv) to the repo, or run the app locally after running the fetch scripts.")
    st.stop()

# ── Sidebar: date picker ────────────────────────────────────────────────────
st.sidebar.title("NBA Game Explorer")

available_dates = sorted(schedule["GAME_DATE"].dt.date.unique())
min_date, max_date = available_dates[0], available_dates[-1]

selected_date = st.sidebar.date_input(
    "Select a date",
    value=max_date,
    min_value=min_date,
    max_value=max_date,
    format="MM/DD/YYYY",
)

# ── Games on selected date ──────────────────────────────────────────────────
day_games = schedule[schedule["GAME_DATE"].dt.date == selected_date].copy()

if day_games.empty:
    st.info(f"No games scheduled on **{selected_date.strftime('%d-%b-%y')}**.")
    st.stop()

st.title(selected_date.strftime("%d-%b-%y"))

game_summaries = []
for _, row in day_games.iterrows():
    gid = row["GAME_ID"]
    matchup_teams = teams_bs[teams_bs["GAME_ID"] == gid].sort_values("TEAM_ABBREVIATION")
    if len(matchup_teams) == 2:
        t1, t2 = matchup_teams.iloc[0], matchup_teams.iloc[1]
        label = f"{t1['TEAM_ABBREVIATION']} {int(t1['PTS'])}  –  {int(t2['PTS'])} {t2['TEAM_ABBREVIATION']}"
    else:
        label = row["MATCHUP"]
    game_summaries.append({"GAME_ID": gid, "label": label})

summary_df = pd.DataFrame(game_summaries)

game_labels = summary_df["label"].tolist()
selected_label = st.selectbox("Select a game", game_labels)
selected_game_id = summary_df.loc[summary_df["label"] == selected_label, "GAME_ID"].iloc[0]

# ── Box score for the selected game ─────────────────────────────────────────
st.divider()

game_teams = teams_bs[teams_bs["GAME_ID"] == selected_game_id].copy()
game_players = players_bs[players_bs["GAME_ID"] == selected_game_id].copy()

TEAM_STAT_COLS = [
    "TEAM_ABBREVIATION", "PTS", "FGM", "FGA", "FG_PCT",
    "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT",
    "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "PF",
]

PLAYER_STAT_COLS = [
    "PLAYER_NAME", "START_POSITION", "MIN",
    "PTS", "FGM", "FGA", "FG_PCT",
    "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT",
    "OREB", "DREB", "REB", "AST", "STL", "BLK", "TO", "PF",
    "PLUS_MINUS",
]

NICE_NAMES = {
    "TEAM_ABBREVIATION": "Team",
    "PLAYER_NAME": "Player",
    "START_POSITION": "Pos",
    "MIN": "Min",
    "PTS": "PTS",
    "FGM": "FGM",
    "FGA": "FGA",
    "FG_PCT": "FG%",
    "FG3M": "3PM",
    "FG3A": "3PA",
    "FG3_PCT": "3P%",
    "FTM": "FTM",
    "FTA": "FTA",
    "FT_PCT": "FT%",
    "OREB": "OREB",
    "DREB": "DREB",
    "REB": "REB",
    "AST": "AST",
    "STL": "STL",
    "BLK": "BLK",
    "TO": "TO",
    "PF": "PF",
    "PLUS_MINUS": "+/-",
}

PCT_COLS = ["FG%", "3P%", "FT%"]


def pct_fmt(val):
    if pd.isna(val):
        return ""
    return f"{val * 100:.1f}%"


def round_minutes(val):
    """Convert '23:06' or 23.1 to a whole-number string like '23'."""
    if pd.isna(val) or val == "":
        return ""
    s = str(val).strip()
    if ":" in s:
        parts = s.split(":")
        return str(int(parts[0]) + (1 if int(parts[1]) >= 30 else 0))
    try:
        return str(round(float(s)))
    except ValueError:
        return s


def format_table(df):
    df = df.copy()
    for col in PCT_COLS:
        if col in df.columns:
            df[col] = df[col].apply(pct_fmt)
    if "Min" in df.columns:
        df["Min"] = df["Min"].apply(round_minutes)
    num_cols = [c for c in df.columns if c not in ("Team", "Player", "Pos", "Min") + tuple(PCT_COLS)]
    for c in num_cols:
        if df[c].dtype in ("float64", "float32"):
            df[c] = df[c].apply(lambda v: "" if pd.isna(v) else str(int(v)))
    return df


# ── Team box scores (both teams together) ───────────────────────────────────
st.subheader("Team Stats")

both_teams_display = game_teams.sort_values("PTS", ascending=False)[TEAM_STAT_COLS].copy()
both_teams_display = both_teams_display.rename(columns=NICE_NAMES)
both_teams_display = format_table(both_teams_display)
st.dataframe(both_teams_display, use_container_width=True, hide_index=True)

# ── Player box scores (per team) ────────────────────────────────────────────
st.subheader("Player Stats")

for _, team_row in game_teams.sort_values("PTS", ascending=False).iterrows():
    team_abbr = team_row["TEAM_ABBREVIATION"]
    team_city = team_row["TEAM_CITY"]
    team_name = team_row["TEAM_NAME"]
    team_pts = int(team_row["PTS"])

    st.markdown(f"**{team_city} {team_name} ({team_abbr}) — {team_pts} pts**")

    team_players = game_players[game_players["TEAM_ABBREVIATION"] == team_abbr].copy()
    starters = team_players[team_players["START_POSITION"].notna() & (team_players["START_POSITION"] != "")]
    bench = team_players[~team_players.index.isin(starters.index)]

    starters_display = format_table(starters[PLAYER_STAT_COLS].rename(columns=NICE_NAMES))
    bench_display = format_table(bench[PLAYER_STAT_COLS].rename(columns=NICE_NAMES))

    st.caption("Starters")
    st.dataframe(starters_display, use_container_width=True, hide_index=True)

    if not bench_display.empty:
        st.caption("Bench")
        st.dataframe(bench_display, use_container_width=True, hide_index=True)

    st.divider()
