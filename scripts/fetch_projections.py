"""Saves outside fantasy projections for a week next to the pick history,
so how far each source's number sits from a prop's line can be backtested
as a signal (see confidence.py) -- the projections live sites don't keep,
and a past week's can't be re-fetched once a site moves on.

Sources (both public, unofficial, and best-effort: a failure or an
unexpected response just skips that source):
- ESPN's fantasy projections endpoint (also used live by analyze.py)
- Sleeper's projections endpoint

Each is written to data/history/projections_{source}_{season}_wk{week}.json
as {"players": {gsis_id: {"name", "team", "position", <stat>: value}}}
with stats named by our own markets (see STAT_KEYS).

Usage: python scripts/fetch_projections.py --season 2026 --weeks 1-7
(the daily pipeline calls save_week() for the upcoming week).
"""
import argparse
import json
import os

import pandas as pd
import requests
from common import DATA_DIR, utcnow_iso
from fetch_stats import ESPN_PROJECTIONS_URL_TEMPLATE, PLAYER_ID_CROSSWALK_URL

HISTORY_DIR = os.path.join(DATA_DIR, "history")
SLEEPER_URL = (
    "https://api.sleeper.app/projections/nfl/{season}/{week}"
    "?season_type=regular&position[]=QB&position[]=RB&position[]=WR&position[]=TE"
)
POSITIONS = {"QB", "RB", "WR", "TE"}
# Our stat names (summed per market the same way MARKETS' stat_cols are).
STAT_KEYS = (
    "pass_att", "pass_yd", "pass_td", "pass_int",
    "rush_att", "rush_yd", "rush_td",
    "rec_tgt", "rec", "rec_yd", "rec_td",
)
# ESPN's numeric stat ids for those (statSourceId 1 = projected).
ESPN_STAT_IDS = {
    0: "pass_att", 3: "pass_yd", 4: "pass_td", 20: "pass_int",
    23: "rush_att", 24: "rush_yd", 25: "rush_td",
    58: "rec_tgt", 41: "rec", 42: "rec_yd", 43: "rec_td",
}


def load_crosswalk():
    """{"espn": {espn_id: gsis_id}, "sleeper": {sleeper_id: gsis_id}}"""
    cols = ["gsis_id", "espn_id", "sleeper_id"]
    df = pd.read_csv(PLAYER_ID_CROSSWALK_URL, low_memory=False, usecols=cols).dropna(subset=["gsis_id"])
    out = {}
    for source in ("espn", "sleeper"):
        sub = df.dropna(subset=[f"{source}_id"])
        out[source] = {str(int(float(i))): g for i, g in zip(sub[f"{source}_id"], sub["gsis_id"])}
    return out


def fetch_espn(season, week, espn_to_gsis):
    resp = requests.get(
        ESPN_PROJECTIONS_URL_TEMPLATE.format(season=season, week=week),
        headers={"x-fantasy-filter": json.dumps({"players": {"filterActive": {"value": True}}})},
        timeout=180,
    )
    resp.raise_for_status()
    players = {}
    for p in resp.json():
        gsis = espn_to_gsis.get(str(p.get("id")))
        if gsis is None:
            continue
        entry = next(
            (
                s for s in p.get("stats", [])
                if s.get("scoringPeriodId") == week and s.get("seasonId") == season
                and s.get("statSourceId") == 1 and s.get("statSplitTypeId") == 1
            ),
            None,
        )
        if not entry or not entry.get("stats"):
            continue
        stats = {k: entry["stats"][str(i)] for i, k in ESPN_STAT_IDS.items() if str(i) in entry["stats"]}
        if stats:
            players[gsis] = {"name": p.get("fullName"), **stats}
    return players


def fetch_sleeper(season, week, sleeper_to_gsis):
    resp = requests.get(SLEEPER_URL.format(season=season, week=week), timeout=120)
    resp.raise_for_status()
    players = {}
    for row in resp.json():
        gsis = sleeper_to_gsis.get(str(row.get("player_id")))
        stats_in = row.get("stats") or {}
        if gsis is None or not stats_in:
            continue
        stats = {k: stats_in[k] for k in STAT_KEYS if k in stats_in}
        if stats:
            info = row.get("player") or {}
            name = " ".join(x for x in (info.get("first_name"), info.get("last_name")) if x)
            players[gsis] = {"name": name or None, "team": row.get("team"), "position": info.get("position"), **stats}
    return players


FETCHERS = {"espn": fetch_espn, "sleeper": fetch_sleeper}


def summarize(source, players, positions):
    """One log line per position: how many players, and the average
    projection per stat -- a quick check that the stat mapping is right
    (a starting QB should project ~30 attempts and ~0.7 interceptions)."""
    print(f"  {source}: {len(players)} players matched")
    for pos in ("QB", "RB", "WR", "TE"):
        rows = [p for gid, p in players.items() if positions.get(gid) == pos]
        if not rows:
            continue
        top = sorted(rows, key=lambda p: -(p.get("pass_yd", 0) + p.get("rush_yd", 0) + p.get("rec_yd", 0)))[:24]
        means = {k: round(sum(p.get(k, 0) for p in top) / len(top), 2) for k in STAT_KEYS if any(k in p for p in top)}
        print(f"    {pos} (top {len(top)}): {means}")


def save_week(season, week, crosswalk=None, positions=None):
    """Fetches and writes every source for one week; returns {source: n}."""
    if crosswalk is None:
        try:
            crosswalk = load_crosswalk()
        except (requests.RequestException, ValueError, OSError) as exc:
            print(f"  player ID crosswalk unavailable ({exc}); skipping projections")
            return {}
    os.makedirs(HISTORY_DIR, exist_ok=True)
    counts = {}
    for source, fetch in FETCHERS.items():
        try:
            players = fetch(season, week, crosswalk[source])
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            print(f"  {source} projections for {season} wk{week} unavailable ({exc}); skipping")
            continue
        if not players:
            print(f"  {source} projections for {season} wk{week}: nothing matched; skipping")
            continue
        path = os.path.join(HISTORY_DIR, f"projections_{source}_{season}_wk{week}.json")
        with open(path, "w") as f:
            json.dump({"source": source, "season": season, "week": week,
                       "fetched_at": utcnow_iso(), "players": players}, f)
        counts[source] = len(players)
        if positions is not None:
            summarize(source, players, positions)
    return counts


def parse_weeks(text):
    weeks = set()
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            weeks.update(range(int(a), int(b) + 1))
        elif part:
            weeks.add(int(part))
    return sorted(weeks)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--weeks", required=True, help="e.g. 1-7 or 1,3,5")
    args = ap.parse_args()
    crosswalk = load_crosswalk()
    positions = {}
    stats_path = os.path.join(DATA_DIR, "player_stats_recent.csv")
    if os.path.exists(stats_path):
        stats = pd.read_csv(stats_path, low_memory=False, usecols=["player_id", "position"])
        positions = dict(zip(stats["player_id"], stats["position"]))
    for week in parse_weeks(args.weeks):
        print(f"wk{week}:")
        print(f"  saved {save_week(args.season, week, crosswalk, positions)}")


if __name__ == "__main__":
    main()
