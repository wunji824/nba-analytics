"""Configuration for NBA data pipeline and analytics."""

from pathlib import Path

# Directory for CSVs (schedule, box scores)
DATA_DIR = Path(__file__).resolve().parent / "data"

# Seasons to fetch (format: "YYYY-YY", e.g. "2023-24")
# LeagueGameFinder uses this format for the Season parameter.
# 2022-23 = first full season uninterrupted by COVID; 2025-26 = ongoing.
SEASONS = [
    "2022-23",
    "2023-24",
    "2024-25",
    "2025-26",
]

# Season type: "Regular Season" | "Playoffs" | "All Star" | "Pre Season"
SEASON_TYPE = "Regular Season"

# Delay between API calls (seconds) to reduce rate-limit risk
REQUEST_DELAY_SECONDS = 0.6
