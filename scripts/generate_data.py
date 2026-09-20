"""Runs the full data pipeline: fetch stats -> fetch odds -> analyze.

Usage: python scripts/generate_data.py
Requires ODDS_API_KEY in the environment for live odds; otherwise falls
back to clearly-labeled sample odds automatically.
"""
import fetch_odds
import fetch_stats
import analyze


def main():
    print("== 1/3 fetching player stats & schedule ==")
    fetch_stats.main()
    print("\n== 2/3 fetching odds ==")
    fetch_odds.main()
    print("\n== 3/3 running value model ==")
    analyze.main()


if __name__ == "__main__":
    main()
