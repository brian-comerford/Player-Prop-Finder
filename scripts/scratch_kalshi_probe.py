"""Scratch probe #2: run the actual (now-fixed) fetch_kalshi_quotes()
end-to-end against real data, to verify the career-market fix and comma-
parsing fix actually clean up production output. Deleted after use.
"""
import json
import os

import fetch_stats
import pandas as pd
from common import DATA_DIR
from kalshi import fetch_kalshi_quotes


def main():
    fetch_stats.main()

    with open(os.path.join(DATA_DIR, "season_week.json")) as f:
        season_week = json.load(f)
    games = pd.read_csv(os.path.join(DATA_DIR, "games_recent.csv"), low_memory=False)
    slate = games[
        (games["season"] == season_week["upcoming_season"])
        & (games["week"] == season_week["upcoming_week"])
    ]
    stats_df = pd.read_csv(os.path.join(DATA_DIR, "player_stats_recent.csv"), low_memory=False)

    print("=" * 80)
    print("Running fetch_kalshi_quotes with the fix applied...")
    quotes = fetch_kalshi_quotes(slate, stats_df)
    print(f"Total quotes returned: {len(quotes)}")
    by_market = {}
    for q in quotes:
        by_market.setdefault(q["market"], []).append(q)
    for mkey, qs in by_market.items():
        print(f"  {mkey}: {len(qs)} quotes")
    print()
    print("First 40 quotes:")
    for q in quotes[:40]:
        print(f"  {q['player_name']:25s} {q['market']:25s} point={q['point']} "
              f"price_over={q['price_over']} price_under={q['price_under']}")


if __name__ == "__main__":
    main()
