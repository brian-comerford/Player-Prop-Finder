"""Core value model: builds a recency-weighted, opponent-adjusted projection
for every player/market we have odds for, converts sportsbook odds to a
no-vig implied probability, and reports the edge between the two.

Output: data/props.json (the list the frontend renders) and data/meta.json
(run metadata: season/week, odds source, generated_at).
"""
import json
import os
import statistics
from collections import Counter

import pandas as pd
from scipy.stats import norm

from common import (
    DATA_DIR,
    MARKETS,
    RECENCY_DECAY,
    SEASON_DECAY,
    american_to_implied_prob,
    game_weights,
    normalize_name,
    remove_vig_two_way,
    utcnow_iso,
    weighted_mean_std,
)

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


def build_player_baselines(stats_df, current_season):
    """Returns {(norm_name, market_key): {mean, std, games, team, recent_games}}."""
    stats_df = stats_df.sort_values(["season", "week"], ascending=False)
    baselines = {}
    team_by_player = {}

    for player_id, group in stats_df.groupby("player_id"):
        display_name = group["player_display_name"].iloc[0]
        position = group["position"].iloc[0]
        norm_name = normalize_name(display_name)
        team_by_player[norm_name] = group["recent_team"].iloc[0]
        weights = game_weights(group["season"].tolist(), current_season)

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

            mean, std, n = weighted_mean_std(per_game, weights)
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


def weighted_defense_factors(rows, current_season, league_avg):
    """Each opponent's recency/season-weighted allowed rate for `rows`'
    stat, relative to `league_avg` -- same game_weights a player's own
    baseline uses, applied here so a defense's current-season games count
    significantly more than last season's at the same recency. A defense's
    personnel and scheme turn over between seasons just like an offense's
    can, so there's no reason to weight "how good is this defense" any
    differently than "how good is this player." Bounded the same as every
    other matchup factor in this file.

    Unlike a player's own game log (one row per week), each week here has
    one row per opposing skill player who touched the ball against this
    defense -- game_weights' games-back index has to be computed off the
    defense's distinct (season, week) games, not off row position, or
    everything from the single most recent game (its ~10 rows) would eat
    nearly the whole decay curve meant for "10 games back."
    """
    factors = {}
    for team, group in rows.groupby("opponent_team"):
        game_keys = (
            group[["season", "week"]].drop_duplicates().sort_values(["season", "week"], ascending=False)
        )
        game_weight_by_key = dict(
            zip(
                map(tuple, game_keys.itertuples(index=False, name=None)),
                game_weights(game_keys["season"].tolist(), current_season),
            )
        )
        row_weights = [
            game_weight_by_key[(season, week)]
            for season, week in zip(group["season"], group["week"])
        ]
        mean, _, _ = weighted_mean_std(group["_val"].tolist(), row_weights)
        factors[team] = min(max(mean / league_avg, DEFENSE_FACTOR_BOUNDS[0]), DEFENSE_FACTOR_BOUNDS[1])
    return factors


def build_defense_factors(stats_df, current_season):
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
    stats_df = stats_df.sort_values(["season", "week"], ascending=False)
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

        overall_factors = weighted_defense_factors(per_game, current_season, league_avg)

        by_position = {}
        for position in cfg["position_group"]:
            pos_rows = per_game[per_game["position"] == position]
            pos_league_avg = pos_rows["_val"].mean()
            if not pos_league_avg:
                continue
            row_counts = pos_rows.groupby("opponent_team")["_val"].count()
            pos_factors = weighted_defense_factors(pos_rows, current_season, pos_league_avg)
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


def split_defense_tiers(defense_factors, market, position):
    """Split this market/position's opponent defenses into two tiers by
    their factor relative to the league median: bottom-half (factor at or
    above the median -- they allow more of this stat than a typical
    defense, an easier matchup for the Over) and top-half (factor below
    the median -- a tougher matchup, relevant for the Under).
    """
    market_factors = defense_factors.get(market, {})
    factors = market_factors.get("by_position", {}).get(position) or market_factors.get("overall", {})
    if not factors:
        return set(), set()
    median = statistics.median(factors.values())
    bottom_half = {team for team, factor in factors.items() if factor >= median}
    top_half = {team for team, factor in factors.items() if factor < median}
    return bottom_half, top_half


def side_hits(binary, side, line, value):
    """Whether a real per-game stat `value` would have hit the given side
    of a line -- shared between the trend-insight hit rate below and the
    historical pick-grading further down.
    """
    if binary:
        return value > 0 if side == "over" else value <= 0
    return value > line if side == "over" else value < line


def build_trend_insights(game_log, cfg, line, side, bottom_half_set, top_half_set):
    """Notable, plain-English hit-rate patterns for the recommended side,
    e.g. "Over 3.5 receptions in 4 of last 5 games" or the same measured
    only against bottom-half defenses for an Over (top-half defenses for
    an Under, since a tough defense is what makes an Under likely to
    hit). Returns [] when nothing clears the bar -- most players won't
    have a notable trend, and that's fine.
    """
    if not game_log:
        return []

    binary = cfg.get("binary", False)

    def is_hit(value):
        return side_hits(binary, side, line, value)

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

    matchup_set = bottom_half_set if side == "over" else top_half_set
    tier_label = "bottom-half" if side == "over" else "top-half"
    matchup_games = [g for g in game_log if g["opponent_team"] in matchup_set]
    if matchup_games != window:
        m = len(matchup_games)
        m_hits = sum(1 for g in matchup_games if is_hit(g["value"]))
        if m >= MATCHUP_TREND_MIN_GAMES and m_hits / m >= MATCHUP_TREND_MIN_HIT_RATE:
            insights.append(f"{verb} in {m_hits} of {m} games vs. {tier_label} defenses")

    return insights


HISTORY_DIR = os.path.join(DATA_DIR, "history")


def snapshot_current_week_picks(props, season, week):
    """Writes data/history/picks_{season}_wk{week}.json: a compact record of
    every current recommendation (side, line, model probability, edge,
    confidence), so it can be graded against what actually happened once
    the games are played. Overwritten on every run up until kickoff, since
    the model's own inputs (odds, injuries, usage) can still change during
    the week -- the last snapshot before the games start is the one that
    actually gets graded.
    """
    os.makedirs(HISTORY_DIR, exist_ok=True)
    picks = [
        {
            "player_id": p["player_id"],
            "player_name": p["player_name"],
            "position": p["position"],
            "team": p["team"],
            "opponent": p["opponent"],
            "market": p["market"],
            "line": p["line"],
            "side": p["recommended_side"],
            "model_prob": p["model_prob_over"] if p["recommended_side"] == "over" else p["model_prob_under"],
            "edge": p["recommended_edge"],
            "confidence": p["confidence"],
        }
        for p in props
    ]
    path = os.path.join(HISTORY_DIR, f"picks_{season}_wk{week}.json")
    with open(path, "w") as f:
        json.dump({"season": season, "week": week, "generated_at": utcnow_iso(), "picks": picks}, f)


def actual_value_for(stats_df, player_id, season, week, market):
    """The real per-game value for this player/market in a past week
    (summed from the same stat columns the projection itself is built
    from), or None if they have no row for that week at all -- didn't
    play (bye, injury, inactive), so there's nothing to grade a pick
    against.
    """
    rows = stats_df[
        (stats_df["player_id"] == player_id) & (stats_df["season"] == season) & (stats_df["week"] == week)
    ]
    if rows.empty:
        return None
    cfg = MARKETS[market]
    total = rows[cfg["stat_cols"]].fillna(0).sum(axis=1).iloc[0]
    if cfg.get("binary"):
        return float(total > 0)
    return float(total)


def grade_past_weeks(stats_df, current_season, current_week):
    """Grades every snapshotted week that's already been played --
    (season, week) strictly before the week currently being projected for
    -- and hasn't been graded yet (no matching results file). Idempotent:
    safe to call on every run, since a week already graded is skipped.
    """
    if current_week is None or not os.path.isdir(HISTORY_DIR):
        return
    for fname in sorted(os.listdir(HISTORY_DIR)):
        if not fname.startswith("picks_") or not fname.endswith(".json"):
            continue
        results_path = os.path.join(HISTORY_DIR, fname.replace("picks_", "results_", 1))
        if os.path.exists(results_path):
            continue
        with open(os.path.join(HISTORY_DIR, fname)) as f:
            snapshot = json.load(f)
        season, week = snapshot["season"], snapshot["week"]
        if (season, week) >= (current_season, current_week):
            continue  # not played yet

        graded = []
        for pick in snapshot["picks"]:
            actual = actual_value_for(stats_df, pick["player_id"], season, week, pick["market"])
            if actual is None:
                continue
            binary = MARKETS[pick["market"]].get("binary", False)
            hit = side_hits(binary, pick["side"], pick["line"], actual)
            graded.append({**pick, "actual_value": round(actual, 1), "hit": hit})

        with open(results_path, "w") as f:
            json.dump({"season": season, "week": week, "graded_at": utcnow_iso(), "picks": graded}, f)
        print(f"  Graded {season} wk{week}: {len(graded)}/{len(snapshot['picks'])} picks (rest didn't play)")


def build_track_record():
    """Rolls up every graded week into overall + per-confidence-tier hit
    rates. Fully derived from data/history/results_*.json, so unlike that
    directory this doesn't need to be committed anywhere -- it's rebuilt
    fresh from the committed source of truth on every run.
    """
    def summarize(picks):
        if not picks:
            return None
        hits = sum(1 for p in picks if p["hit"])
        return {"picks": len(picks), "hits": hits, "hit_rate": round(hits / len(picks), 3)}

    all_picks = []
    weeks_graded = 0
    if os.path.isdir(HISTORY_DIR):
        for fname in sorted(os.listdir(HISTORY_DIR)):
            if not fname.startswith("results_") or not fname.endswith(".json"):
                continue
            with open(os.path.join(HISTORY_DIR, fname)) as f:
                data = json.load(f)
            all_picks.extend(data["picks"])
            weeks_graded += 1

    by_confidence = {}
    for tier in ("High", "Medium", "Low"):
        summary = summarize([p for p in all_picks if p["confidence"] == tier])
        if summary:
            by_confidence[tier] = summary

    return {
        "overall": summarize(all_picks),
        "by_confidence": by_confidence,
        "weeks_graded": weeks_graded,
        "updated_at": utcnow_iso(),
    }


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


CONFIDENCE_TIERS = ["Low", "Medium", "High"]


def espn_projected_value(market, espn_stats):
    """Our own market keys don't line up 1:1 with ESPN's stat categories
    (rush+rec yards and anytime TD are both combinations), so this maps
    each market to the ESPN stat(s) that estimate the same thing. Returns
    None when ESPN has no relevant projection for this player at all,
    rather than treating a genuinely missing stat as zero.
    """
    if espn_stats is None:
        return None
    if market == "player_rush_reception_yds":
        if "rush_yd" not in espn_stats and "rec_yd" not in espn_stats:
            return None
        return espn_stats.get("rush_yd", 0) + espn_stats.get("rec_yd", 0)
    if market == "player_anytime_td":
        if "rush_td" not in espn_stats and "rec_td" not in espn_stats:
            return None
        return espn_stats.get("rush_td", 0) + espn_stats.get("rec_td", 0)
    return espn_stats.get(
        {
            "player_pass_yds": "pass_yd",
            "player_pass_tds": "pass_td",
            "player_rush_yds": "rush_yd",
            "player_receptions": "rec",
            "player_reception_yds": "rec_yd",
        }.get(market)
    )


def espn_agreement_level(our_value, espn_value):
    """How closely ESPN's independent projection matches our own, as a
    relative spread between the two -- same bucketing (<=15% strong,
    <=35% moderate, else split) as a working reference implementation
    that blends multiple fantasy projection sources this same way.
    """
    if our_value is None or espn_value is None:
        return None
    avg = (our_value + espn_value) / 2
    if avg <= 0:
        return None
    rel_spread = abs(our_value - espn_value) / avg
    if rel_spread <= 0.15:
        return "strong"
    if rel_spread <= 0.35:
        return "moderate"
    return "split"


def adjust_confidence(label, agreement):
    """A second, independent projection system agreeing closely is
    evidence the model's estimate isn't a fluke; one that's way off is
    reason for more caution -- shifts the confidence tier by at most one
    step either way, never overriding it outright.
    """
    if agreement not in ("strong", "split"):
        return label
    idx = CONFIDENCE_TIERS.index(label)
    idx = idx + 1 if agreement == "strong" else idx - 1
    return CONFIDENCE_TIERS[max(0, min(idx, len(CONFIDENCE_TIERS) - 1))]


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
    injury_report_path = os.path.join(DATA_DIR, "injury_report.json")
    injury_report = {}
    if os.path.exists(injury_report_path):
        with open(injury_report_path) as f:
            injury_report = json.load(f)
    espn_projections_path = os.path.join(DATA_DIR, "espn_projections.json")
    espn_projections = {}
    if os.path.exists(espn_projections_path):
        with open(espn_projections_path) as f:
            espn_projections = json.load(f)

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

    # The season being projected for, not the (possibly stale, see
    # baseline_season above) season nflverse's player_stats release has
    # fully caught up to -- that's the season current-season weighting
    # should actually mean. Falls back to the newest season on file for
    # the rare offseason case where there's no upcoming week at all.
    current_season = season_week["upcoming_season"] or int(stats_df["season"].max())
    baselines, team_by_player = build_player_baselines(stats_df, current_season)
    defense_factors = build_defense_factors(stats_df, current_season)
    defense_tier_cache = {}

    inactive_players = set()
    ruled_out_players = set()
    if season_week["upcoming_season"] is not None:
        active_baselines = {}
        for key, base in baselines.items():
            injury = injury_report.get(base["player_id"])
            if injury and injury["status"] in ("Out", "Doubtful"):
                ruled_out_players.add(base["display_name"])
                inactive_players.add(base["display_name"])
                continue

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
            f"Excluded {len(inactive_players)} players total: "
            f"{len(ruled_out_players)} ruled Out/Doubtful this week, "
            f"{len(inactive_players) - len(ruled_out_players)} with no confirmed snap in the last "
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

        tier_key = (q["market"], base["position"])
        if tier_key not in defense_tier_cache:
            defense_tier_cache[tier_key] = split_defense_tiers(defense_factors, q["market"], base["position"])
        bottom_half_set, top_half_set = defense_tier_cache[tier_key]
        trends = build_trend_insights(
            base["game_log"], cfg, q["point"], recommended_side, bottom_half_set, top_half_set
        )

        injury = injury_report.get(base["player_id"])
        injury_status = None
        if injury and injury["status"] == "Questionable":
            injury_status = f"Questionable ({injury['injury']})" if injury.get("injury") else "Questionable"

        espn_value = espn_projected_value(q["market"], espn_projections.get(base["player_id"]))
        agreement = espn_agreement_level(projected_mean, espn_value)
        confidence = adjust_confidence(
            confidence_label(base["games"], base["mean"], base["std"]), agreement
        )

        props.append(
            {
                "player_id": base["player_id"],
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
                "confidence": confidence,
                "recent_games": base["recent_games"],
                "trends": trends,
                "injury_status": injury_status,
                "espn_projected_value": round(espn_value, 1) if espn_value is not None else None,
                "espn_agreement": agreement,
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

    agreement_counts = Counter(p["espn_agreement"] for p in props if p["espn_agreement"])
    print(
        f"ESPN second-opinion agreement: {len(espn_projections):,} players with ESPN projections, "
        f"{sum(agreement_counts.values())} props compared -- "
        f"strong={agreement_counts.get('strong', 0)} "
        f"moderate={agreement_counts.get('moderate', 0)} "
        f"split={agreement_counts.get('split', 0)}"
    )

    anytime_td_props = sorted(
        (p for p in props if p["market"] == "player_anytime_td" and p["price_over"] is not None),
        key=lambda p: p["price_over"],
    )
    if anytime_td_props:
        print("Shortest anytime_td prices (most likely to score):")
        for p in anytime_td_props[:10]:
            print(
                f"  {p['player_name']} ({p['position']}, {p['team']} vs {p['opponent']}): "
                f"{p['price_over']} via {p['book_over']}, sample_games={p['sample_games']}, "
                f"projected={p['projected_value']}"
            )
        print("Longest anytime_td prices (least likely to score):")
        for p in anytime_td_props[-10:]:
            print(
                f"  {p['player_name']} ({p['position']}, {p['team']} vs {p['opponent']}): "
                f"{p['price_over']} via {p['book_over']}, sample_games={p['sample_games']}, "
                f"projected={p['projected_value']}"
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

    if season_week["upcoming_season"] is not None and season_week["upcoming_week"] is not None:
        snapshot_current_week_picks(props, season_week["upcoming_season"], season_week["upcoming_week"])
        print(
            f"Snapshotted {len(props)} picks for {season_week['upcoming_season']} "
            f"wk{season_week['upcoming_week']} -> data/history/"
        )
    grade_past_weeks(stats_df, current_season, season_week["upcoming_week"])

    track_record = build_track_record()
    with open(os.path.join(DATA_DIR, "track_record.json"), "w") as f:
        json.dump(track_record, f)
    print(f"Wrote track record ({track_record['weeks_graded']} weeks graded) -> data/track_record.json")


if __name__ == "__main__":
    main()
