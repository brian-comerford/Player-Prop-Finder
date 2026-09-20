"""Download NFL player stats and schedules from the free, public nflverse
data releases (https://github.com/nflverse/nflverse-data) and cache the
current + previous season locally as CSV for the analysis step.

No API key is required for this data.
"""
import json
import os

import pandas as pd
import requests

from common import (
    DATA_DIR,
    NFLVERSE_GAMES_URL,
    NFLVERSE_PLAYER_STATS_URL,
    stats_season_and_upcoming_week,
)

RAW_DIR = os.path.join(DATA_DIR, "raw")


def download(url, dest, timeout=120):
    print(f"Downloading {url}")
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)
    print(f"  -> saved {dest} ({len(resp.content):,} bytes)")


def main():
    os.makedirs(RAW_DIR, exist_ok=True)

    games_path = os.path.join(RAW_DIR, "games.csv")
    download(NFLVERSE_GAMES_URL, games_path)
    games = pd.read_csv(games_path, low_memory=False)

    stats_path = os.path.join(RAW_DIR, "player_stats_full.csv")
    download(NFLVERSE_PLAYER_STATS_URL, stats_path)
    stats = pd.read_csv(stats_path, low_memory=False)

    baseline_season, upcoming_season, upcoming_week = stats_season_and_upcoming_week(games, stats)
    print(
        f"baseline_season={baseline_season} upcoming_season={upcoming_season} "
        f"upcoming_week={upcoming_week}"
    )

    keep_seasons = {baseline_season, baseline_season - 1}
    filtered = stats[stats["season"].isin(keep_seasons)].copy()
    filtered = filtered[filtered["season_type"].isin(["REG", "POST"])]

    out_stats = os.path.join(DATA_DIR, "player_stats_recent.csv")
    filtered.to_csv(out_stats, index=False)
    print(f"Wrote {len(filtered):,} rows for seasons {sorted(keep_seasons)} -> {out_stats}")

    wanted_seasons = keep_seasons | ({upcoming_season} if upcoming_season is not None else set())
    out_games = os.path.join(DATA_DIR, "games_recent.csv")
    games[games["season"].isin(wanted_seasons)].to_csv(out_games, index=False)
    print(f"Wrote schedule rows -> {out_games}")

    with open(os.path.join(DATA_DIR, "season_week.json"), "w") as f:
        json.dump(
            {
                "baseline_season": baseline_season,
                "upcoming_season": upcoming_season,
                "upcoming_week": upcoming_week,
            },
            f,
        )

    # Clean up the large raw download; we only need the filtered CSVs.
    os.remove(stats_path)


if __name__ == "__main__":
    main()
