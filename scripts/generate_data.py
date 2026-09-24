"""Runs the full data pipeline: fetch stats -> fetch odds -> analyze, for
both player props and game-level (spread/total) bets.

Usage: python scripts/generate_data.py
Requires ODDS_API_KEY in the environment for live odds; otherwise falls
back to clearly-labeled sample odds automatically for player props (game
odds have no sample fallback -- see fetch_game_odds.py).
"""
import json
import os

import analyze
import analyze_games
import fetch_game_odds
import fetch_odds
import fetch_stats
import fetch_team_stats
from common import DATA_DIR


def main():
    print("== 1/5 fetching player stats & schedule ==")
    fetch_stats.main()
    print("\n== 2/5 fetching odds ==")
    fetch_odds.main()
    print("\n== 3/5 running value model ==")
    analyze.main()

    with open(os.path.join(DATA_DIR, "season_week.json")) as f:
        upcoming_season = json.load(f)["upcoming_season"]

    print("\n== 4/5 fetching team stats & game odds ==")
    fetch_team_stats.main(upcoming_season)
    fetch_game_odds.main()
    print("\n== 5/5 running game value model ==")
    analyze_games.main()


if __name__ == "__main__":
    main()
