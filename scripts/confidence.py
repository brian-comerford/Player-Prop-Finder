"""Pick confidence for player props: how likely a recommended pick is to
beat the market's own expectation, from signals the odds don't fully price
in, learned from how past picks actually turned out.

Each run fits a small logistic model on every graded pick that recorded
its signals (snapshots store them as "conf_features"), using the market's
no-vig probability for the picked side as a fixed baseline -- so the model
only learns what each signal adds on top of the odds:

- edge: the blended model's edge on the pick
- last5_clear: share of the player's last 5 games that went the picked way
- defense_supports: how much the opponent's defense factor leans toward
  the pick (+0.10 = it allows 10% more on an Over, or 10% less on an Under)
- share_trend: how the player's share of the team's targets (receiving
  markets) or carries (rushing) over the last 3 team games compares with
  the 7 before, signed toward the pick (log ratio; + = trending the
  pick's way). The model learns a negative weight: the market overreacts
  to recent usage swings. On 3,341 graded wk1-6 props, share spikes went
  Over 2.9 points less often than the odds implied and drops 2.4 more;
  as a fourth signal it lifted High from +3.8 to +4.6 points over the
  market (+6u to +17u), beating it in all 6 held-out weeks. Teammate
  absences and snap-share trends were tested too and added nothing (the
  market prices injuries fully).

Designed on 1,582 graded 2026 wk3-5 props, where the top fifth by
predicted advantage (High) appeared to hit 68.9% against 51.9% expected --
but much of that came from interception props graded on stats that never
counted interceptions (common.STATS_FIXES). With those regraded and the
stale picks left out, wk1-6 held out gives High 55.0% vs 50.7% expected,
about break-even on units. backtest() reruns this on every graded week for
the site. Other candidates -- results so far this
season (redundant with last 5), usage trend, snap share and trend, sample
size, volatility -- added nothing held out, so they aren't used.

Anytime TD isn't scored: nothing tested beat the market there.
"""
import glob
import json
import math
import os

import numpy as np

from common import MARKETS, modeled_on_stale_stats

FEATURES = ("edge", "last5_clear", "defense_supports", "share_trend")
MIN_TRAINING_PICKS = 300
# High = predicted advantage at or above this quantile of the training
# picks' predictions; Medium = any positive advantage; Low = negative.
HIGH_QUANTILE = 0.8
L2 = 1.0
REASON_MIN_WEIGHT = 0.05
MAX_REASONS = 3


def pick_features(game_log, side, line, defense_factor, edge):
    """Signals for one pick. game_log is most-recent-first."""
    sign = 1 if side == "over" else -1
    last5 = [g["value"] for g in game_log[:5]]
    went_our_way = sum((v > line) if sign == 1 else (v < line) for v in last5)
    return {
        "edge": edge,
        "last5_clear": went_our_way / len(last5),
        "last5_hits": went_our_way,
        "last5_n": len(last5),
        "defense_supports": sign * (defense_factor - 1),
        "defense_factor": defense_factor,
    }


TARGET_MARKETS = {"player_receptions", "player_reception_yds"}
CARRY_MARKETS = {"player_rush_yds", "player_rush_attempts"}
SHARE_RECENT_GAMES = 3
SHARE_WINDOW_GAMES = 10


def share_kind(market, position):
    """Which usage share drives this market, or None (QB markets)."""
    if market in TARGET_MARKETS:
        return "targets"
    if market in CARRY_MARKETS:
        return "carries"
    if market == "player_rush_reception_yds":
        return "targets" if position in ("WR", "TE") else "carries"
    return None


class ShareContext:
    """Per-team-game target/carry totals and each player's share of them,
    indexed once from the stats table for share_features."""

    def __init__(self, stats_df):
        df = stats_df[["player_id", "recent_team", "season", "week", "targets", "carries"]].copy()
        df[["targets", "carries"]] = df[["targets", "carries"]].fillna(0)
        keys = ["recent_team", "season", "week"]
        totals = df.groupby(keys)[["targets", "carries"]].sum()
        self.team_totals = {k: (row.targets, row.carries) for k, row in totals.iterrows()}
        self.team_games = {}
        for team, season, week in totals.index:
            self.team_games.setdefault(team, []).append((int(season), int(week)))
        for games in self.team_games.values():
            games.sort(reverse=True)
        own = df.groupby(["player_id"] + keys)[["targets", "carries"]].sum()
        self.player = {k: (row.targets, row.carries) for k, row in own.iterrows()}

    def ratio(self, player_id, team, season, week, kind):
        """Share over the last SHARE_RECENT_GAMES team games before
        (season, week) relative to the rest of the last
        SHARE_WINDOW_GAMES, or None if there's too little to compare."""
        if season is None or week is None:
            return None
        games = [g for g in self.team_games.get(team, []) if g < (season, week)][:SHARE_WINDOW_GAMES]
        if len(games) <= SHARE_RECENT_GAMES:
            return None
        i = 0 if kind == "targets" else 1
        shares = []
        for s, w in games:
            total = self.team_totals[(team, s, w)][i]
            mine = self.player.get((player_id, team, s, w), (0, 0))[i]
            shares.append(mine / total if total else 0.0)
        recent = sum(shares[:SHARE_RECENT_GAMES]) / SHARE_RECENT_GAMES
        older = sum(shares[SHARE_RECENT_GAMES:]) / len(shares[SHARE_RECENT_GAMES:])
        return recent / older if older > 0.02 else None


def share_features(ctx, player_id, team, season, week, market, position, side):
    kind = share_kind(market, position)
    ratio = ctx.ratio(player_id, team, season, week, kind) if kind else None
    sign = 1 if side == "over" else -1
    # A zero recent share almost always means the player missed those
    # games, not a real trend, so it counts as no trend.
    value = sign * math.log(min(max(ratio, 1 / 3), 3)) if ratio else 0.0
    return {"share_trend": value, "share_ratio": ratio, "share_kind": kind}


def backfill_share_trend(history_dir, stats_df):
    """Adds share_trend to graded and snapshotted picks recorded before it
    existed (from the same pre-week stats it would have used), so the
    model can train on it right away. A no-op once every pick has it."""
    ctx = None
    added = 0
    for path in sorted(glob.glob(os.path.join(history_dir, "*.json"))):
        if not os.path.basename(path).startswith(("picks_", "results_")):
            continue
        with open(path) as f:
            data = json.load(f)
        changed = False
        for pick in data["picks"]:
            feats = pick.get("conf_features")
            if not feats or "share_trend" in feats:
                continue
            if ctx is None:
                ctx = ShareContext(stats_df)
            feats.update(share_features(
                ctx, pick["player_id"], pick["team"], data["season"], data["week"],
                pick["market"], pick["position"], pick["side"],
            ))
            changed = True
            added += 1
        if changed:
            with open(path, "w") as f:
                json.dump(data, f)
    if added:
        print(f"Backfilled share_trend on {added} recorded picks")


def _logit(p):
    p = np.clip(p, 0.01, 0.99)
    return np.log(p / (1 - p))


def _graded_weeks(history_dir):
    """[(season, week, was it rebuilt by backfill_history.py, scorable picks)]."""
    weeks = []
    for path in sorted(glob.glob(os.path.join(history_dir, "results_*.json"))):
        with open(path) as f:
            data = json.load(f)
        picks = [
            p for p in data["picks"]
            if p.get("conf_features") and p["market"] != "player_anytime_td"
            # Its edge came from a model fed wrong stats (common.STATS_FIXES),
            # so it says nothing about what the signals are worth.
            and not modeled_on_stale_stats(p)
        ]
        backfilled = bool(data["picks"]) and all(p.get("backfilled") for p in data["picks"])
        weeks.append((data["season"], data["week"], backfilled, picks))
    return weeks


def _market_prob(pick):
    return pick["model_prob"] - pick["edge"]


def fit_model(history_dir, exclude_week=None):
    """None until there are enough graded picks with recorded signals.
    exclude_week=(season, week) leaves that week out (see backtest)."""
    picks = [
        p
        for season, week, _, week_picks in _graded_weeks(history_dir)
        if (season, week) != exclude_week
        for p in week_picks
    ]
    if len(picks) < MIN_TRAINING_PICKS:
        return None
    feats = [[p["conf_features"].get(k, 0.0) for k in FEATURES] for p in picks]
    market_probs = [_market_prob(p) for p in picks]
    hits = [1.0 if p["hit"] else 0.0 for p in picks]

    raw = np.array(feats, dtype=float)
    means, sds = raw.mean(axis=0), raw.std(axis=0)
    sds[sds == 0] = 1.0
    X = np.c_[np.ones(len(raw)), (raw - means) / sds]
    y = np.array(hits)
    offset = _logit(np.array(market_probs))
    penalty = np.diag([0.0] + [L2] * len(FEATURES))
    w = np.zeros(X.shape[1])
    for _ in range(50):
        mu = 1 / (1 + np.exp(-(offset + X @ w)))
        grad = X.T @ (mu - y) + penalty @ w
        hess = (X * (mu * (1 - mu))[:, None]).T @ X + penalty
        w -= np.linalg.solve(hess, grad)
    advantage = 1 / (1 + np.exp(-(offset + X @ w))) - np.array(market_probs)
    return {
        "means": means,
        "sds": sds,
        "weights": w,
        "high_cut": float(np.quantile(advantage, HIGH_QUANTILE)),
        "n": len(y),
    }


def _score(model, features, market_prob):
    """(tier, standardized features, predicted advantage over the market)."""
    z = (np.array([features.get(k, 0.0) for k in FEATURES], dtype=float) - model["means"]) / model["sds"]
    logit = _logit(market_prob) + model["weights"][0] + z @ model["weights"][1:]
    advantage = float(1 / (1 + np.exp(-logit)) - market_prob)
    if advantage >= model["high_cut"]:
        tier = "High"
    elif advantage >= 0:
        tier = "Medium"
    else:
        tier = "Low"
    return tier, z, advantage


def assess(model, features, market_prob, side, line, opponent, noun):
    """(tier, reasons, predicted advantage over the market)."""
    tier, z, advantage = _score(model, features, market_prob)

    contributions = dict(zip(FEATURES, model["weights"][1:] * z))
    texts = {
        "edge": f"Model edge of {features['edge'] * 100:.1f}%",
        "last5_clear": (
            f"Went {side} {line:g} in {features['last5_hits']} of the last {features['last5_n']} games"
        ),
        "defense_supports": _defense_text(features["defense_factor"], opponent, noun),
        "share_trend": _share_text(features.get("share_ratio"), features.get("share_kind")),
    }
    ranked = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)
    reasons = [
        {"text": texts[name], "supports": bool(c > 0)}
        for name, c in ranked[:MAX_REASONS]
        if abs(c) >= REASON_MIN_WEIGHT and texts[name]
    ]
    return tier, reasons, advantage


def _share_text(ratio, kind):
    if not ratio:
        return None
    pct = round(abs(ratio - 1) * 100)
    label = "Target share" if kind == "targets" else "Carry share"
    if pct < 5:
        return f"{label} steady over the last 3 games"
    return (
        f"{label} {'up' if ratio > 1 else 'down'} {pct}% over the last 3 games "
        "(the market tends to overreact to recent swings)"
    )


def _defense_text(factor, opponent, noun):
    pct = round(abs(factor - 1) * 100)
    if pct < 2:
        return f"{opponent} is about average against {noun}"
    return f"{opponent} allows {pct}% {'more' if factor > 1 else 'fewer'} {noun} than average"


def backtest(history_dir, edge_fn):
    """Today's confidence system replayed on every graded week: each week's
    picks are tiered by a model fit only on the *other* weeks, so no week
    is graded by a model that already saw its results. Covers every listed
    non-Anytime-TD pick with recorded signals, and includes weeks rebuilt
    by backfill_history.py (flagged), which the live track record leaves
    out. One row per pick, so the site can apply the track record's own
    filters; edge_fn gives the edge on the track record's scale."""
    weeks, picks = [], []
    for season, week, backfilled, week_picks in _graded_weeks(history_dir):
        model = fit_model(history_dir, exclude_week=(season, week)) if week_picks else None
        if model is None:
            continue
        weeks.append({"season": season, "week": week, "backfilled": backfilled, "trained_on": model["n"]})
        for p in week_picks:
            tier, _, _ = _score(model, p["conf_features"], _market_prob(p))
            picks.append({
                "season": season,
                "week": week,
                "confidence": tier,
                "side": p["side"],
                "market_label": MARKETS[p["market"]]["label"],
                "edge": edge_fn(p),
                "market_prob": round(_market_prob(p), 4),
                "hit": bool(p["hit"]),
                "price": p.get("price"),
            })
    return {"weeks": weeks, "picks": picks}


def write_backtest(history_dir, data_dir, edge_fn):
    result = backtest(history_dir, edge_fn)
    with open(os.path.join(data_dir, "confidence_backtest.json"), "w") as f:
        json.dump(result, f)
    print(
        f"Wrote confidence backtest ({len(result['weeks'])} weeks, {len(result['picks'])} picks) "
        "-> data/confidence_backtest.json"
    )
