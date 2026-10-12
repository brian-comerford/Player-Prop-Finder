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

Backtested on 1,582 graded 2026 wk3-5 props, scoring each week with a model
fit only on the other weeks: the top fifth by predicted advantage over the
market (High) hit 68.9% against 51.9% expected; the old games-and-
consistency label's High hit 49.4%. Other candidates -- results so far this
season (redundant with last 5), usage trend, snap share and trend, sample
size, volatility -- added nothing held out, so they aren't used.

Anytime TD isn't scored: nothing tested beat the market there.
"""
import glob
import json
import os

import numpy as np

FEATURES = ("edge", "last5_clear", "defense_supports")
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


def _logit(p):
    p = np.clip(p, 0.01, 0.99)
    return np.log(p / (1 - p))


def fit_model(history_dir):
    """None until there are enough graded picks with recorded signals."""
    feats, market_probs, hits = [], [], []
    for path in sorted(glob.glob(os.path.join(history_dir, "results_*.json"))):
        with open(path) as f:
            data = json.load(f)
        for pick in data["picks"]:
            f_ = pick.get("conf_features")
            if not f_ or pick["market"] == "player_anytime_td":
                continue
            feats.append([f_[k] for k in FEATURES])
            market_probs.append(pick["model_prob"] - pick["edge"])
            hits.append(1.0 if pick["hit"] else 0.0)
    if len(hits) < MIN_TRAINING_PICKS:
        return None

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


def assess(model, features, market_prob, side, line, opponent, noun):
    """(tier, reasons, predicted advantage over the market)."""
    z = (np.array([features[k] for k in FEATURES], dtype=float) - model["means"]) / model["sds"]
    logit = _logit(market_prob) + model["weights"][0] + z @ model["weights"][1:]
    advantage = float(1 / (1 + np.exp(-logit)) - market_prob)
    if advantage >= model["high_cut"]:
        tier = "High"
    elif advantage >= 0:
        tier = "Medium"
    else:
        tier = "Low"

    contributions = dict(zip(FEATURES, model["weights"][1:] * z))
    texts = {
        "edge": f"Model edge of {features['edge'] * 100:.1f}%",
        "last5_clear": (
            f"Went {side} {line:g} in {features['last5_hits']} of the last {features['last5_n']} games"
        ),
        "defense_supports": _defense_text(features["defense_factor"], opponent, noun),
    }
    ranked = sorted(contributions.items(), key=lambda kv: abs(kv[1]), reverse=True)
    reasons = [
        {"text": texts[name], "supports": bool(c > 0)}
        for name, c in ranked[:MAX_REASONS]
        if abs(c) >= REASON_MIN_WEIGHT
    ]
    return tier, reasons, advantage


def _defense_text(factor, opponent, noun):
    pct = round(abs(factor - 1) * 100)
    if pct < 2:
        return f"{opponent} is about average against {noun}"
    return f"{opponent} allows {pct}% {'more' if factor > 1 else 'fewer'} {noun} than average"
