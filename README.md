# NBA Analytics

Player-level and team-level NBA analytics, starting with historical game schedules and box scores.

## Data sources

- **[nba_api](https://github.com/swar/nba_api)** – Python client for NBA.com stats (schedules, box scores, player/team stats).
- Inspiration from **[nba-box-scores](https://github.com/matsonj/nba-box-scores)** for the pipeline: fetch schedule → fetch box scores → store for analysis.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Requires **Python 3.10+**.

## Data pipeline

1. **Fetch game schedule** (historical seasons)
   ```bash
   python scripts/fetch_schedule.py
   ```
   Uses `LeagueGameFinder` to get all games for the configured seasons. Output: `data/schedule.csv`.

2. **Fetch box scores** (player and team stats per game)
   ```bash
   python scripts/fetch_box_scores.py
   ```
   Uses `BoxScoreTraditionalV2` for each game in the schedule. Outputs:
   - `data/box_scores_players.csv`
   - `data/box_scores_teams.csv`

Run step 1 first; step 2 reads the schedule and skips games already in the box score files (safe to re-run to backfill).

## Configuration

- **Seasons**: Edit `config.py` and set `SEASONS` (e.g. `["2023-24", "2024-25"]`). Season format is `YYYY-YY`.
- **Data dir**: Default `data/`. Change `DATA_DIR` in `config.py` if needed.

## Project layout

```
NBA Analytics/
├── config.py           # Seasons, paths
├── data/               # schedule.csv, box_scores_*.csv (git-ignored)
├── scripts/
│   ├── fetch_schedule.py
│   └── fetch_box_scores.py
├── requirements.txt
└── README.md
```

## Running the app

```bash
streamlit run app.py
```

Open the URL shown (e.g. http://localhost:8501). The app has three sections:

- **Box Scores** – Pick a date and game to view full box scores.
- **Team Rotation** – Heatmap of player minutes by game (season + team), sortable columns, Avg column.
- **Shooting Breakdown** – FGA share by player per team, colored by eFG%; filter by season, date range, or last N games; W–L and standings sort.

## Version control (GitHub)

After initializing and pushing to GitHub you have a backup and can collaborate or deploy:

```bash
git init
git add .
git commit -m "Initial commit: NBA Analytics app"
# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/nba-analytics.git
git branch -M main
git push -u origin main
```

Note: `data/` is in `.gitignore`, so your CSV files are not pushed. The repo stays small; you keep data locally or add it later if you want the deployed app to have data.

## Deploy online (access from mobile without your computer)

To use the app from a phone or another device when your computer is off, deploy it to **Streamlit Community Cloud** (free):

1. Push your code to GitHub (see above).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub.
3. Click **New app**, choose your repo and branch, set **Main file path** to `app.py`.
4. Click **Deploy**. Streamlit runs the app on their servers and gives you a public URL (e.g. `https://your-app.streamlit.app`).

You can open that URL on any device. Your local `data/` folder is not in the repo, so the deployed app will have **no data** until you either remove `data/` from `.gitignore` and push the CSVs (if size is OK) or run the fetch scripts in the cloud (advanced). For a quick demo or layout check, deploy as-is; for full data on the cloud, push the data or run the pipeline there.

## Next steps (analytics)

After data is fetched you can:

- **Player level**: Aggregate box_scores_players by player, season, splits (home/away, vs team), rolling averages, etc.
- **Team level**: Aggregate box_scores_teams by team, season, offensive/defensive ratings derived from box scores.
