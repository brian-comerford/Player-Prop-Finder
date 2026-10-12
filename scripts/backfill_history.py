"""Backfill pick history from The Odds API's historical snapshots.

Two jobs, both reading each game's player-prop odds as they stood an hour
before its kickoff:

- Full weeks (--full-weeks): rebuild a week the app never snapshotted.
  Runs the normal analyze.py pipeline in a scratch directory, with only
  the stats from before that week, and saves its picks to
  data/history/picks_{season}_wk{week}.json with every pick flagged
  "backfilled". The regular grading run grades them like any other week.
  They train the market blend and confidence model, but the public track
  record leaves them out, since nobody saw them before the games.
- Price weeks (--price-weeks): fill in the odds for real, already-shown
  picks that were snapshotted before prices were recorded, so they count
  toward units won. A price is only filled when the historical consensus
  line matches the pick's line; those picks are marked "price_backfilled".

Historical requests cost 10x normal (about 100 credits per game here), so
the script stops once the account's remaining credits fall below
--credit-floor. A game missing from the historical data is skipped (a
rebuilt week is written with whatever games were found), and fetched odds
are saved to data/backfill_quotes/ after every game so a crash doesn't
waste credits already spent. --dry-run lists what would be fetched
without calling the API.

Run from scripts/ after fetch_stats.py (needs data/player_stats_recent.csv
and data/games_recent.csv); see .github/workflows/backfill-history.yml.
"""
import argparse
import json
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import requests

import analyze
from common import DATA_DIR, MARKETS, TEAM_CODE_TO_NAME, normalize_name, utcnow_iso
from fetch_odds import BOOKMAKERS, ODDS_API_BASE, ODDS_FORMAT, SPORT_KEY, _parse_event_odds

HISTORY_DIR = os.path.join(DATA_DIR, "history")
QUOTES_DIR = os.path.join(DATA_DIR, "backfill_quotes")
EASTERN = ZoneInfo("America/New_York")
SNAPSHOT_LEAD = timedelta(hours=1)
EST_CREDITS_PER_GAME = 10 * len(MARKETS)


class OutOfCredits(Exception):
    pass


def kickoff_utc(game):
    local = datetime.strptime(f"{game.gameday} {game.gametime}", "%Y-%m-%d %H:%M").replace(tzinfo=EASTERN)
    return local.astimezone(timezone.utc)


def snapshot_time(game, for_prices):
    """When to read the odds. Rebuilt weeks use an hour before kickoff, the
    sharpest pre-game line. Price fills try to match the line the real
    pick was frozen at, which was usually the daily 13:00 UTC run on game
    day (deploy.yml's schedule)."""
    kickoff = kickoff_utc(game)
    if for_prices:
        daily_run = datetime.strptime(game.gameday, "%Y-%m-%d").replace(hour=13, tzinfo=timezone.utc)
        if daily_run < kickoff:
            return daily_run
    return kickoff - SNAPSHOT_LEAD


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def api_get(path, params, api_key, credit_floor):
    resp = requests.get(f"{ODDS_API_BASE}{path}", params={"apiKey": api_key, **params}, timeout=30)
    resp.raise_for_status()
    remaining = resp.headers.get("x-requests-remaining")
    print(f"    cost {resp.headers.get('x-requests-last', '?')}, remaining {remaining}")
    if remaining is not None and float(remaining) < credit_floor:
        raise OutOfCredits(f"remaining credits {remaining} fell below the floor of {credit_floor}")
    payload = resp.json()
    return payload.get("data", payload)


def event_ids_at(date, api_key, credit_floor):
    events = api_get(f"/historical/sports/{SPORT_KEY}/events", {"date": date}, api_key, credit_floor)
    return {frozenset((e["home_team"], e["away_team"])): e["id"] for e in events}


def event_odds(event_id, snapshot, api_key, credit_floor):
    """The event's odds payload, or None if that event ID isn't found at
    that time -- IDs can change when a game is rescheduled."""
    try:
        return api_get(
            f"/historical/sports/{SPORT_KEY}/events/{event_id}/odds",
            {"date": snapshot, "bookmakers": BOOKMAKERS, "markets": ",".join(MARKETS), "oddsFormat": ODDS_FORMAT},
            api_key,
            credit_floor,
        )
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return None
        raise


def fetch_week_quotes(season, week, slate, api_key, credit_floor, for_prices):
    """{"AWAY@HOME": [quotes]} for the games in `slate` that could be
    fetched. Saved to QUOTES_DIR after every game, and reused on a rerun,
    so credits already spent survive a crash."""
    os.makedirs(QUOTES_DIR, exist_ok=True)
    cache_path = os.path.join(QUOTES_DIR, f"{season}_wk{week}.json")
    quotes = {}
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            quotes = json.load(f)
    todo = [g for g in slate.itertuples() if f"{g.away_team}@{g.home_team}" not in quotes]
    if not todo:
        return quotes
    first_kickoff = min(kickoff_utc(g) for g in todo)
    event_ids = event_ids_at(iso(first_kickoff - timedelta(days=1)), api_key, credit_floor)
    for g in todo:
        name = f"{g.away_team}@{g.home_team}"
        key = frozenset((TEAM_CODE_TO_NAME.get(g.home_team), TEAM_CODE_TO_NAME.get(g.away_team)))
        snapshot = iso(snapshot_time(g, for_prices))
        print(f"  {name} at {snapshot}")
        event_id = event_ids.get(key)
        data = event_odds(event_id, snapshot, api_key, credit_floor) if event_id else None
        if data is None:
            fresh_id = event_ids_at(snapshot, api_key, credit_floor).get(key)
            if fresh_id and fresh_id != event_id:
                print(f"    retrying under event id as of {snapshot}")
                data = event_odds(fresh_id, snapshot, api_key, credit_floor)
        if data is None:
            print("    not found in the historical data, skipping")
            continue
        quotes[name] = _parse_event_odds(data)
        with open(cache_path, "w") as f:
            json.dump(quotes, f)
    return quotes


def rebuild_week(season, week, quotes, stats_df, games_path):
    """Runs analyze.main point-in-time for one week in a scratch dir and
    returns its picks snapshot, every pick flagged as backfilled."""
    scratch = tempfile.mkdtemp(prefix=f"backfill_wk{week}_")
    try:
        pre = stats_df[(stats_df["season"] < season) | ((stats_df["season"] == season) & (stats_df["week"] < week))]
        pre.to_csv(os.path.join(scratch, "player_stats_recent.csv"), index=False)
        shutil.copy(games_path, os.path.join(scratch, "games_recent.csv"))
        inputs = {
            "season_week.json": {"baseline_season": season - 1, "upcoming_season": season, "upcoming_week": week},
            "odds_meta.json": {"source": "live", "fetched_at": utcnow_iso()},
            "odds_quotes.json": quotes,
            "player_activity.json": {},
        }
        for name, value in inputs.items():
            with open(os.path.join(scratch, name), "w") as f:
                json.dump(value, f)
        saved = analyze.DATA_DIR, analyze.HISTORY_DIR
        analyze.DATA_DIR, analyze.HISTORY_DIR = scratch, os.path.join(scratch, "history")
        try:
            analyze.main()
        finally:
            analyze.DATA_DIR, analyze.HISTORY_DIR = saved
        with open(os.path.join(scratch, "history", f"picks_{season}_wk{week}.json")) as f:
            snapshot = json.load(f)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    for pick in snapshot["picks"]:
        pick["backfilled"] = True
    snapshot["backfilled_at"] = utcnow_iso()
    return snapshot


def fill_prices(path, quotes_by_game):
    """Adds the historical price to picks in `path` that have none, when the
    historical consensus line matches the pick's own line."""
    if not os.path.exists(path):
        return
    index = {}
    for quotes in quotes_by_game.values():
        for q in quotes:
            index[(normalize_name(q["player_name"]), q["market"])] = q
    with open(path) as f:
        data = json.load(f)
    filled = no_quote = line_moved = 0
    for pick in data["picks"]:
        if pick.get("price") is not None:
            continue
        q = index.get((normalize_name(pick["player_name"]), pick["market"]))
        if q is None:
            no_quote += 1
        elif q["point"] != pick["line"]:
            line_moved += 1
        else:
            pick["price"] = q["price_over"] if pick["side"] == "over" else q["price_under"]
            pick["price_backfilled"] = True
            filled += 1
    with open(path, "w") as f:
        json.dump(data, f)
    print(f"  {os.path.basename(path)}: filled {filled}, no historical quote {no_quote}, line had moved {line_moved}")


def games_missing_prices(season, week, slate):
    path = os.path.join(HISTORY_DIR, f"picks_{season}_wk{week}.json")
    if not os.path.exists(path):
        return slate.iloc[0:0]
    with open(path) as f:
        teams = {p["team"] for p in json.load(f)["picks"] if p.get("price") is None}
    return slate[slate["home_team"].isin(teams) | slate["away_team"].isin(teams)]


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--full-weeks", default="", help="comma-separated weeks to rebuild, e.g. 1,2")
    parser.add_argument("--price-weeks", default="", help="comma-separated weeks to fill prices for, e.g. 3,4")
    parser.add_argument("--credit-floor", type=float, default=7000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    full_weeks = [int(w) for w in args.full_weeks.split(",") if w]
    price_weeks = [int(w) for w in args.price_weeks.split(",") if w]

    games_path = os.path.join(DATA_DIR, "games_recent.csv")
    games = pd.read_csv(games_path, low_memory=False)
    stats_df = pd.read_csv(os.path.join(DATA_DIR, "player_stats_recent.csv"), low_memory=False)

    plan = []
    for week in sorted(set(full_weeks) | set(price_weeks)):
        slate = games[(games["season"] == args.season) & (games["week"] == week)]
        if week not in full_weeks:
            slate = games_missing_prices(args.season, week, slate)
        if week in full_weeks and os.path.exists(os.path.join(HISTORY_DIR, f"picks_{args.season}_wk{week}.json")):
            print(f"wk{week}: already has a picks snapshot, not rebuilding it")
            continue
        if not slate.empty:
            plan.append((week, slate))
    total = sum(len(s) for _, s in plan)
    print(f"Plan: {total} games, est. ~{total * EST_CREDITS_PER_GAME + len(plan)} credits")
    for week, slate in plan:
        kind = "rebuild picks" if week in full_weeks else "fill prices"
        print(f"  wk{week} ({kind}): {', '.join(f'{g.away_team}@{g.home_team}' for g in slate.itertuples())}")
    if args.dry_run:
        return

    api_key = os.environ["ODDS_API_KEY"]
    for week, slate in plan:
        print(f"\nwk{week}: fetching {len(slate)} games")
        stopping = False
        try:
            quotes = fetch_week_quotes(args.season, week, slate, api_key, args.credit_floor, week not in full_weeks)
        except OutOfCredits as exc:
            print(f"Stopping after this week: {exc}")
            stopping = True
            cache_path = os.path.join(QUOTES_DIR, f"{args.season}_wk{week}.json")
            quotes = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
        print(f"  have odds for {len(quotes)} of {len(slate)} games")
        if not quotes:
            pass
        elif week in full_weeks:
            # A partial week is still useful training data, and these
            # picks never appear in the public track record anyway.
            snapshot = rebuild_week(args.season, week, [q for qs in quotes.values() for q in qs], stats_df, games_path)
            with open(os.path.join(HISTORY_DIR, f"picks_{args.season}_wk{week}.json"), "w") as f:
                json.dump(snapshot, f)
            print(f"  wrote {len(snapshot['picks'])} backfilled picks")
        else:
            for prefix in ("picks", "results"):
                fill_prices(os.path.join(HISTORY_DIR, f"{prefix}_{args.season}_wk{week}.json"), quotes)
        if stopping:
            break


if __name__ == "__main__":
    main()
