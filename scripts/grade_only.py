"""Refreshes graded pick results and the track record from real stats and
final scores only -- no odds API or Kalshi calls.

Grading has never actually depended on odds; analyze.py's main() just
happens to also rebuild props.json from live odds in the same pass. This
lets the track record catch up mid-day (e.g. right after the early Sunday
games finish) without spending Odds API quota: it re-fetches the free
nflverse/ESPN data (player stats, schedule/final scores, injuries) via
fetch_stats.py, then re-grades and rewrites data/track_record.json. It
does not touch data/history/picks_*.json or props.json/game_props.json --
those still reflect the last full run, unchanged.

Usage: python scripts/grade_only.py
"""
import json
import os

import fetch_stats
import pandas as pd
from analyze import build_track_record, grade_past_weeks
from common import DATA_DIR


def main():
    fetch_stats.main()

    with open(os.path.join(DATA_DIR, "season_week.json")) as f:
        season_week = json.load(f)
    stats_df = pd.read_csv(os.path.join(DATA_DIR, "player_stats_recent.csv"), low_memory=False)
    games_path = os.path.join(DATA_DIR, "games_recent.csv")
    games = pd.read_csv(games_path, low_memory=False) if os.path.exists(games_path) else pd.DataFrame()

    current_season = season_week["upcoming_season"] or int(stats_df["season"].max())
    grade_past_weeks(stats_df, games, current_season, season_week["upcoming_week"])

    track_record = build_track_record()
    with open(os.path.join(DATA_DIR, "track_record.json"), "w") as f:
        json.dump(track_record, f)
    print(f"Wrote track record ({track_record['weeks_graded']} weeks graded) -> data/track_record.json")


if __name__ == "__main__":
    main()
