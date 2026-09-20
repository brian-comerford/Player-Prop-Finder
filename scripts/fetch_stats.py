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
    nflverse_pbp_url,
    stats_season_and_upcoming_week,
)

RAW_DIR = os.path.join(DATA_DIR, "raw")
PBP_ID_COLS = ["passer_player_id", "rusher_player_id", "receiver_player_id"]

# Columns pulled from play-by-play to aggregate real per-game player stat
# lines (see build_recent_stats_from_pbp) for seasons the official
# player_stats release hasn't caught up to yet.
GAP_SEASON_PBP_COLS = [
    "season",
    "week",
    "season_type",
    "posteam",
    "defteam",
    "two_point_attempt",
    "passer_player_id",
    "passing_yards",
    "pass_touchdown",
    "pass_attempt",
    "rusher_player_id",
    "rushing_yards",
    "rush_touchdown",
    "rush_attempt",
    "receiver_player_id",
    "receiving_yards",
    "complete_pass",
]

ROSTER_URL_TEMPLATE = (
    "https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_{season}.csv"
)


def download(url, dest, timeout=120):
    print(f"Downloading {url}")
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)
    print(f"  -> saved {dest} ({len(resp.content):,} bytes)")


def load_roster_info(season):
    """{player_id: (display_name, position)} from nflverse's weekly roster
    release for `season`. Play-by-play has no position column and only
    abbreviated names (e.g. "T.Kelce"), so this backfills both from the
    roster snapshot instead.
    """
    dest = os.path.join(RAW_DIR, f"roster_{season}.csv")
    try:
        download(ROSTER_URL_TEMPLATE.format(season=season), dest)
    except requests.RequestException as exc:
        print(f"  no roster available yet for {season} ({exc}); skipping")
        return {}
    roster = pd.read_csv(dest, low_memory=False, usecols=["gsis_id", "full_name", "position", "week"])
    os.remove(dest)
    roster = roster[roster["gsis_id"].notna()]
    # Position/team rarely change mid-season; take each player's most
    # recent roster snapshot rather than trying to align on exact week.
    latest = roster.sort_values("week").groupby("gsis_id").tail(1)
    return {row["gsis_id"]: (row["full_name"], row["position"]) for _, row in latest.iterrows()}


def build_recent_stats_from_pbp(seasons):
    """Real per-game player stat lines aggregated directly from play-by-play
    for seasons the nflverse `player_stats` release hasn't published yet --
    it's a heavier, pre-aggregated release that can lag a full season
    behind (see nflverse_pbp_url()), which otherwise leaves every
    projection stuck on last season's numbers (including its playoffs)
    even once a new season is well underway.

    Also derives the last-confirmed-active (season, week) for every player
    who touched the ball, from the same pass over each season's
    play-by-play, so we only download it once per season.

    Returns (stats_df, activity) where stats_df has the columns
    analyze.py actually reads (a subset of the official player_stats
    schema) and activity is {player_id: {"season": S, "week": W}}.
    """
    stat_frames = []
    activity_frames = []

    for season in seasons:
        pbp_dest = os.path.join(RAW_DIR, f"pbp_{season}.csv")
        try:
            download(nflverse_pbp_url(season), pbp_dest)
        except requests.RequestException as exc:
            print(f"  no play-by-play available yet for {season} ({exc}); skipping")
            continue
        pbp = pd.read_csv(pbp_dest, low_memory=False, usecols=lambda c: c in GAP_SEASON_PBP_COLS)
        os.remove(pbp_dest)
        pbp = pbp[pbp["season_type"].isin(["REG", "POST"])]
        pbp = pbp[pbp["two_point_attempt"] != 1]

        for col in PBP_ID_COLS:
            appearances = pbp.loc[pbp[col].notna(), ["season", "week", col]].rename(
                columns={col: "player_id"}
            )
            activity_frames.append(appearances)

        passing = (
            pbp[(pbp["pass_attempt"] == 1) & pbp["passer_player_id"].notna()]
            .groupby(["passer_player_id", "season", "week"])
            .agg(
                attempts=("pass_attempt", "sum"),
                passing_yards=("passing_yards", "sum"),
                passing_tds=("pass_touchdown", "sum"),
                recent_team=("posteam", "first"),
                opponent_team=("defteam", "first"),
                season_type=("season_type", "first"),
            )
            .reset_index()
            .rename(columns={"passer_player_id": "player_id"})
        )
        rushing = (
            pbp[(pbp["rush_attempt"] == 1) & pbp["rusher_player_id"].notna()]
            .groupby(["rusher_player_id", "season", "week"])
            .agg(
                carries=("rush_attempt", "sum"),
                rushing_yards=("rushing_yards", "sum"),
                rushing_tds=("rush_touchdown", "sum"),
                recent_team=("posteam", "first"),
                opponent_team=("defteam", "first"),
                season_type=("season_type", "first"),
            )
            .reset_index()
            .rename(columns={"rusher_player_id": "player_id"})
        )
        receiving = (
            pbp[(pbp["pass_attempt"] == 1) & pbp["receiver_player_id"].notna()]
            .groupby(["receiver_player_id", "season", "week"])
            .agg(
                targets=("pass_attempt", "sum"),
                receptions=("complete_pass", "sum"),
                receiving_yards=("receiving_yards", "sum"),
                receiving_tds=("pass_touchdown", "sum"),
                recent_team=("posteam", "first"),
                opponent_team=("defteam", "first"),
                season_type=("season_type", "first"),
            )
            .reset_index()
            .rename(columns={"receiver_player_id": "player_id"})
        )

        merged = passing.merge(
            rushing, on=["player_id", "season", "week"], how="outer", suffixes=("", "_rush")
        ).merge(receiving, on=["player_id", "season", "week"], how="outer", suffixes=("", "_recv"))
        for col in ("recent_team", "opponent_team", "season_type"):
            for suffix in ("_rush", "_recv"):
                other = f"{col}{suffix}"
                if other in merged.columns:
                    merged[col] = merged[col].combine_first(merged[other])
                    merged = merged.drop(columns=[other])

        stat_cols = [
            "attempts", "passing_yards", "passing_tds",
            "carries", "rushing_yards", "rushing_tds",
            "targets", "receptions", "receiving_yards", "receiving_tds",
        ]
        for col in stat_cols:
            merged[col] = merged[col].fillna(0.0) if col in merged.columns else 0.0

        roster_info = load_roster_info(season)
        names_positions = merged["player_id"].map(roster_info)
        merged["player_display_name"] = names_positions.map(
            lambda t: t[0] if isinstance(t, tuple) else None
        )
        merged["position"] = names_positions.map(lambda t: t[1] if isinstance(t, tuple) else None)
        # A handful of ids (practice-squad call-ups mid-week, etc.) won't
        # match a roster snapshot -- drop rather than guess their position.
        merged = merged[merged["player_display_name"].notna() & merged["position"].notna()]
        stat_frames.append(merged)

    if not stat_frames:
        return pd.DataFrame(), {}

    stats_df = pd.concat(stat_frames, ignore_index=True)

    if not activity_frames:
        activity = {}
    else:
        all_appearances = pd.concat(activity_frames, ignore_index=True)
        latest = all_appearances.sort_values(["season", "week"]).groupby("player_id").tail(1)
        activity = {
            row["player_id"]: {"season": int(row["season"]), "week": int(row["week"])}
            for _, row in latest.iterrows()
        }
    return stats_df, activity


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

    # player_stats can lag the real season by a while (it's a heavier,
    # pre-aggregated release); bridge that gap by aggregating real per-game
    # stat lines straight from play-by-play for every season it's missing,
    # so projections reflect what a player has actually done recently
    # instead of stalling on last season's numbers once a new season is
    # already underway. A no-op once player_stats itself is caught up.
    gap_seasons = (
        range(baseline_season + 1, upcoming_season + 1)
        if upcoming_season is not None and upcoming_season > baseline_season
        else range(0)
    )
    gap_stats, activity = build_recent_stats_from_pbp(gap_seasons)
    if not gap_stats.empty:
        print(
            f"  Aggregated {len(gap_stats):,} player-game rows from play-by-play "
            f"for seasons {list(gap_seasons)}"
        )
        filtered = pd.concat([filtered, gap_stats], ignore_index=True)

    out_stats = os.path.join(DATA_DIR, "player_stats_recent.csv")
    filtered.to_csv(out_stats, index=False)
    print(
        f"Wrote {len(filtered):,} rows for seasons {sorted(keep_seasons | set(gap_seasons))} "
        f"-> {out_stats}"
    )

    wanted_seasons = (
        keep_seasons | ({upcoming_season} if upcoming_season is not None else set()) | set(gap_seasons)
    )
    out_games = os.path.join(DATA_DIR, "games_recent.csv")
    games[games["season"].isin(wanted_seasons)].to_csv(out_games, index=False)
    print(f"Wrote schedule rows -> {out_games}")

    with open(os.path.join(DATA_DIR, "player_activity.json"), "w") as f:
        json.dump(activity, f)
    print(f"Wrote {len(activity):,} player activity records -> data/player_activity.json")

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
