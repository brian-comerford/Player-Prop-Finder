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

from analyze import HISTORY_DIR, classify_time_slot
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


CONFIDENCE_HIGH_PERCENTILE = 0.75
CONFIDENCE_LOW_PERCENTILE = 0.25
MIN_SCORES_FOR_TIERS = 4


def reliability_score(home_games, away_games, home_cv, away_cv):
    """A single higher-is-better number: rewards a longer combined
    (current + prior season) track record and penalizes the less
    consistent of the two teams' own scoring (by coefficient of
    variation) in this segment -- a wildly erratic team shouldn't look
    just as trustworthy as a steady one purely because a full prior
    season pads its game count.
    """
    games = min(home_games, away_games)
    cv = max(home_cv, away_cv)
    return games / (1.0 + cv)


def confidence_cutoffs(scores):
    """Fixed absolute thresholds meant nearly every bet cleared the bar
    for High once a full prior season was folded into the sample --
    "High" stopped meaning anything selective. Confidence is relative
    instead: High is reserved for the top quartile of this week's own
    suggested bets by reliability_score, Low is the bottom quartile, and
    everything else is Medium. Too few bets on the slate to make a
    quartile split meaningful (e.g. a short week) falls back to treating
    everything as Medium rather than an unstable, near-arbitrary split.
    """
    if len(scores) < MIN_SCORES_FOR_TIERS:
        return None, None
    series = pd.Series(scores, dtype=float)
    return series.quantile(CONFIDENCE_HIGH_PERCENTILE), series.quantile(CONFIDENCE_LOW_PERCENTILE)


def confidence_label(score, high_cutoff, low_cutoff):
    if high_cutoff is None:
        return "Medium"
    if score >= high_cutoff:
        return "High"
    if score <= low_cutoff:
        return "Low"
    return "Medium"


def build_matchup_props(slate, team_rates, league_avg, quotes_by_key):
    # First pass: for every matchup/segment we'll actually offer a bet on
    # (at least one of spread/total quoted), compute its projection and
    # reliability score. Confidence tiers are assigned afterward, relative
    # to this week's own set of suggested bets -- see confidence_cutoffs.
    segment_entries = []
    for g in slate.itertuples():
        home, away = g.home_team, g.away_team
        home_rates = team_rates.get(home)
        away_rates = team_rates.get(away)
        if home_rates is None or away_rates is None:
            continue

        for segment in SEGMENTS:
            has_quote = any(
                quotes_by_key.get((home, away, segment, market)) is not None
                for market in ("spread", "total")
            )
            if not has_quote:
                continue
            home_points = projected_points(home_rates, away_rates, league_avg, segment)
            away_points = projected_points(away_rates, home_rates, league_avg, segment)
            score = reliability_score(
                home_rates["games"],
                away_rates["games"],
                home_rates[f"points_cv_{segment}"],
                away_rates[f"points_cv_{segment}"],
            )
            segment_entries.append(
                {
                    "game": g,
                    "home": home,
                    "away": away,
                    "segment": segment,
                    "home_points": home_points,
                    "away_points": away_points,
                    "score": score,
                    "games_home": home_rates["games"],
                    "games_away": away_rates["games"],
                }
            )

    high_cutoff, low_cutoff = confidence_cutoffs([e["score"] for e in segment_entries])

    props = []
    for entry in segment_entries:
        g = entry["game"]
        home, away, segment = entry["home"], entry["away"], entry["segment"]
        home_points, away_points = entry["home_points"], entry["away_points"]
        matchup = f"{away} @ {home}"
        model_total = home_points + away_points
        model_margin_home = home_points - away_points
        confidence = confidence_label(entry["score"], high_cutoff, low_cutoff)

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
                    "sample_games_home": entry["games_home"],
                    "sample_games_away": entry["games_away"],
                    "confidence": confidence,
                }
            )
    return props


def snapshot_current_week_game_picks(props, season, week):
    """Writes data/history/game_picks_{season}_wk{week}.json -- the game-
    level (spread/total) analog of analyze.py's snapshot_current_week_picks,
    same merge behavior: a matchup with no props in this run (its game has
    already kicked off) keeps whatever was last snapshotted for it, and
    only matchups still on the board get refreshed.
    """
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = os.path.join(HISTORY_DIR, f"game_picks_{season}_wk{week}.json")

    fresh_matchups = {(p["home_team"], p["away_team"]) for p in props}
    carried_over = []
    if os.path.exists(path):
        with open(path) as f:
            previous = json.load(f)
        carried_over = [
            pick
            for pick in previous.get("picks", [])
            if (pick["home_team"], pick["away_team"]) not in fresh_matchups
        ]

    fresh_picks = [
        {
            "matchup": p["matchup"],
            "home_team": p["home_team"],
            "away_team": p["away_team"],
            "segment": p["segment"],
            "segment_label": p["segment_label"],
            "market": p["market"],
            "market_label": p["market_label"],
            "line": p["line"],
            "side": p["recommended_side"],
            "side_label": p["side_a_label"] if p["recommended_side"] == "a" else p["side_b_label"],
            "model_prob": p["model_prob_a"] if p["recommended_side"] == "a" else p["model_prob_b"],
            "edge": p["recommended_edge"],
            "confidence": p["confidence"],
        }
        for p in props
    ]
    picks = carried_over + fresh_picks
    with open(path, "w") as f:
        json.dump({"season": season, "week": week, "generated_at": utcnow_iso(), "picks": picks}, f)


def completed_matchups(games_df, season, week):
    """{(home_team, away_team): (home_score, away_score)} for every game in
    (season, week) that already has a final score."""
    if games_df.empty:
        return {}
    rows = games_df[
        (games_df["season"] == season)
        & (games_df["week"] == week)
        & games_df["home_score"].notna()
        & (games_df["home_score"] != "")
    ]
    return {(g.home_team, g.away_team): (float(g.home_score), float(g.away_score)) for g in rows.itertuples()}


def actual_segment_points(team_stats_df, season, week, team, segment):
    """Approximates a team's actual points scored in `segment` for an
    already-played game, from real per-half scoring-play counts
    (team_game_stats.csv) using the same TD_POINT_VALUE/FG_POINT_VALUE the
    model's own projections use. Only needed for h1/h2 -- nflverse's
    schedule file has no actual half-by-half score to grade a half-game
    bet against, unlike "full", which uses the real final score from
    games_recent.csv instead (see grade_past_game_weeks). This is
    therefore an approximation (it won't count a safety or a 2-point
    return, for instance), but it's the same approximation the model
    itself is judged by, so it stays an apples-to-apples comparison.
    """
    rows = team_stats_df[
        (team_stats_df["season"] == season) & (team_stats_df["week"] == week) & (team_stats_df["team"] == team)
    ]
    if rows.empty:
        return None
    row = rows.iloc[0]
    return float(
        row[f"rushing_tds_{segment}"] * TD_POINT_VALUE
        + row[f"passing_tds_{segment}"] * TD_POINT_VALUE
        + row[f"field_goals_{segment}"] * FG_POINT_VALUE
    )


def graded_game_pick(pick, actual_home, actual_away):
    """(hit, margin) for one snapshotted pick given the actual points each
    side scored in its segment -- margin is signed so it's positive
    whenever the pick hit (by how much) and negative when it missed (by
    how much), mirroring analyze.py's player-prop margin convention.
    Returns (None, None) if the pick has no line to grade against.
    """
    line = pick["line"]
    if line is None:
        return None, None
    if pick["market"] == "spread":
        raw = (actual_home - actual_away) + line  # positive => home covered by this many points
    else:
        raw = (actual_home + actual_away) - line  # positive => total went Over by this many points
    margin = raw if pick["side"] == "a" else -raw
    return margin > 0, round(margin, 1)


def grade_past_game_weeks(games_df, team_stats_df, current_season, current_week):
    """Grades every snapshotted game pick whose own matchup has already
    finished -- the game-level analog of analyze.py's grade_past_weeks.
    Recomputed from scratch each run for any week not yet fully graded, so
    newly finished games (and newly available team-game-stats rows) are
    picked up without needing to merge with a prior partial result.
    """
    if current_week is None or not os.path.isdir(HISTORY_DIR):
        return
    for fname in sorted(os.listdir(HISTORY_DIR)):
        if not fname.startswith("game_picks_") or not fname.endswith(".json"):
            continue
        with open(os.path.join(HISTORY_DIR, fname)) as f:
            snapshot = json.load(f)
        season, week = snapshot["season"], snapshot["week"]
        if (season, week) > (current_season, current_week):
            continue

        results_path = os.path.join(HISTORY_DIR, fname.replace("game_picks_", "game_results_", 1))
        if os.path.exists(results_path):
            with open(results_path) as f:
                if json.load(f).get("fully_graded"):
                    continue

        finished = completed_matchups(games_df, season, week)
        graded = []
        pending = 0
        for pick in snapshot["picks"]:
            key = (pick["home_team"], pick["away_team"])
            if key not in finished:
                pending += 1
                continue
            actual_home, actual_away = finished[key]
            if pick["segment"] != "full":
                seg_home = actual_segment_points(team_stats_df, season, week, pick["home_team"], pick["segment"])
                seg_away = actual_segment_points(team_stats_df, season, week, pick["away_team"], pick["segment"])
                if seg_home is None or seg_away is None:
                    continue
                actual_home, actual_away = seg_home, seg_away

            hit, margin = graded_game_pick(pick, actual_home, actual_away)
            if hit is None:
                continue
            graded.append(
                {
                    **pick,
                    "actual_home_points": round(actual_home, 1),
                    "actual_away_points": round(actual_away, 1),
                    "hit": hit,
                    "margin": margin,
                }
            )

        fully_graded = pending == 0
        with open(results_path, "w") as f:
            json.dump(
                {
                    "season": season,
                    "week": week,
                    "graded_at": utcnow_iso(),
                    "fully_graded": fully_graded,
                    "picks": graded,
                },
                f,
            )
        status = "fully graded" if fully_graded else f"{pending} picks still pending (games not final yet)"
        print(f"  Graded game props {season} wk{week}: {len(graded)}/{len(snapshot['picks'])} picks ({status})")


def build_game_track_record():
    """Games analog of analyze.py's build_track_record -- rolled up from
    data/history/game_results_*.json instead of results_*.json."""
    def summarize(picks):
        if not picks:
            return None
        hits = sum(1 for p in picks if p["hit"])
        return {"picks": len(picks), "hits": hits, "hit_rate": round(hits / len(picks), 3)}

    all_picks = []
    weeks_graded = 0
    week_in_progress = False
    if os.path.isdir(HISTORY_DIR):
        for fname in sorted(os.listdir(HISTORY_DIR)):
            if not fname.startswith("game_results_") or not fname.endswith(".json"):
                continue
            with open(os.path.join(HISTORY_DIR, fname)) as f:
                data = json.load(f)
            all_picks.extend(data["picks"])
            if data.get("fully_graded"):
                weeks_graded += 1
            elif data["picks"]:
                week_in_progress = True

    by_confidence = {}
    for tier in ("High", "Medium", "Low"):
        summary = summarize([p for p in all_picks if p["confidence"] == tier])
        if summary:
            by_confidence[tier] = summary

    return {
        "overall": summarize(all_picks),
        "by_confidence": by_confidence,
        "weeks_graded": weeks_graded,
        "week_in_progress": week_in_progress,
        "updated_at": utcnow_iso(),
    }


def build_game_track_record_detail():
    """Games analog of analyze.py's build_track_record_detail."""
    picks = []
    if os.path.isdir(HISTORY_DIR):
        for fname in sorted(os.listdir(HISTORY_DIR)):
            if not fname.startswith("game_results_") or not fname.endswith(".json"):
                continue
            with open(os.path.join(HISTORY_DIR, fname)) as f:
                data = json.load(f)
            for p in data["picks"]:
                picks.append(
                    {
                        "season": data["season"],
                        "week": data["week"],
                        "matchup": p["matchup"],
                        "segment_label": p["segment_label"],
                        "market_label": p["market_label"],
                        "side_label": p["side_label"],
                        "line": p["line"],
                        "confidence": p["confidence"],
                        "edge": p["edge"],
                        "actual_home_points": p["actual_home_points"],
                        "actual_away_points": p["actual_away_points"],
                        "hit": p["hit"],
                        "margin": p["margin"],
                    }
                )
    picks.sort(key=lambda p: (p["season"], p["week"]), reverse=True)
    return {"updated_at": utcnow_iso(), "picks": picks}


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

    games_path = os.path.join(DATA_DIR, "games_recent.csv")
    games = pd.read_csv(games_path, low_memory=False) if os.path.exists(games_path) else pd.DataFrame()

    props = []
    if upcoming_season is not None and not team_stats.empty and not games.empty:
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

    books = sorted({p[side] for p in props for side in ("book_a", "book_b") if p[side]})
    meta = {
        "generated_at": utcnow_iso(),
        "upcoming_season": upcoming_season,
        "upcoming_week": upcoming_week,
        "odds_source": odds_meta.get("source", "none"),
        "odds_fetched_at": odds_meta.get("fetched_at"),
        "prop_count": len(props),
        "segments": SEGMENT_LABELS,
        "books": books,
    }
    with open(os.path.join(DATA_DIR, "game_meta.json"), "w") as f:
        json.dump(meta, f)

    by_segment = Counter(p["segment"] for p in props)
    print(f"Wrote {len(props)} game props -> data/game_props.json ({dict(by_segment)})")

    if upcoming_season is not None and upcoming_week is not None:
        snapshot_current_week_game_picks(props, upcoming_season, upcoming_week)
        print(f"Snapshotted {len(props)} game picks for {upcoming_season} wk{upcoming_week} -> data/history/")
    grade_past_game_weeks(games, team_stats, upcoming_season, upcoming_week)

    game_track_record = build_game_track_record()
    with open(os.path.join(DATA_DIR, "game_track_record.json"), "w") as f:
        json.dump(game_track_record, f)
    print(
        f"Wrote game track record ({game_track_record['weeks_graded']} weeks graded) "
        "-> data/game_track_record.json"
    )

    game_track_record_detail = build_game_track_record_detail()
    with open(os.path.join(DATA_DIR, "game_track_record_detail.json"), "w") as f:
        json.dump(game_track_record_detail, f)
    print(
        f"Wrote game track record detail ({len(game_track_record_detail['picks'])} graded picks) "
        "-> data/game_track_record_detail.json"
    )


if __name__ == "__main__":
    main()
