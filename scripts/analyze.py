"""Core value model: builds a recency-weighted, opponent-adjusted projection
for every player/market we have odds for, converts sportsbook odds to a
no-vig implied probability, and reports the edge between the two.

Output: data/props.json (the list the frontend renders) and data/meta.json
(run metadata: season/week, odds source, generated_at).
"""
import json
import math
import os
import re

import numpy as np
import pandas as pd
from scipy.stats import norm

from common import DATA_DIR, MARKETS, american_to_implied_prob, remove_vig_two_way, utcnow_iso

RECENCY_DECAY = 0.88
MIN_GAMES = 3
DEFENSE_FACTOR_BOUNDS = (0.75, 1.25)
TD_PROB_BOUNDS = (0.02, 0.95)

USAGE_MIN = {
    "player_pass_yds": ("attempts", 5),
    "player_pass_tds": ("attempts", 5),
    "player_rush_yds": ("carries", 2),
    "player_receptions": ("targets", 1),
    "player_reception_yds": ("targets", 1),
    "player_rush_reception_yds": (None, 0),
    "player_anytime_td": (None, 0),
}


def normalize_name(name):
    return re.sub(r"[^a-z]", "", str(name).lower())


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
            recent = rows.head(8)[["season", "week", "opponent_team"] + cfg["stat_cols"]].copy()
            recent["value"] = recent[cfg["stat_cols"]].sum(axis=1)
            recent_games = recent[["season", "week", "opponent_team", "value"]].to_dict("records")

            baselines[(norm_name, mkey)] = {
                "mean": mean,
                "std": floor,
                "games": n,
                "team": group["recent_team"].iloc[0],
                "position": position,
                "display_name": display_name,
                "recent_games": recent_games,
            }
    return baselines, team_by_player


def build_defense_factors(stats_df):
    """{market_key: {team_code: factor}} -- how much a defense inflates or
    suppresses opponents' production in that stat, relative to league average.
    """
    factors = {}
    for mkey, cfg in MARKETS.items():
        if cfg.get("binary"):
            per_game = stats_df.copy()
            per_game["_val"] = (per_game[cfg["stat_cols"]].fillna(0).sum(axis=1) > 0).astype(float)
        else:
            per_game = stats_df.copy()
            per_game["_val"] = per_game[cfg["stat_cols"]].fillna(0).sum(axis=1)

        league_avg = per_game["_val"].mean()
        if not league_avg:
            continue
        by_team = per_game.groupby("opponent_team")["_val"].mean()
        team_factors = (by_team / league_avg).clip(*DEFENSE_FACTOR_BOUNDS).to_dict()
        factors[mkey] = team_factors
    return factors


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

    baselines, team_by_player = build_player_baselines(stats_df)
    defense_factors = build_defense_factors(stats_df)

    props = []
    for q in quotes:
        norm_name = normalize_name(q["player_name"])
        key = (norm_name, q["market"])
        base = baselines.get(key)
        if base is None:
            continue

        player_team = base["team"]
        if player_team == q["home_team"]:
            opponent = q["away_team"]
        elif player_team == q["away_team"]:
            opponent = q["home_team"]
        else:
            # Player's team on file doesn't match either side of this game
            # (likely a stale roster snapshot) -- skip rather than guess.
            continue

        cfg = MARKETS[q["market"]]
        factor = defense_factors.get(q["market"], {}).get(opponent, 1.0)
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
            continue
        recommended_side, recommended_edge = max(candidates, key=lambda x: x[1])

        props.append(
            {
                "player_name": base["display_name"],
                "position": base["position"],
                "team": player_team,
                "opponent": opponent,
                "market": q["market"],
                "market_label": cfg["label"],
                "line": q["point"],
                "book": q["book"],
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
            }
        )

    props.sort(key=lambda p: p["recommended_edge"], reverse=True)

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
    }
    with open(os.path.join(DATA_DIR, "meta.json"), "w") as f:
        json.dump(meta, f)

    print(f"Wrote {len(props)} props -> data/props.json")
    print(meta)


if __name__ == "__main__":
    main()
