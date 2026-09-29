"""Refreshes graded pick results and the track record from real stats and
final scores only -- no odds API or Kalshi calls.

Grading has never actually depended on odds; analyze.py's main() just
happens to also rebuild props.json from live odds in the same pass. This
lets the track record catch up mid-day (e.g. right after the early Sunday
games finish) without spending Odds API quota: it re-fetches the free
nflverse/ESPN data (player stats, schedule/final scores, injuries) via
fetch_stats.py and team-game stats via fetch_team_stats.py, then re-grades
and rewrites the player, Anytime TD, and game track records. It does not
touch data/history/picks_*.json, data/history/game_picks_*.json,
props.json, anytime_td_props.json, or game_props.json -- those still
reflect the last full run, unchanged.

Usage: python scripts/grade_only.py
"""
import json
import os

import fetch_stats
import fetch_team_stats
import pandas as pd
from analyze import build_track_record, build_track_record_detail, grade_past_weeks
from analyze_games import (
    build_game_track_record,
    build_game_track_record_detail,
    grade_past_game_weeks,
)
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

    def is_anytime_td(p):
        return p["market"] == "player_anytime_td"

    def is_not_anytime_td(p):
        return p["market"] != "player_anytime_td"

    track_record = build_track_record(is_not_anytime_td)
    with open(os.path.join(DATA_DIR, "track_record.json"), "w") as f:
        json.dump(track_record, f)
    print(f"Wrote track record ({track_record['weeks_graded']} weeks graded) -> data/track_record.json")

    track_record_detail = build_track_record_detail(is_not_anytime_td)
    with open(os.path.join(DATA_DIR, "track_record_detail.json"), "w") as f:
        json.dump(track_record_detail, f)
    print(
        f"Wrote track record detail ({len(track_record_detail['picks'])} graded picks) "
        "-> data/track_record_detail.json"
    )

    anytime_td_track_record = build_track_record(is_anytime_td)
    with open(os.path.join(DATA_DIR, "anytime_td_track_record.json"), "w") as f:
        json.dump(anytime_td_track_record, f)
    print(
        f"Wrote Anytime TD track record ({anytime_td_track_record['weeks_graded']} weeks graded) "
        "-> data/anytime_td_track_record.json"
    )

    anytime_td_track_record_detail = build_track_record_detail(is_anytime_td)
    with open(os.path.join(DATA_DIR, "anytime_td_track_record_detail.json"), "w") as f:
        json.dump(anytime_td_track_record_detail, f)
    print(
        f"Wrote Anytime TD track record detail ({len(anytime_td_track_record_detail['picks'])} graded picks) "
        "-> data/anytime_td_track_record_detail.json"
    )

    fetch_team_stats.main(season_week["upcoming_season"])
    team_stats_path = os.path.join(DATA_DIR, "team_game_stats.csv")
    team_stats = pd.read_csv(team_stats_path, low_memory=False) if os.path.exists(team_stats_path) else pd.DataFrame()
    grade_past_game_weeks(games, team_stats, season_week["upcoming_season"], season_week["upcoming_week"])

    game_track_record = build_game_track_record()
    with open(os.path.join(DATA_DIR, "game_track_record.json"), "w") as f:
        json.dump(game_track_record, f)
    print(
        f"Wrote game track record ({game_track_record['weeks_graded']} weeks graded) "
        "-> data/game_track_record.json"
    )

    game_track_record_detail = build_game_track_record_detail()
    with open(os.path.join(DATA_DIR, "game_track_record_detail.json"), "w") as f:
        json.dump(game_track_record_detail, f)
    print(
        f"Wrote game track record detail ({len(game_track_record_detail['picks'])} graded picks) "
        "-> data/game_track_record_detail.json"
    )


if __name__ == "__main__":
    main()
