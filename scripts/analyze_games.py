"""Game-level value model: full-game and 1st/2nd-half spreads and totals.

Estimates how many points each team would score in a given matchup/segment
from scoring components (rushing TDs, passing TDs, field goals), the same
matchup-factor approach player props uses: a team's own recency-and-season-
weighted scoring rate for a component, adjusted by the opponent's weighted
rate of allowing that component relative to league average. Summed across
components (with a fixed ~6.94 points per TD to account for the PAT, and
3 for a made field goal) gives each team's projected points for that
segment; the two teams' projections give a model total and a model margin,
compared the same way player props compare a model probability to the
sportsbook's no-vig implied probability.

Deliberately capped to at most one season back (the season being projected
for, plus the immediately preceding one) -- team rosters, schemes, and
coaching turn over enough between seasons that reaching back further
would mostly be diluting the signal with a materially different team.
This is why team-game stats get their own fetch (fetch_team_stats.py)
rather than reusing the multi-season player_stats_recent.csv.

Output: data/game_props.json and data/game_meta.json.
"""
import json
import os
from collections import Counter

import pandas as pd
from scipy.stats import norm

from analyze import classify_time_slot
from common import (
    DATA_DIR,
    RECENCY_DECAY,
    SEASON_DECAY,
    american_to_implied_prob,
    game_weights,
    remove_vig_two_way,
    utcnow_iso,
    weighted_mean_std,
)

MIN_GAMES = 3
DEFENSE_FACTOR_BOUNDS = (0.75, 1.25)
STAT_COMPONENTS = ["rushing_tds", "passing_tds", "field_goals"]
SEGMENTS = ["full", "h1", "h2"]
SEGMENT_LABELS = {"full": "Full Game", "h1": "1st Half", "h2": "2nd Half"}

# A touchdown is worth 6 plus the extra point/2-point try -- rather than
# modeling PAT vs. 2-point choice and each one's own success rate
# separately, this folds in the league-wide expected value of "whatever a
# team does after a TD" (PAT make rate is ~94%, 2-point conversions are
# rare and roughly a coin flip, netting out close to +0.94 either way).
TD_POINT_VALUE = 6.94
FG_POINT_VALUE = 3.0

# Fixed, not fit to this dataset: commonly-cited real-world std devs for
# NFL full-game margins and totals. Team scoring components (TD counts, FG
# makes) are low-count and high-variance individually, and don't capture
# everything that moves a final score (turnovers, special-teams TDs, late-
# game strategy) -- rather than understate uncertainty with a variance
# built only from those components, this uses the actual observed spread
# of real NFL outcomes. Half-segments get a smaller std (roughly full-game
# scaled by sqrt(0.5)) since half a game is a shorter, less variable
# sample.
MARGIN_STD = {"full": 13.5, "h1": 9.5, "h2": 9.5}
TOTAL_STD = {"full": 10.5, "h1": 7.5, "h2": 7.5}


def team_weighted_rates(team_stats, current_season):
    """{team: {f"{stat}_{segment}": rate, f"{stat}_{segment}_allowed": rate,
    f"points_cv_{segment}": cv, "games": n}} -- each team's own
    recency/season-weighted scoring rate and what their defense has
    allowed, for every stat/segment combination, plus how consistent
    (game to game) that team's own scoring has actually been.
    """
    team_stats = team_stats.sort_values(["season", "week"], ascending=False)
    rates = {}
    for team, group in team_stats.groupby("team"):
        n = len(group)
        if n < MIN_GAMES:
            continue
        weights = game_weights(group["season"].tolist(), current_season)
        entry = {"games": n}
        for stat in STAT_COMPONENTS:
            for segment in SEGMENTS:
                for col in (f"{stat}_{segment}", f"{stat}_allowed_{segment}"):
                    mean, _, _ = weighted_mean_std(group[col].tolist(), weights)
                    entry[col] = mean
        for segment in SEGMENTS:
            points_per_game = (
                group[f"rushing_tds_{segment}"] * TD_POINT_VALUE
                + group[f"passing_tds_{segment}"] * TD_POINT_VALUE
                + group[f"field_goals_{segment}"] * FG_POINT_VALUE
            )
            mean, std, _ = weighted_mean_std(points_per_game.tolist(), weights)
            entry[f"points_cv_{segment}"] = std / mean if mean else 1.0
        rates[team] = entry
    return rates


def league_averages(team_stats):
    """Simple (unweighted) league-wide mean per stat/segment -- the
    denominator for a defense's allowed-rate factor, same role
    build_defense_factors' league_avg plays for player props."""
    averages = {}
    for stat in STAT_COMPONENTS:
        for segment in SEGMENTS:
            col = f"{stat}_{segment}"
            averages[col] = team_stats[col].mean()
    return averages


def defense_factor(team_rates, league_avg, stat, segment):
    stat_col = f"{stat}_{segment}"
    league_mean = league_avg.get(stat_col)
    if not league_mean:
        return 1.0
    allowed_rate = team_rates.get(f"{stat}_allowed_{segment}")
    if allowed_rate is None:
        return 1.0
    factor = allowed_rate / league_mean
    return min(max(factor, DEFENSE_FACTOR_BOUNDS[0]), DEFENSE_FACTOR_BOUNDS[1])


def projected_points(offense_rates, defense_rates, league_avg, segment):
    total = 0.0
    for stat in STAT_COMPONENTS:
        own_rate = offense_rates.get(f"{stat}_{segment}") or 0.0
        factor = defense_factor(defense_rates, league_avg, stat, segment)
        projected = own_rate * factor
        total += projected * (TD_POINT_VALUE if stat != "field_goals" else FG_POINT_VALUE)
    return total


def confidence_for(home_games, away_games, home_cv, away_cv):
    """Mirrors player props' confidence_label: a big enough sample alone
    isn't enough for High -- the less consistent of the two teams' own
    scoring (by coefficient of variation) also has to be reasonably low,
    or a wildly erratic team would look just as trustworthy as a steady
    one purely because a full prior season pads its game count.
    """
    n = min(home_games, away_games)
    cv = max(home_cv, away_cv)
    if n >= 8 and cv < 0.6:
        return "High"
    if n >= 5:
        return "Medium"
    return "Low"


def build_matchup_props(slate, team_rates, league_avg, quotes_by_key):
    props = []
    for g in slate.itertuples():
        home, away = g.home_team, g.away_team
        home_rates = team_rates.get(home)
        away_rates = team_rates.get(away)
        if home_rates is None or away_rates is None:
            continue
        matchup = f"{away} @ {home}"

        for segment in SEGMENTS:
            home_points = projected_points(home_rates, away_rates, league_avg, segment)
            away_points = projected_points(away_rates, home_rates, league_avg, segment)
            model_total = home_points + away_points
            model_margin_home = home_points - away_points
            confidence = confidence_for(
                home_rates["games"],
                away_rates["games"],
                home_rates[f"points_cv_{segment}"],
                away_rates[f"points_cv_{segment}"],
            )

            for market in ("spread", "total"):
                quote = quotes_by_key.get((home, away, segment, market))
                if quote is None:
                    continue

                if market == "spread":
                    line = quote["home_point"]
                    prob_a = 1 - norm.cdf(-line, loc=model_margin_home, scale=MARGIN_STD[segment])
                    prob_b = 1 - prob_a
                    price_a, price_b = quote["home_price"], quote["away_price"]
                    book_a, book_b = quote["home_book"], quote["away_book"]
                    side_a_label = f"{home} {line:+g}"
                    side_b_label = f"{away} {-line:+g}" if line is not None else f"{away}"
                else:
                    line = quote["point"]
                    prob_a = 1 - norm.cdf(line, loc=model_total, scale=TOTAL_STD[segment])
                    prob_b = 1 - prob_a
                    price_a, price_b = quote["over_price"], quote["under_price"]
                    book_a, book_b = quote["over_book"], quote["under_book"]
                    side_a_label = f"Over {line}"
                    side_b_label = f"Under {line}"

                raw_a = american_to_implied_prob(price_a)
                raw_b = american_to_implied_prob(price_b)
                if raw_a is not None and raw_b is not None:
                    novig_a, novig_b = remove_vig_two_way(raw_a, raw_b)
                else:
                    novig_a, novig_b = raw_a, raw_b

                edge_a = (prob_a - novig_a) if novig_a is not None else None
                edge_b = (prob_b - novig_b) if novig_b is not None else None
                candidates = [(s, e) for s, e in (("a", edge_a), ("b", edge_b)) if e is not None]
                if not candidates:
                    continue
                recommended_side, recommended_edge = max(candidates, key=lambda x: x[1])

                props.append(
                    {
                        "matchup": matchup,
                        "home_team": home,
                        "away_team": away,
                        "game_date": g.game_date,
                        "time_slot": g.time_slot,
                        "segment": segment,
                        "segment_label": SEGMENT_LABELS[segment],
                        "market": market,
                        "market_label": "Spread" if market == "spread" else "Total",
                        "line": line,
                        "side_a_label": side_a_label,
                        "side_b_label": side_b_label,
                        "price_a": price_a,
                        "price_b": price_b,
                        "book_a": book_a,
                        "book_b": book_b,
                        "model_prob_a": round(prob_a, 4),
                        "model_prob_b": round(prob_b, 4),
                        "implied_prob_a": round(novig_a, 4) if novig_a is not None else None,
                        "implied_prob_b": round(novig_b, 4) if novig_b is not None else None,
                        "edge_a": round(edge_a, 4) if edge_a is not None else None,
                        "edge_b": round(edge_b, 4) if edge_b is not None else None,
                        "recommended_side": recommended_side,
                        "recommended_edge": round(recommended_edge, 4),
                        "model_home_points": round(home_points, 1),
                        "model_away_points": round(away_points, 1),
                        "model_total": round(model_total, 1),
                        "model_margin_home": round(model_margin_home, 1),
                        "sample_games_home": home_rates["games"],
                        "sample_games_away": away_rates["games"],
                        "confidence": confidence,
                    }
                )
    return props


def main():
    with open(os.path.join(DATA_DIR, "season_week.json")) as f:
        season_week = json.load(f)
    team_stats_path = os.path.join(DATA_DIR, "team_game_stats.csv")
    quotes_path = os.path.join(DATA_DIR, "game_odds_quotes.json")
    odds_meta_path = os.path.join(DATA_DIR, "game_odds_meta.json")

    upcoming_season, upcoming_week = season_week["upcoming_season"], season_week["upcoming_week"]
    team_stats = pd.read_csv(team_stats_path, low_memory=False) if os.path.exists(team_stats_path) else pd.DataFrame()
    quotes = []
    if os.path.exists(quotes_path):
        with open(quotes_path) as f:
            quotes = json.load(f)
    odds_meta = {}
    if os.path.exists(odds_meta_path):
        with open(odds_meta_path) as f:
            odds_meta = json.load(f)

    props = []
    if upcoming_season is not None and not team_stats.empty:
        games = pd.read_csv(os.path.join(DATA_DIR, "games_recent.csv"), low_memory=False)
        slate = games[
            (games["season"] == upcoming_season) & (games["week"] == upcoming_week)
        ].copy()
        slate["game_date"] = slate["gameday"]
        slate["time_slot"] = [classify_time_slot(r.weekday, r.gametime) for r in slate.itertuples()]

        current_season = upcoming_season
        team_rates = team_weighted_rates(team_stats, current_season)
        league_avg = league_averages(team_stats)
        quotes_by_key = {
            (q["home_team"], q["away_team"], q["segment"], q["market"]): q for q in quotes
        }
        props = build_matchup_props(slate, team_rates, league_avg, quotes_by_key)

    with open(os.path.join(DATA_DIR, "game_props.json"), "w") as f:
        json.dump(props, f)

    meta = {
        "generated_at": utcnow_iso(),
        "upcoming_season": upcoming_season,
        "upcoming_week": upcoming_week,
        "odds_source": odds_meta.get("source", "none"),
        "odds_fetched_at": odds_meta.get("fetched_at"),
        "prop_count": len(props),
        "segments": SEGMENT_LABELS,
    }
    with open(os.path.join(DATA_DIR, "game_meta.json"), "w") as f:
        json.dump(meta, f)

    by_segment = Counter(p["segment"] for p in props)
    print(f"Wrote {len(props)} game props -> data/game_props.json ({dict(by_segment)})")


if __name__ == "__main__":
    main()
