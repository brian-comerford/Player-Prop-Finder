"""Shared constants and helpers for the data pipeline."""
import datetime as dt
import math
import os
import re

import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Recency/season weighting shared by both the player-prop model (analyze.py)
# and the game-level spread/total model (analyze_games.py) -- see
# game_weights() below for what these actually do.
RECENCY_DECAY = 0.88
# Extra per-season penalty on top of the game-by-game recency decay above --
# a game from last season gets an additional SEASON_DECAY**1 multiplier, one
# from two seasons back SEASON_DECAY**2, and so on, while every game in the
# season being projected for keeps its full game-recency weight (multiplier
# 1.0). Games stay ordered most-recent-first regardless of season, so this
# doesn't change the within-season decay shape -- it just makes last
# season's tail end (still fairly high game-recency weight on its own,
# since RECENCY_DECAY alone doesn't know about season boundaries) count for
# distinctly less than this season's own games, which is exactly the
# signal a season boundary should carry: new-season role/scheme/health
# changes make old-season stats a weaker proxy for what a player (or a
# team) will do now, even when the two are only a few games apart by raw
# count.
SEASON_DECAY = 0.6


def game_weights(seasons, current_season):
    """Per-game weight for weighted_mean_std: game-recency decay combined
    with the extra per-season penalty described at SEASON_DECAY above.
    `seasons` is most-recent-first, aligned with the values being weighted.
    """
    return [
        RECENCY_DECAY**i * SEASON_DECAY ** max(0, current_season - int(season))
        for i, season in enumerate(seasons)
    ]


def weighted_mean_std(values, weights):
    """`values`/`weights` aligned, most-recent-first. Returns (mean, std, n)."""
    n = len(values)
    if n == 0:
        return None, None, 0
    values = np.array(values, dtype=float)
    weights = np.array(weights, dtype=float)
    mean = np.average(values, weights=weights)
    var = np.average((values - mean) ** 2, weights=weights)
    std = math.sqrt(var)
    return mean, std, n

NFLVERSE_PLAYER_STATS_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/player_stats/player_stats.csv"
)
NFLVERSE_GAMES_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"
)


def nflverse_pbp_url(season):
    """Play-by-play is nflverse's most actively-maintained feed -- unlike the
    pre-aggregated player_stats release (which can lag real time by a season
    or more), pbp for the current season is updated as games are played. We
    use it only as a lightweight "did this player take any snap recently"
    signal (see scripts/analyze.py), not to recompute full stat lines.
    """
    return f"https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv"

# Maps nflverse's 2-3 letter team codes to the full team names used by
# The Odds API (and most sportsbook feeds).
TEAM_CODE_TO_NAME = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LA": "Los Angeles Rams",
    "LAC": "Los Angeles Chargers",
    "LV": "Las Vegas Raiders",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers",
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
    # Historical / alternate codes nflverse sometimes emits
    "OAK": "Las Vegas Raiders",
    "SD": "Los Angeles Chargers",
    "STL": "Los Angeles Rams",
}
TEAM_NAME_TO_CODE = {v: k for k, v in TEAM_CODE_TO_NAME.items() if k not in ("OAK", "SD", "STL")}

# Markets we model. Keys match The Odds API market keys; `stat_cols` says how
# to derive the same quantity from nflverse's weekly player_stats columns.
MARKETS = {
    "player_pass_yds": {
        "label": "Passing Yards",
        "noun": "passing yards",
        "stat_cols": ["passing_yards"],
        "usage_col": "attempts",
        "position_group": {"QB"},
    },
    "player_pass_tds": {
        "label": "Passing TDs",
        "noun": "passing TDs",
        "stat_cols": ["passing_tds"],
        "usage_col": "attempts",
        "position_group": {"QB"},
    },
    "player_rush_yds": {
        "label": "Rushing Yards",
        "noun": "rushing yards",
        "stat_cols": ["rushing_yards"],
        "usage_col": "carries",
        "position_group": {"RB", "QB", "WR"},
    },
    "player_receptions": {
        "label": "Receptions",
        "noun": "receptions",
        "stat_cols": ["receptions"],
        "usage_col": "targets",
        "position_group": {"WR", "TE", "RB"},
    },
    "player_reception_yds": {
        "label": "Receiving Yards",
        "noun": "receiving yards",
        "stat_cols": ["receiving_yards"],
        "usage_col": "targets",
        "position_group": {"WR", "TE", "RB"},
    },
    "player_rush_reception_yds": {
        "label": "Rush + Rec Yards",
        "noun": "rush+rec yards",
        "stat_cols": ["rushing_yards", "receiving_yards"],
        "usage_col": None,  # combined usage handled specially
        "position_group": {"RB", "WR", "TE"},
    },
    "player_anytime_td": {
        "label": "Anytime TD",
        "noun": "TD",
        # Anytime TD scorer markets pay out on the player rushing or
        # receiving for a score -- a QB's own passing TDs don't count here
        # (that's the separate player_pass_tds market above).
        "stat_cols": ["rushing_tds", "receiving_tds"],
        "usage_col": None,
        "position_group": {"RB", "WR", "TE", "QB"},
        "binary": True,
    },
}


def stats_season_and_upcoming_week(games_df, stats_df):
    """Return (baseline_season, upcoming_season, upcoming_week).

    The two nflverse feeds can lag each other (schedules are published well
    ahead of player stats, and the stats file can take a day or two to catch
    up after games are played), so we don't assume they agree on "now":

    - `baseline_season` is the most recent season we actually have player
      stats for -- that's what player projections are built from.
    - `upcoming_season`/`upcoming_week` is the next slate of games (in that
      same season if one remains, otherwise the following season's week 1)
      that still has no final score, i.e. what we're finding props for.
      Both are None if the schedule has no unplayed games at all.
    """
    baseline_season = int(stats_df["season"].max())

    def first_unplayed(season):
        season_games = games_df[games_df["season"] == season]
        if season_games.empty:
            return None
        unplayed = season_games[
            season_games["home_score"].isna() | (season_games["home_score"] == "")
        ]
        if unplayed.empty:
            return None
        return int(unplayed["week"].astype(int).min())

    max_schedule_season = int(games_df["season"].max())
    for season in range(baseline_season, max_schedule_season + 1):
        week = first_unplayed(season)
        if week is not None:
            return baseline_season, season, week

    return baseline_season, None, None


def american_to_implied_prob(odds):
    """Convert American odds to a raw (vig-included) implied probability."""
    if odds is None:
        return None
    odds = float(odds)
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return -odds / (-odds + 100.0)


def remove_vig_two_way(prob_a, prob_b):
    """Normalize two complementary raw implied probabilities to remove vig."""
    if prob_a is None or prob_b is None:
        return prob_a, prob_b
    total = prob_a + prob_b
    if total <= 0:
        return prob_a, prob_b
    return prob_a / total, prob_b / total


def utcnow_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_name(name):
    return re.sub(r"[^a-z]", "", str(name).lower())


def prob_to_american(p):
    """Convert a 0-1 probability to the American odds that imply it."""
    p = min(max(p, 0.01), 0.99)
    if p >= 0.5:
        return round(-100 * p / (1 - p))
    return round(100 * (1 - p) / p)
