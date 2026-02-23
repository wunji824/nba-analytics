import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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
st.sidebar.title("Team Rotation")

seasons = sorted(schedule["SEASON"].unique())
selected_season = st.sidebar.selectbox("Season", seasons, index=len(seasons) - 1)

season_schedule = schedule[schedule["SEASON"] == selected_season].copy()
season_game_ids = set(season_schedule["GAME_ID"])
season_teams = teams_bs[teams_bs["GAME_ID"].isin(season_game_ids)]

team_info = (
    season_teams[["TEAM_ABBREVIATION", "TEAM_CITY", "TEAM_NAME"]]
    .drop_duplicates()
    .sort_values("TEAM_NAME")
    .reset_index(drop=True)
)
team_labels = [
    f"{r.TEAM_CITY} {r.TEAM_NAME} ({r.TEAM_ABBREVIATION})"
    for _, r in team_info.iterrows()
]
selected_idx = st.sidebar.selectbox(
    "Team", range(len(team_labels)), format_func=lambda i: team_labels[i]
)
sel = team_info.iloc[selected_idx]
team_abbr = sel.TEAM_ABBREVIATION
team_full = f"{sel.TEAM_CITY} {sel.TEAM_NAME}"

# ── Build rotation matrix ────────────────────────────────────────────────────
team_game_ids = set(
    season_teams[season_teams["TEAM_ABBREVIATION"] == team_abbr]["GAME_ID"]
)
team_schedule = (
    season_schedule[season_schedule["GAME_ID"].isin(team_game_ids)]
    .sort_values("GAME_DATE")
    .reset_index(drop=True)
)
team_schedule["GAME_NUM"] = range(1, len(team_schedule) + 1)
gid_to_num = dict(zip(team_schedule["GAME_ID"], team_schedule["GAME_NUM"]))

# Opponent labels for hover: find the other team in each game
def get_opponent(game_id):
    game_rows = teams_bs[teams_bs["GAME_ID"] == game_id]
    opp = game_rows[game_rows["TEAM_ABBREVIATION"] != team_abbr]
    return opp["TEAM_ABBREVIATION"].iloc[0] if len(opp) > 0 else "?"

team_schedule["OPP"] = team_schedule["GAME_ID"].apply(get_opponent)
gid_to_opp = dict(zip(team_schedule["GAME_ID"], team_schedule["OPP"]))
gid_to_date = dict(
    zip(team_schedule["GAME_ID"], team_schedule["GAME_DATE"].dt.strftime("%d-%b-%y"))
)

team_players = players_bs[
    (players_bs["GAME_ID"].isin(team_game_ids))
    & (players_bs["TEAM_ABBREVIATION"] == team_abbr)
].copy()


def parse_minutes(val):
    if pd.isna(val) or str(val).strip() == "":
        return 0
    s = str(val).strip()
    if ":" in s:
        parts = s.split(":")
        return round(int(parts[0]) + int(parts[1]) / 60)
    try:
        return round(float(s))
    except ValueError:
        return 0


team_players["MIN_ROUND"] = team_players["MIN"].apply(parse_minutes)
team_players["GAME_NUM"] = team_players["GAME_ID"].map(gid_to_num)

pivot = team_players.pivot_table(
    index="PLAYER_NAME",
    columns="GAME_NUM",
    values="MIN_ROUND",
    aggfunc="first",
    fill_value=0,
)

all_nums = list(range(1, len(team_schedule) + 1))
for n in all_nums:
    if n not in pivot.columns:
        pivot[n] = 0
pivot = pivot[sorted(pivot.columns)].fillna(0).astype(int)

pivot["_avg"] = pivot.mean(axis=1)
pivot = pivot.sort_values("_avg", ascending=False)
pivot = pivot.drop(columns="_avg")

# Optional filter
min_games = st.sidebar.slider(
    "Min games played", 1, len(all_nums), 1
)
games_played = (pivot > 0).sum(axis=1)
pivot = pivot[games_played >= min_games]

if pivot.empty:
    st.warning("No players match the filter.")
    st.stop()

# ── Build hover text matrix ──────────────────────────────────────────────────
game_num_to_gid = dict(zip(team_schedule["GAME_NUM"], team_schedule["GAME_ID"]))
hover_text = []
for player in pivot.index:
    row_hover = []
    for gn in pivot.columns:
        gid = game_num_to_gid.get(gn, "")
        opp = gid_to_opp.get(gid, "")
        date = gid_to_date.get(gid, "")
        mins = pivot.loc[player, gn]
        row_hover.append(f"{player}<br>Game {gn} vs {opp} ({date})<br>{mins} min")
    hover_text.append(row_hover)

# ── Heatmap as HTML table with sticky player names ───────────────────────────
import streamlit.components.v1 as components
import numpy as np

n_players = len(pivot)
n_games = len(pivot.columns)

COLOR_STOPS = [
    (0.00, (49, 54, 149)),
    (0.10, (69, 117, 180)),
    (0.20, (116, 173, 209)),
    (0.30, (171, 217, 233)),
    (0.40, (224, 243, 248)),
    (0.50, (255, 255, 191)),
    (0.60, (254, 224, 144)),
    (0.70, (253, 174, 97)),
    (0.80, (244, 109, 67)),
    (0.90, (215, 48, 39)),
    (1.00, (165, 0, 38)),
]

def minutes_to_color(val, vmin=0, vmax=42):
    t = max(0.0, min(1.0, (val - vmin) / (vmax - vmin)))
    for i in range(len(COLOR_STOPS) - 1):
        t0, c0 = COLOR_STOPS[i]
        t1, c1 = COLOR_STOPS[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0)
            r = int(c0[0] + f * (c1[0] - c0[0]))
            g = int(c0[1] + f * (c1[1] - c0[1]))
            b = int(c0[2] + f * (c1[2] - c0[2]))
            return r, g, b
    return COLOR_STOPS[-1][1]

def text_color(r, g, b):
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return "#000" if lum > 150 else "#fff"

# Compute per-player averages (only counting games where they appeared in the data)
player_avgs = {}
for player in pivot.index:
    vals = pivot.loc[player]
    games_present = (vals > 0).sum()
    player_avgs[player] = round(vals.sum() / max(games_present, 1), 1)

# Build HTML rows as JSON-friendly data for JS sorting
import json

game_num_to_gid = dict(zip(team_schedule["GAME_NUM"], team_schedule["GAME_ID"]))
rows_data = []
for player in pivot.index:
    cells_html = ""
    sort_vals = []
    for gn in pivot.columns:
        val = int(pivot.loc[player, gn])
        r, g, b = minutes_to_color(val)
        tc = text_color(r, g, b)
        gid = game_num_to_gid.get(gn, "")
        opp = gid_to_opp.get(gid, "")
        date = gid_to_date.get(gid, "")
        tip = f"{player} — Game {gn} vs {opp} ({date}) — {val} min"
        display = str(val) if val > 0 else ""
        cells_html += f'<td style="background:rgb({r},{g},{b});color:{tc};" title="{tip}">{display}</td>'
        sort_vals.append(val)
    avg = player_avgs[player]
    avg_r, avg_g, avg_b = minutes_to_color(avg)
    avg_tc = text_color(avg_r, avg_g, avg_b)
    avg_cell = f'<td class="avg" style="background:rgb({avg_r},{avg_g},{avg_b});color:{avg_tc};">{avg}</td>'
    sort_vals.append(avg)
    rows_data.append({
        "player": player,
        "cells": cells_html,
        "avg_cell": avg_cell,
        "vals": sort_vals,
    })

rows_json = json.dumps(rows_data)

header_cells = ['<th class="pn corner" onclick="sortTable(-1)">Player ⇅</th>']
for i, gn in enumerate(pivot.columns):
    header_cells.append(f'<th onclick="sortTable({i})">{gn}</th>')
header_cells.append(f'<th class="avg" onclick="sortTable({len(pivot.columns)})">Avg</th>')
header = "<tr>" + "".join(header_cells) + "</tr>"

n_cols = len(pivot.columns) + 1
table_height = n_players * 36 + 80

html_page = f"""
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0e1117; font-family: 'Source Sans Pro', sans-serif; }}
  body {{ padding: 0; margin: 0; }}
  h2 {{ color: #fafafa; padding: 4px 0 8px 140px; font-size: 15px; font-weight: 600; margin: 0; }}
  .wrap {{
    overflow-x: auto;
    overflow-y: auto;
    max-height: {table_height}px;
    width: 100%;
    min-width: 100%;
    -webkit-overflow-scrolling: touch;
  }}
  table {{
    border-collapse: collapse;
    font-size: 12px;
  }}
  th, td {{
    width: 52px;
    min-width: 52px;
    max-width: 52px;
    height: 36px;
    text-align: center;
    padding: 0;
    border: 1px solid rgba(255,255,255,0.06);
  }}
  th {{
    position: sticky;
    top: 0;
    z-index: 2;
    background: #0e1117;
    color: #aaa;
    font-weight: 500;
    font-size: 11px;
    cursor: pointer;
    user-select: none;
  }}
  th:hover {{ color: #fff; }}
  .pn {{
    position: sticky;
    left: 0;
    z-index: 3;
    background: #0e1117;
    color: #eee;
    text-align: right;
    padding: 0 10px 0 4px;
    width: 140px;
    min-width: 140px;
    max-width: 140px;
    white-space: nowrap;
    font-size: 12px;
    font-weight: 500;
  }}
  .corner {{
    z-index: 4;
  }}
  .avg {{
    position: sticky;
    right: 0;
    z-index: 3;
    background: #0e1117;
    font-weight: 600;
    width: 52px;
    min-width: 52px;
    max-width: 52px;
  }}
  th.avg {{
    z-index: 5;
  }}
  .legend {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 0 0 140px;
    color: #ccc;
    font-size: 12px;
  }}
  .legend-bar {{
    width: 260px;
    height: 14px;
    border-radius: 3px;
    background: linear-gradient(to right,
      rgb(49,54,149), rgb(69,117,180), rgb(116,173,209),
      rgb(171,217,233), rgb(224,243,248), rgb(255,255,191),
      rgb(254,224,144), rgb(253,174,97), rgb(244,109,67),
      rgb(215,48,39), rgb(165,0,38));
  }}
  .legend span {{
    font-size: 11px;
    color: #aaa;
  }}
</style>
<h2>{team_full} — rotation and playing time by game | {selected_season} Season</h2>
<div class="wrap">
  <table id="rot">
    <thead>{header}</thead>
    <tbody id="tbody"></tbody>
  </table>
</div>
<div class="legend">
  <span>0</span>
  <div class="legend-bar"></div>
  <span>42</span>
  <span style="margin-left:4px; color:#888;">Minutes Played</span>
</div>
<script>
var rows = {rows_json};
var sortCol = null;
var sortAsc = false;

function render(data) {{
  var tb = document.getElementById('tbody');
  tb.innerHTML = '';
  for (var i = 0; i < data.length; i++) {{
    var tr = document.createElement('tr');
    tr.innerHTML = '<td class="pn">' + data[i].player + '</td>'
                   + data[i].cells + data[i].avg_cell;
    tb.appendChild(tr);
  }}
}}

function sortTable(col) {{
  if (sortCol === col) {{
    sortAsc = !sortAsc;
  }} else {{
    sortCol = col;
    sortAsc = false;
  }}
  var sorted = rows.slice();
  if (col === -1) {{
    sorted.sort(function(a, b) {{
      return sortAsc ? a.player.localeCompare(b.player)
                     : b.player.localeCompare(a.player);
    }});
  }} else {{
    sorted.sort(function(a, b) {{
      return sortAsc ? a.vals[col] - b.vals[col]
                     : b.vals[col] - a.vals[col];
    }});
  }}
  render(sorted);
}}

sortTable({len(pivot.columns)});
</script>
"""

components.html(html_page, height=min(table_height + 100, n_players * 36 + 160), scrolling=False)
