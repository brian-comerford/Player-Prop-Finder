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
    "sack",
    "interception",
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
INJURIES_URL_TEMPLATE = (
    "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv"
)
ESPN_PROJECTIONS_URL_TEMPLATE = (
    "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{season}/players"
    "?view=kona_player_info&scoringPeriodId={week}"
)
PLAYER_ID_CROSSWALK_URL = (
    "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
)

# ESPN's own weekly projections are keyed by internal numeric stat IDs
# rather than named fields; this is the subset relevant to our own markets,
# carried over from a working reference integration (fantasy-command-center)
# that already reverse-engineered and tested it against ESPN's live data.
ESPN_STAT_IDS = {
    3: "pass_yd", 4: "pass_td",
    24: "rush_yd", 25: "rush_td",
    41: "rec", 53: "rec", 42: "rec_yd", 43: "rec_td",
}


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


def fetch_injury_report(season, week):
    """{player_id: {"status": "Out"|"Doubtful"|"Questionable", "injury": str
    or None}} from nflverse's official weekly injury report for the
    upcoming game, wherever it's been published yet (teams file these
    Wed-Fri before Sunday games, so it can be partial or absent early in
    the week). Players with no listed designation aren't included.

    This is real, current-week injury status -- a different signal from
    the play-by-play-derived "still active this season" check elsewhere
    in this module, and catches something that can't: an every-week
    starter who got hurt *this* week.
    """
    dest = os.path.join(RAW_DIR, f"injuries_{season}.csv")
    try:
        download(INJURIES_URL_TEMPLATE.format(season=season), dest)
    except requests.RequestException as exc:
        print(f"  no injury report available yet for {season} ({exc}); skipping")
        return {}
    injuries = pd.read_csv(
        dest,
        low_memory=False,
        usecols=["season", "week", "gsis_id", "report_status", "report_primary_injury"],
    )
    os.remove(dest)
    week_rows = injuries[
        (injuries["week"] == week) & injuries["gsis_id"].notna() & injuries["report_status"].notna()
    ]
    return {
        row["gsis_id"]: {
            "status": row["report_status"],
            "injury": row["report_primary_injury"] if pd.notna(row["report_primary_injury"]) else None,
        }
        for _, row in week_rows.iterrows()
    }


def fetch_espn_projections(season, week):
    """{gsis_id: {stat_key: projected_value}} for this week, from ESPN's
    public (but unofficial/undocumented) fantasy football projections
    endpoint -- a second, independent projection system used in analyze.py
    as a sanity check against our own model, to raise or lower confidence
    when they agree or disagree.

    ESPN's own player IDs don't match nflverse's gsis_id, so this joins
    through a community-maintained ID crosswalk (dynastyprocess/data) that
    carries both.

    Best-effort like fetch_injury_report above: returns {} on any network
    hiccup or unexpected response shape rather than failing the whole
    pipeline, since this is a supplementary signal, not a required one.
    """
    crosswalk_dest = os.path.join(RAW_DIR, "player_id_crosswalk.csv")
    try:
        download(PLAYER_ID_CROSSWALK_URL, crosswalk_dest)
        crosswalk = pd.read_csv(crosswalk_dest, low_memory=False, usecols=["gsis_id", "espn_id"])
    except (requests.RequestException, ValueError) as exc:
        print(f"  player ID crosswalk unavailable ({exc}); skipping ESPN projections")
        return {}
    finally:
        if os.path.exists(crosswalk_dest):
            os.remove(crosswalk_dest)

    crosswalk = crosswalk.dropna(subset=["gsis_id", "espn_id"])
    espn_to_gsis = {str(int(row.espn_id)): row.gsis_id for row in crosswalk.itertuples()}

    try:
        resp = requests.get(
            ESPN_PROJECTIONS_URL_TEMPLATE.format(season=season, week=week),
            headers={"x-fantasy-filter": json.dumps({"players": {"filterActive": {"value": True}}})},
            timeout=180,
        )
        resp.raise_for_status()
        espn_players = resp.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"  ESPN projections unavailable ({exc}); skipping")
        return {}
    if not isinstance(espn_players, list):
        print("  ESPN projections response shape changed unexpectedly; skipping")
        return {}

    projections = {}
    for player in espn_players:
        gsis_id = espn_to_gsis.get(str(player.get("id")))
        if gsis_id is None:
            continue
        entry = next(
            (
                s
                for s in player.get("stats", [])
                if s.get("scoringPeriodId") == week
                and s.get("seasonId") == season
                and s.get("statSourceId") == 1
                and s.get("statSplitTypeId") == 1
            ),
            None,
        )
        if entry is None or not entry.get("stats"):
            continue
        stats = {
            name: entry["stats"][str(stat_id)]
            for stat_id, name in ESPN_STAT_IDS.items()
            if str(stat_id) in entry["stats"]
        }
        if stats:
            projections[gsis_id] = stats
    return projections


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

        # pbp's pass_attempt also flags sacks, which the official box score
        # (and the books' Pass Attempts lines) don't count as attempts.
        passing = (
            pbp[(pbp["pass_attempt"] == 1) & (pbp["sack"] != 1) & pbp["passer_player_id"].notna()]
            .groupby(["passer_player_id", "season", "week"])
            .agg(
                attempts=("pass_attempt", "sum"),
                passing_yards=("passing_yards", "sum"),
                passing_tds=("pass_touchdown", "sum"),
                interceptions=("interception", "sum"),
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
            "attempts", "passing_yards", "passing_tds", "interceptions",
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


OFFICIAL_WEEKLY_URL_TEMPLATE = (
    "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv"
)
# nflverse's newer weekly release -> the columns the rest of the pipeline
# reads (named as in the older player_stats release used for 2023-24).
OFFICIAL_COLUMNS = {
    "player_id": "player_id", "player_display_name": "player_display_name", "position": "position",
    "season": "season", "week": "week", "season_type": "season_type",
    "team": "recent_team", "opponent_team": "opponent_team",
    "completions": "completions", "attempts": "attempts", "passing_yards": "passing_yards",
    "passing_tds": "passing_tds", "passing_interceptions": "interceptions",
    "carries": "carries", "rushing_yards": "rushing_yards", "rushing_tds": "rushing_tds",
    "targets": "targets", "receptions": "receptions", "receiving_yards": "receiving_yards",
    "receiving_tds": "receiving_tds",
}


OFFENSIVE_POSITIONS = {"QB", "RB", "FB", "WR", "TE"}
TWO_WAY_MIN_TOUCHES = 5


def load_official_weekly(season):
    """nflverse's official per-game player stats for `season` (its
    stats_player release), or an empty frame if it isn't published or
    can't be read. Preferred over our own play-by-play aggregation, which
    once missed interceptions entirely and counted sacks as pass attempts,
    and still drifts on edge cases (laterals, some penalty plays)."""
    dest = os.path.join(RAW_DIR, f"stats_player_week_{season}.csv")
    try:
        download(OFFICIAL_WEEKLY_URL_TEMPLATE.format(season=season), dest)
        df = pd.read_csv(dest, low_memory=False, usecols=lambda c: c in OFFICIAL_COLUMNS)
    except (requests.RequestException, ValueError) as exc:
        print(f"  no official weekly stats for {season} ({exc}); using play-by-play totals")
        return pd.DataFrame()
    finally:
        if os.path.exists(dest):
            os.remove(dest)
    df = df.rename(columns=OFFICIAL_COLUMNS)
    # Offense only, like the older player_stats release: defensive and
    # special-teams rows would pad every league average with zeros.
    df = df[df["season_type"].isin(["REG", "POST"])]
    # ...but keep a two-way player (e.g. Travis Hunter, listed CB) for every
    # game of a season he had a real offensive role in (TWO_WAY_MIN_TOUCHES;
    # a punter's fake or a lineman's trick play doesn't count) -- a game he played
    # only on defense still counts as played (0 targets), the way a book
    # grades it -- as a receiver or runner by what he did on offense.
    off_stats = df[["attempts", "carries", "targets"]].fillna(0)
    season_touches = off_stats.sum(axis=1).groupby(df["player_id"]).transform("sum")
    season_targets = off_stats["targets"].groupby(df["player_id"]).transform("sum")
    two_way = ~df["position"].isin(OFFENSIVE_POSITIONS) & (season_touches >= TWO_WAY_MIN_TOUCHES)
    df.loc[two_way, "position"] = season_targets[two_way].gt(0).map({True: "WR", False: "RB"})
    df = df[df["position"].isin(OFFENSIVE_POSITIONS)]
    stat_cols = [c for c in OFFICIAL_COLUMNS.values() if c not in (
        "player_id", "player_display_name", "position", "season", "week", "season_type",
        "recent_team", "opponent_team")]
    df[stat_cols] = df[stat_cols].fillna(0.0)
    return df


def prefer_official(pbp_stats, official):
    """Official rows for every team-game the official file has, and our
    play-by-play rows only for team-games it hasn't posted yet (it can lag
    the latest games by a day or so). `stats_source` records which, so
    grading can wait for the official numbers before freezing a week."""
    if official.empty:
        return pbp_stats.assign(stats_source="pbp")
    keys = ["season", "week", "recent_team"]
    covered = set(map(tuple, official[keys].drop_duplicates().itertuples(index=False, name=None)))
    fallback = pbp_stats[
        [k not in covered for k in map(tuple, pbp_stats[keys].itertuples(index=False, name=None))]
    ]
    if len(fallback):
        games = fallback[keys].drop_duplicates().sort_values(keys)
        print(f"  official stats not posted yet for {len(games)} team-games; using play-by-play totals for those")
    return pd.concat(
        [official.assign(stats_source="official"), fallback.assign(stats_source="pbp")],
        ignore_index=True,
    )


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
    official = [load_official_weekly(season) for season in gap_seasons]
    official = [df for df in official if not df.empty]
    if official:
        official = pd.concat(official, ignore_index=True)
        print(f"  Official weekly stats: {len(official):,} player-game rows")
        gap_stats = prefer_official(gap_stats, official)
    elif not gap_stats.empty:
        gap_stats = gap_stats.assign(stats_source="pbp")
    if not gap_stats.empty:
        print(
            f"  {len(gap_stats):,} player-game rows for seasons {list(gap_seasons)} "
            f"({(gap_stats['stats_source'] == 'official').sum():,} official, "
            f"{(gap_stats['stats_source'] == 'pbp').sum():,} play-by-play)"
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

    injury_report = {}
    if upcoming_season is not None and upcoming_week is not None:
        injury_report = fetch_injury_report(upcoming_season, upcoming_week)
    with open(os.path.join(DATA_DIR, "injury_report.json"), "w") as f:
        json.dump(injury_report, f)
    print(f"Wrote {len(injury_report):,} injury report entries -> data/injury_report.json")

    espn_projections = {}
    if upcoming_season is not None and upcoming_week is not None:
        espn_projections = fetch_espn_projections(upcoming_season, upcoming_week)
    with open(os.path.join(DATA_DIR, "espn_projections.json"), "w") as f:
        json.dump(espn_projections, f)
    print(f"Wrote {len(espn_projections):,} ESPN projection entries -> data/espn_projections.json")

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
