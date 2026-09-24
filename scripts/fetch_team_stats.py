"""Downloads play-by-play for the season being projected for, plus at most
one season back (never further -- see analyze_games.py), and aggregates
each team's scoring components per game: rushing TDs, passing TDs, and
field goals made, both for that team's own offense and for what its
defense allowed, split into full game / 1st half / 2nd half.

This is the raw input the game-level spread/total model weights and
compares team-vs-opponent, the same way player props compare a player's
own rate to what their opponent allows at the position level. 2nd-half
segments exclude overtime (standard sportsbook settlement for 2H bets);
full-game segments include it, since a full-game bet settles on the
actual final score.

Output: data/team_game_stats.csv, one row per (season, week, team).
"""
import os

import pandas as pd
import requests

from common import DATA_DIR, nflverse_pbp_url

RAW_DIR = os.path.join(DATA_DIR, "raw")

TEAM_STATS_PBP_COLS = [
    "season",
    "week",
    "season_type",
    "posteam",
    "defteam",
    "game_half",
    "two_point_attempt",
    "pass_touchdown",
    "rush_touchdown",
    "field_goal_result",
]

# (column_suffix, game_half filter). "full" includes overtime (a full-game
# bet settles on the real final score); "h2" excludes it (2nd-half bets
# settle on regulation only).
SEGMENTS = [
    ("full", None),
    ("h1", "Half1"),
    ("h2", "Half2"),
]


def _download(url, dest, timeout=180):
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)


def _segment_stats(pbp, suffix, half_filter):
    seg = pbp if half_filter is None else pbp[pbp["game_half"] == half_filter]

    def counts(team_col, mask):
        return seg[mask].groupby(["season", "week", team_col]).size()

    return {
        f"rushing_tds_{suffix}": counts("posteam", seg["rush_touchdown"] == 1),
        f"passing_tds_{suffix}": counts("posteam", seg["pass_touchdown"] == 1),
        f"field_goals_{suffix}": counts("posteam", seg["field_goal_result"] == "made"),
        f"rushing_tds_allowed_{suffix}": counts("defteam", seg["rush_touchdown"] == 1),
        f"passing_tds_allowed_{suffix}": counts("defteam", seg["pass_touchdown"] == 1),
        f"field_goals_allowed_{suffix}": counts("defteam", seg["field_goal_result"] == "made"),
    }


def build_team_game_stats(seasons):
    """Returns a DataFrame with one row per (season, week, team) that
    actually played, plus their opponent that week and every segment's
    scoring-component counts (0 where nothing scored, not missing).
    """
    frames = []
    for season in seasons:
        pbp_dest = os.path.join(RAW_DIR, f"pbp_team_{season}.csv")
        try:
            _download(nflverse_pbp_url(season), pbp_dest)
        except requests.RequestException as exc:
            print(f"  no play-by-play available yet for {season} ({exc}); skipping")
            continue
        pbp = pd.read_csv(pbp_dest, low_memory=False, usecols=lambda c: c in TEAM_STATS_PBP_COLS)
        os.remove(pbp_dest)
        pbp = pbp[pbp["season_type"].isin(["REG", "POST"])]
        pbp = pbp[pbp["two_point_attempt"] != 1]

        base = (
            pbp[["season", "week", "posteam", "defteam"]]
            .dropna(subset=["posteam", "defteam"])
            .drop_duplicates(subset=["season", "week", "posteam"])
            .rename(columns={"posteam": "team", "defteam": "opponent"})
            .set_index(["season", "week", "team"])
        )

        stat_series = {}
        for suffix, half_filter in SEGMENTS:
            stat_series.update(_segment_stats(pbp, suffix, half_filter))

        season_df = base.copy()
        for col, series in stat_series.items():
            series = series.rename_axis(["season", "week", "team"])
            season_df[col] = series
        season_df = season_df.fillna(0)
        for col in stat_series:
            season_df[col] = season_df[col].astype(int)

        frames.append(season_df.reset_index())
        print(f"  Aggregated team-game stats for {season}: {len(season_df)} team-games")

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def main(upcoming_season):
    """Only ever looks at the season being projected for and the one
    immediately before it -- see analyze_games.py's docstring for why.
    """
    if upcoming_season is None:
        team_stats = pd.DataFrame()
    else:
        seasons = [upcoming_season - 1, upcoming_season]
        team_stats = build_team_game_stats(seasons)

    out_path = os.path.join(DATA_DIR, "team_game_stats.csv")
    team_stats.to_csv(out_path, index=False)
    print(f"Wrote {len(team_stats):,} team-game rows -> data/team_game_stats.csv")


if __name__ == "__main__":
    import json

    with open(os.path.join(DATA_DIR, "season_week.json")) as f:
        season_week = json.load(f)
    main(season_week["upcoming_season"])
