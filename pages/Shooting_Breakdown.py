import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from pathlib import Path

from data_loader import load_data, data_available

DATA_DIR = Path(__file__).parent.parent / "data"


@st.cache_data
def get_data():
    return load_data()


schedule, teams_bs, players_bs = get_data()

if not data_available() or schedule.empty:
    st.info("No data loaded. Add the `data/` folder (schedule.csv, box_scores_teams.csv, box_scores_players.csv) to the repo for the deployed app, or run the fetch scripts locally.")
    st.stop()

# ── Sidebar controls ─────────────────────────────────────────────────────────
st.sidebar.title("Shooting Breakdown")
seasons = sorted(schedule["SEASON"].unique())
selected_season = st.sidebar.selectbox("Season", seasons, index=len(seasons) - 1)

season_schedule = schedule[schedule["SEASON"] == selected_season].copy()
season_schedule = season_schedule.sort_values("GAME_DATE").reset_index(drop=True)
season_game_ids_all = set(season_schedule["GAME_ID"])

filter_mode = st.sidebar.radio(
    "Filter games",
    ["All games", "Date range", "Last N games"],
    horizontal=False,
)

allowed_game_ids = season_game_ids_all
filter_label = ""

if filter_mode == "Date range":
    min_date = season_schedule["GAME_DATE"].min().date()
    max_date = season_schedule["GAME_DATE"].max().date()
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("From", value=min_date, min_value=min_date, max_value=max_date, format="MM/DD/YYYY", key="sb_start")
    with col2:
        end_date = st.date_input("To", value=max_date, min_value=min_date, max_value=max_date, format="MM/DD/YYYY", key="sb_end")
    if start_date > end_date:
        st.sidebar.warning("From must be before To.")
    else:
        mask = (season_schedule["GAME_DATE"].dt.date >= start_date) & (season_schedule["GAME_DATE"].dt.date <= end_date)
        allowed_game_ids = set(season_schedule.loc[mask, "GAME_ID"])
    # Format dates as 8-Feb-26 for title
    fmt_date = lambda d: f"{d.day}-{d.strftime('%b-%y')}"
    filter_label = f" ({fmt_date(start_date)} to {fmt_date(end_date)})"

last_n_per_team = None
if filter_mode == "Last N games":
    last_n = st.sidebar.selectbox(
        "Last N games per team",
        [5, 10, 15, 20, 30, 40, "All"],
        format_func=lambda x: str(x) if x != "All" else "All",
        index=3,
    )
    if last_n != "All":
        last_n_per_team = int(last_n)
        filter_label = f" (Last {last_n} games)"
    else:
        filter_label = ""

if last_n_per_team is None:
    if filter_mode != "Date range":
        allowed_game_ids = season_game_ids_all
    season_players = players_bs[players_bs["GAME_ID"].isin(allowed_game_ids)].copy()
    games_teams = teams_bs[teams_bs["GAME_ID"].isin(allowed_game_ids)][["GAME_ID", "TEAM_ABBREVIATION", "PTS"]]
else:
    # Per-team: each team's last N games only (record and stats both from that set)
    team_games = teams_bs[teams_bs["GAME_ID"].isin(season_game_ids_all)][["GAME_ID", "TEAM_ABBREVIATION"]].drop_duplicates()
    team_games = team_games.merge(
        season_schedule[["GAME_ID", "GAME_DATE"]],
        on="GAME_ID",
        how="left",
    )
    team_last_n = {}
    for team, grp in team_games.groupby("TEAM_ABBREVIATION"):
        gids = grp.sort_values("GAME_DATE").tail(last_n_per_team)["GAME_ID"].tolist()
        team_last_n[team] = set(gids)
    allowed_game_ids = set().union(*team_last_n.values())
    season_players = players_bs[players_bs["GAME_ID"].isin(allowed_game_ids)].copy()
    # Restrict each team's rows to only their last N games (for aggregation we'll filter below)
    games_teams = teams_bs[teams_bs["GAME_ID"].isin(allowed_game_ids)][["GAME_ID", "TEAM_ABBREVIATION", "PTS"]].copy()
    games_teams = games_teams[games_teams.apply(lambda r: r["GAME_ID"] in team_last_n.get(r["TEAM_ABBREVIATION"], set()), axis=1)]

# W-L record per team (from games_teams: higher PTS = W for that game)
team_wins = {}
for gid, grp in games_teams.groupby("GAME_ID"):
    if len(grp) < 2:
        continue
    grp = grp.sort_values("PTS", ascending=False)
    winner = grp.iloc[0]["TEAM_ABBREVIATION"]
    team_wins[winner] = team_wins.get(winner, 0) + 1
team_games_played = games_teams.groupby("TEAM_ABBREVIATION").size()
team_records = {}
for t in team_games_played.index:
    w = int(team_wins.get(t, 0))
    L = int(team_games_played[t] - w)
    team_records[t] = (w, L)

# For "Last N games", only aggregate player stats from each team's last N games
if last_n_per_team is not None:
    def in_team_last_n(row):
        return row["GAME_ID"] in team_last_n.get(row["TEAM_ABBREVIATION"], set())
    season_players = season_players[season_players.apply(in_team_last_n, axis=1)]

# Aggregate per player-team
agg = (
    season_players
    .groupby(["TEAM_ABBREVIATION", "PLAYER_NAME"])
    .agg(FGM=("FGM", "sum"), FGA=("FGA", "sum"), FG3M=("FG3M", "sum"))
    .reset_index()
)
agg = agg[agg["FGA"] > 0].copy()
agg["eFG"] = (agg["FGM"] + 0.5 * agg["FG3M"]) / agg["FGA"]

team_fga = agg.groupby("TEAM_ABBREVIATION")["FGA"].transform("sum")
agg["share"] = agg["FGA"] / team_fga

# ── Color scale: eFG% → red (bad) to green (good), centered near league avg ~0.52
# More separation: red/orange for below avg, yellow for avg, green only for above avg
EFG_STOPS = [
    (0.38, (165, 20, 20)),
    (0.42, (200, 60, 50)),
    (0.46, (230, 120, 80)),
    (0.50, (245, 200, 100)),
    (0.52, (255, 235, 150)),
    (0.54, (220, 240, 140)),
    (0.57, (120, 195, 100)),
    (0.60, (50, 160, 70)),
    (0.65, (20, 120, 45)),
    (0.72, (10, 85, 30)),
]


def efg_to_color(val):
    val = max(EFG_STOPS[0][0], min(EFG_STOPS[-1][0], val))
    for i in range(len(EFG_STOPS) - 1):
        t0, c0 = EFG_STOPS[i]
        t1, c1 = EFG_STOPS[i + 1]
        if t0 <= val <= t1:
            f = (val - t0) / (t1 - t0)
            r = int(c0[0] + f * (c1[0] - c0[0]))
            g = int(c0[1] + f * (c1[1] - c0[1]))
            b = int(c0[2] + f * (c1[2] - c0[2]))
            return r, g, b
    return EFG_STOPS[-1][1]


def text_color(r, g, b):
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return "#111" if lum > 140 else "#fff"


def build_all_teams_html(agg_df, team_records, filter_suffix=""):
    teams_in_data = list(agg_df["TEAM_ABBREVIATION"].unique())
    if not teams_in_data:
        return ""

    # Sort teams by record (best to worst: fewest losses first, then most wins)
    def sort_key(t):
        w, L = team_records.get(t, (0, 0))
        return (L, -w)
    sorted_teams = sorted(teams_in_data, key=sort_key)

    rows_html = ""
    for team in sorted_teams:
        w, L = team_records.get(team, (0, 0))
        team_label = f'<span class="team-abbr">{team}</span><span class="team-rec">{w}-{L}</span>'
        team_data = agg_df[agg_df["TEAM_ABBREVIATION"] == team].sort_values("share", ascending=False)
        segments = ""
        for _, p in team_data.iterrows():
            pct = p["share"] * 100
            if pct < 0.5:
                continue
            r, g, b = efg_to_color(p["eFG"])
            tc = text_color(r, g, b)
            efg_display = f"{p['eFG']:.1%}"
            tip = f"{p['PLAYER_NAME']}&#10;eFG%: {efg_display}&#10;FGA share: {pct:.1f}%&#10;FGA: {int(p['FGA'])}  FGM: {int(p['FGM'])}"
            label = p["PLAYER_NAME"]
            if pct < 3:
                label = ""
            elif pct < 5:
                parts = label.split()
                label = parts[-1] if parts else label
            segments += (
                f'<div class="seg" style="width:{pct}%;background:rgb({r},{g},{b});color:{tc};" title="{tip}">'
                f'<span>{label}</span></div>'
            )
        rows_html += f'<div class="row"><div class="tlbl">{team_label}</div><div class="bar">{segments}</div></div>'

    return f'<div class="conf-title">Shooting Breakdown | {selected_season} Season{filter_suffix}</div>{rows_html}'


chart_html = build_all_teams_html(agg, team_records, filter_label)

# Title in Streamlit (above iframe); padding so it's not cut off by app header
st.markdown(
    f"<div style='padding-top: 28px; margin-top: 0;'>"
    f"<h2 style='margin: 0 0 0.5rem 0; font-weight: 600;'>Shooting Breakdown | {selected_season} Season{filter_label}</h2>"
    f"</div>",
    unsafe_allow_html=True,
)

# X-axis ticks
ticks_html = ""
for v in [0, 0.25, 0.50, 0.75, 1.00]:
    label = f"{int(v * 100)}%"
    ticks_html += f'<span style="position:absolute;left:{v*100}%;transform:translateX(-50%);color:#fff;font-size:13px;">{label}</span>'

n_teams = agg["TEAM_ABBREVIATION"].nunique()
total_height = n_teams * 52 + 240

html_page = f"""
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0e1117; font-family: 'Source Sans Pro', sans-serif; padding-top: 4px; }}
  .conf-title {{
    color: #fff; font-size: 14px; font-weight: 600;
    padding: 18px 0 10px 52px;
    background: #0e1117;
    position: sticky;
    top: 0;
    z-index: 10;
  }}
  .row {{
    display: flex;
    align-items: center;
    height: 44px;
    margin: 2px 0;
  }}
  .tlbl {{
    width: 52px;
    min-width: 52px;
    text-align: center;
    padding-right: 6px;
    color: #ccc;
    font-size: 12px;
    font-weight: 600;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    line-height: 1.2;
  }}
  .tlbl .team-abbr {{ font-size: 12px; font-weight: 600; color: #fff; }}
  .tlbl .team-rec {{ font-size: 12px; font-weight: 500; color: #fff; margin-top: 2px; }}
  .bar {{
    flex: 1;
    display: flex;
    height: 100%;
    border-radius: 2px;
    overflow: hidden;
  }}
  .seg {{
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    font-size: 11px;
    font-weight: 500;
    white-space: nowrap;
    border-right: 1px solid rgba(0,0,0,0.15);
  }}
  .seg span {{
    overflow: hidden;
    text-overflow: ellipsis;
    padding: 0 2px;
  }}
  .axis {{
    position: relative;
    height: 20px;
    margin: 6px 0 0 72px;
  }}
  .axis-label {{
    text-align: center;
    color: #fff;
    font-size: 12px;
    padding-top: 2px;
  }}
  .legend-wrap {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 12px 0 4px 52px;
    font-size: 11px;
    color: #fff;
  }}
  .legend-bar {{
    width: 200px;
    height: 14px;
    border-radius: 3px;
    background: linear-gradient(to right,
      rgb(165,20,20), rgb(200,60,50), rgb(230,120,80),
      rgb(245,200,100), rgb(255,235,150), rgb(220,240,140),
      rgb(120,195,100), rgb(50,160,70), rgb(20,120,45));
  }}
</style>

{chart_html}
<div class="axis">{ticks_html}</div>
<div class="axis-label">Proportion of Team Field Goal Attempts</div>

<div class="legend-wrap">
  <span>Low</span>
  <div class="legend-bar"></div>
  <span>High</span>
  <span style="margin-left:6px;color:#fff;">eFG%</span>
</div>
"""

components.html(html_page, height=total_height, scrolling=False)
