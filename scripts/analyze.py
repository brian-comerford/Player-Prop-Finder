"""Core value model: builds a recency-weighted, opponent-adjusted projection
for every player/market we have odds for, converts sportsbook odds to a
no-vig implied probability, and reports the edge between the two.

Output: data/props.json (the list the frontend renders) and data/meta.json
(run metadata: season/week, odds source, generated_at).
"""
import json
import math
import os
import statistics
from collections import Counter

import numpy as np
import pandas as pd
from scipy.stats import norm

from common import (
    DATA_DIR,
    MARKETS,
    american_to_implied_prob,
    normalize_name,
    remove_vig_two_way,
    utcnow_iso,
)

RECENCY_DECAY = 0.88
MIN_GAMES = 3
DEFENSE_FACTOR_BOUNDS = (0.75, 1.25)
MIN_ROWS_FOR_POSITION_FACTOR = 8
TD_PROB_BOUNDS = (0.02, 0.95)

TREND_WINDOW = 10
TREND_MIN_GAMES = 4
TREND_MIN_HIT_RATE = 0.7
MATCHUP_TREND_MIN_GAMES = 3
MATCHUP_TREND_MIN_HIT_RATE = 0.7

# A player who hasn't taken a confirmed snap in this many "league weeks"
# (roughly: games) is treated as inactive/injured/retired and excluded
# entirely, regardless of how good their old stat line looks. Loose enough
# to tolerate a bye week or a short-term injury blip, tight enough to catch
# someone who's been out for a month or missed a full offseason.
INACTIVE_GAMES_MISSED_THRESHOLD = 4
WEEKS_PER_SEASON = 18


def games_missed(last_active_season, last_active_week, upcoming_season, upcoming_week):
    return (upcoming_season - last_active_season) * WEEKS_PER_SEASON + (
        upcoming_week - last_active_week
    )

USAGE_MIN = {
    "player_pass_yds": ("attempts", 5),
    "player_pass_tds": ("attempts", 5),
    "player_rush_yds": ("carries", 2),
    "player_receptions": ("targets", 1),
    "player_reception_yds": ("targets", 1),
    "player_rush_reception_yds": (None, 0),
    "player_anytime_td": (None, 0),
}


def weighted_mean_std(values, decay=RECENCY_DECAY):
    """`values` ordered most-recent-first. Returns (mean, std, n)."""
    n = len(values)
    if n == 0:
        return None, None, 0
    weights = np.array([decay**i for i in range(n)])
    values = np.array(values, dtype=float)
    mean = np.average(values, weights=weights)
    var = np.average((values - mean) ** 2, weights=weights)
    std = math.sqrt(var)
    return mean, std, n


def build_player_baselines(stats_df):
    """Returns {(norm_name, market_key): {mean, std, games, team, recent_games}}."""
    stats_df = stats_df.sort_values(["season", "week"], ascending=False)
    baselines = {}
    team_by_player = {}

    for player_id, group in stats_df.groupby("player_id"):
        display_name = group["player_display_name"].iloc[0]
        position = group["position"].iloc[0]
        norm_name = normalize_name(display_name)
        team_by_player[norm_name] = group["recent_team"].iloc[0]

        for mkey, cfg in MARKETS.items():
            if position not in cfg["position_group"]:
                continue
            usage_col, usage_min = USAGE_MIN[mkey]
            rows = group

            if cfg.get("binary"):
                per_game = (rows[cfg["stat_cols"]].fillna(0).sum(axis=1) > 0).astype(float).tolist()
            else:
                per_game = rows[cfg["stat_cols"]].fillna(0).sum(axis=1).tolist()

            if len(per_game) < MIN_GAMES:
                continue
            if usage_col is not None and rows[usage_col].fillna(0).mean() < usage_min:
                continue

            mean, std, n = weighted_mean_std(per_game)
            floor = max(std, 0.2 * abs(mean), 0.5 if not cfg.get("binary") else 0.03)
            game_log_df = rows[["season", "week", "opponent_team"]].copy()
            game_log_df["value"] = per_game
            game_log = game_log_df.to_dict("records")

            baselines[(norm_name, mkey)] = {
                "player_id": player_id,
                "mean": mean,
                "std": floor,
                "games": n,
                "team": group["recent_team"].iloc[0],
                "position": position,
                "display_name": display_name,
                "game_log": game_log,
                "recent_games": game_log[:8],
                "last_active_season": int(group["season"].iloc[0]),
                "last_active_week": int(group["week"].iloc[0]),
            }
    return baselines, team_by_player


def build_defense_factors(stats_df):
    """{market_key: {"overall": {team: factor}, "by_position": {position: {team: factor}}}}

    How much a defense inflates or suppresses opponents' production in a
    stat, relative to league average -- split by the offensive player's own
    position (QB/RB/WR/TE) wherever there's enough sample to trust it, so a
    defense's rushing/receiving-TD funnel to running backs is judged
    separately from its funnel to receivers and tight ends. This also means
    a running back's receiving production is judged against what a defense
    allows to running backs specifically, not blended in with wideouts.
    Falls back to one blended team factor (all positions combined) when a
    position-specific bucket is too thin to trust.
    """
    factors = {}
    for mkey, cfg in MARKETS.items():
        per_game = stats_df.copy()
        if cfg.get("binary"):
            per_game["_val"] = (per_game[cfg["stat_cols"]].fillna(0).sum(axis=1) > 0).astype(float)
        else:
            per_game["_val"] = per_game[cfg["stat_cols"]].fillna(0).sum(axis=1)

        league_avg = per_game["_val"].mean()
        if not league_avg:
            continue

        overall_by_team = per_game.groupby("opponent_team")["_val"].mean()
        overall_factors = (overall_by_team / league_avg).clip(*DEFENSE_FACTOR_BOUNDS).to_dict()

        by_position = {}
        for position in cfg["position_group"]:
            pos_rows = per_game[per_game["position"] == position]
            pos_league_avg = pos_rows["_val"].mean()
            if not pos_league_avg:
                continue
            row_counts = pos_rows.groupby("opponent_team")["_val"].count()
            pos_factors = (pos_rows.groupby("opponent_team")["_val"].mean() / pos_league_avg).clip(
                *DEFENSE_FACTOR_BOUNDS
            )
            by_position[position] = {
                team: value
                for team, value in pos_factors.items()
                if row_counts.get(team, 0) >= MIN_ROWS_FOR_POSITION_FACTOR
            }

        factors[mkey] = {"overall": overall_factors, "by_position": by_position}
    return factors


def defense_factor_for(defense_factors, market, position, opponent):
    """Position-specific factor when there's enough sample, else the
    blended-across-all-positions factor, else neutral (1.0)."""
    market_factors = defense_factors.get(market, {})
    factor = market_factors.get("by_position", {}).get(position, {}).get(opponent)
    if factor is not None:
        return factor
    return market_factors.get("overall", {}).get(opponent, 1.0)


def bottom_half_teams(defense_factors, market, position):
    """Teams whose defense-factor for this market/position is at or above
    the league median -- i.e. they allow more of this stat than a typical
    defense, so they'd be ranked in the bottom half defensively.
    """
    market_factors = defense_factors.get(market, {})
    factors = market_factors.get("by_position", {}).get(position) or market_factors.get("overall", {})
    if not factors:
        return set()
    median = statistics.median(factors.values())
    return {team for team, factor in factors.items() if factor >= median}


def build_trend_insights(game_log, cfg, line, side, bottom_half_set):
    """Notable, plain-English hit-rate patterns for the recommended side,
    e.g. "Over 3.5 receptions in 4 of last 5 games" or the same measured
    only against bottom-half defenses. Returns [] when nothing clears the
    bar -- most players won't have a notable trend, and that's fine.
    """
    if not game_log:
        return []

    binary = cfg.get("binary", False)

    def is_hit(value):
        if binary:
            return value > 0 if side == "over" else value <= 0
        return value > line if side == "over" else value < line

    if binary:
        verb = "Scored a TD" if side == "over" else "Held without a TD"
    else:
        verb = f"{'Over' if side == 'over' else 'Under'} {line} {cfg['noun']}"

    insights = []

    window = game_log[:TREND_WINDOW]
    n = len(window)
    hits = sum(1 for g in window if is_hit(g["value"]))
    if n >= TREND_MIN_GAMES and hits / n >= TREND_MIN_HIT_RATE:
        insights.append(f"{verb} in {hits} of last {n} games")

    matchup_games = [g for g in game_log if g["opponent_team"] in bottom_half_set]
    if matchup_games != window:
        m = len(matchup_games)
        m_hits = sum(1 for g in matchup_games if is_hit(g["value"]))
        if m >= MATCHUP_TREND_MIN_GAMES and m_hits / m >= MATCHUP_TREND_MIN_HIT_RATE:
            insights.append(f"{verb} in {m_hits} of {m} games vs. bottom-half defenses")

    return insights


def classify_time_slot(weekday, gametime):
    """A human-recognizable NFL broadcast window from a game's weekday and
    ET kickoff time (games.csv gives both already in Eastern time)."""
    if weekday == "Thursday":
        return "Thursday Night"
    if weekday == "Monday":
        return "Monday Night"
    if weekday in ("Friday", "Saturday"):
        return weekday
    if weekday == "Sunday":
        try:
            hour = int(str(gametime).split(":")[0])
        except (ValueError, IndexError):
            return "Sunday"
        if hour < 14:
            return "Sunday Early (1:00 PM ET)"
        if hour < 18:
            return "Sunday Afternoon"
        return "Sunday Night"
    return weekday or "Other"


TIME_SLOT_ORDER = [
    "Thursday Night",
    "Friday",
    "Saturday",
    "Sunday Early (1:00 PM ET)",
    "Sunday Afternoon",
    "Sunday Night",
    "Monday Night",
]


def confidence_label(games, mean, std):
    cv = std / mean if mean else 1.0
    if games >= 8 and cv < 0.6:
        return "High"
    if games >= 5:
        return "Medium"
    return "Low"


def project_probabilities(mean, std, line, binary=False):
    if binary:
        p_yes = min(max(mean, TD_PROB_BOUNDS[0]), TD_PROB_BOUNDS[1])
        return p_yes, 1 - p_yes
    p_over = 1 - norm.cdf(line, loc=mean, scale=std)
    return p_over, 1 - p_over


def main():
    stats_df = pd.read_csv(os.path.join(DATA_DIR, "player_stats_recent.csv"), low_memory=False)
    with open(os.path.join(DATA_DIR, "season_week.json")) as f:
        season_week = json.load(f)
    with open(os.path.join(DATA_DIR, "odds_meta.json")) as f:
        odds_meta = json.load(f)
    with open(os.path.join(DATA_DIR, "odds_quotes.json")) as f:
        quotes = json.load(f)
    with open(os.path.join(DATA_DIR, "player_activity.json")) as f:
        player_activity = json.load(f)

    game_lookup = {}
    matchup_options = []
    if season_week["upcoming_season"] is not None:
        games = pd.read_csv(os.path.join(DATA_DIR, "games_recent.csv"), low_memory=False)
        slate = games[
            (games["season"] == season_week["upcoming_season"])
            & (games["week"] == season_week["upcoming_week"])
        ].sort_values(["gameday", "gametime"])
        for g in slate.itertuples():
            matchup = f"{g.away_team} @ {g.home_team}"
            time_slot = classify_time_slot(g.weekday, g.gametime)
            info = {
                "matchup": matchup,
                "game_date": g.gameday,
                "time_slot": time_slot,
            }
            game_lookup[frozenset((g.home_team, g.away_team))] = info
            matchup_options.append(matchup)

    baselines, team_by_player = build_player_baselines(stats_df)
    defense_factors = build_defense_factors(stats_df)
    bottom_half_cache = {}

    inactive_players = set()
    if season_week["upcoming_season"] is not None:
        active_baselines = {}
        for key, base in baselines.items():
            last_season, last_week = base["last_active_season"], base["last_active_week"]
            pbp_seen = player_activity.get(base["player_id"])
            if pbp_seen and (pbp_seen["season"], pbp_seen["week"]) > (last_season, last_week):
                last_season, last_week = pbp_seen["season"], pbp_seen["week"]

            missed = games_missed(
                last_season, last_week, season_week["upcoming_season"], season_week["upcoming_week"]
            )
            if missed > INACTIVE_GAMES_MISSED_THRESHOLD:
                inactive_players.add(base["display_name"])
                continue
            active_baselines[key] = base
        baselines = active_baselines
        print(
            f"Excluded {len(inactive_players)} players with no confirmed snap in the last "
            f"{INACTIVE_GAMES_MISSED_THRESHOLD} games"
        )

    quote_counts = Counter(q["market"] for q in quotes)
    drop_no_baseline = Counter()
    drop_team_mismatch = Counter()
    drop_no_candidates = Counter()

    props = []
    for q in quotes:
        norm_name = normalize_name(q["player_name"])
        key = (norm_name, q["market"])
        base = baselines.get(key)
        if base is None:
            drop_no_baseline[q["market"]] += 1
            continue

        player_team = base["team"]
        if player_team == q["home_team"]:
            opponent = q["away_team"]
        elif player_team == q["away_team"]:
            opponent = q["home_team"]
        else:
            # Player's team on file doesn't match either side of this game
            # (likely a stale roster snapshot) -- skip rather than guess.
            drop_team_mismatch[q["market"]] += 1
            continue

        game_info = game_lookup.get(frozenset((player_team, opponent)), {})

        cfg = MARKETS[q["market"]]
        factor = defense_factor_for(defense_factors, q["market"], base["position"], opponent)
        projected_mean = base["mean"] * factor

        model_over, model_under = project_probabilities(
            projected_mean, base["std"], q["point"], binary=cfg.get("binary", False)
        )

        raw_over = american_to_implied_prob(q["price_over"])
        raw_under = american_to_implied_prob(q["price_under"])
        if raw_over is not None and raw_under is not None:
            novig_over, novig_under = remove_vig_two_way(raw_over, raw_under)
        else:
            novig_over, novig_under = raw_over, raw_under

        edge_over = (model_over - novig_over) if novig_over is not None else None
        edge_under = (model_under - novig_under) if novig_under is not None else None

        candidates = [
            (side, edge)
            for side, edge in (("over", edge_over), ("under", edge_under))
            if edge is not None
        ]
        if not candidates:
            drop_no_candidates[q["market"]] += 1
            continue
        recommended_side, recommended_edge = max(candidates, key=lambda x: x[1])

        bh_key = (q["market"], base["position"])
        if bh_key not in bottom_half_cache:
            bottom_half_cache[bh_key] = bottom_half_teams(defense_factors, q["market"], base["position"])
        trends = build_trend_insights(
            base["game_log"], cfg, q["point"], recommended_side, bottom_half_cache[bh_key]
        )

        props.append(
            {
                "player_name": base["display_name"],
                "position": base["position"],
                "team": player_team,
                "opponent": opponent,
                "matchup": game_info.get("matchup"),
                "game_date": game_info.get("game_date"),
                "time_slot": game_info.get("time_slot"),
                "market": q["market"],
                "market_label": cfg["label"],
                "line": q["point"],
                "book_over": q["book_over"],
                "book_under": q["book_under"],
                "price_over": q["price_over"],
                "price_under": q["price_under"],
                "model_prob_over": round(model_over, 4),
                "model_prob_under": round(model_under, 4),
                "implied_prob_over": round(novig_over, 4) if novig_over is not None else None,
                "implied_prob_under": round(novig_under, 4) if novig_under is not None else None,
                "edge_over": round(edge_over, 4) if edge_over is not None else None,
                "edge_under": round(edge_under, 4) if edge_under is not None else None,
                "recommended_side": recommended_side,
                "recommended_edge": round(recommended_edge, 4),
                "projected_value": round(projected_mean, 1),
                "defense_factor": round(factor, 3),
                "sample_games": base["games"],
                "confidence": confidence_label(base["games"], base["mean"], base["std"]),
                "recent_games": base["recent_games"],
                "trends": trends,
            }
        )

    props.sort(key=lambda p: p["recommended_edge"], reverse=True)

    final_counts = Counter(p["market"] for p in props)
    print("Per-market quote -> prop funnel:")
    for mkey in MARKETS:
        print(
            f"  {mkey}: {quote_counts.get(mkey, 0)} quotes -> "
            f"no_baseline={drop_no_baseline.get(mkey, 0)} "
            f"team_mismatch={drop_team_mismatch.get(mkey, 0)} "
            f"no_candidates={drop_no_candidates.get(mkey, 0)} -> "
            f"{final_counts.get(mkey, 0)} final props"
        )

    with open(os.path.join(DATA_DIR, "props.json"), "w") as f:
        json.dump(props, f)

    meta = {
        "generated_at": utcnow_iso(),
        "baseline_season": season_week["baseline_season"],
        "upcoming_season": season_week["upcoming_season"],
        "upcoming_week": season_week["upcoming_week"],
        "odds_source": odds_meta["source"],
        "odds_fetched_at": odds_meta["fetched_at"],
        "prop_count": len(props),
        "markets": {k: v["label"] for k, v in MARKETS.items()},
        "inactive_players_excluded": len(inactive_players),
        "matchups": matchup_options,
        "time_slots": [
            t for t in TIME_SLOT_ORDER if t in {info["time_slot"] for info in game_lookup.values()}
        ],
    }
    with open(os.path.join(DATA_DIR, "meta.json"), "w") as f:
        json.dump(meta, f)

    print(f"Wrote {len(props)} props -> data/props.json")
    print(meta)


if __name__ == "__main__":
    main()
