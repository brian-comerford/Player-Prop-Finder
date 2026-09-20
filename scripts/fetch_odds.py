"""Fetch player prop odds for the upcoming week's games.

Live mode (default once configured): calls The Odds API
(https://the-odds-api.com), which has a free tier (500 credits/month).
Requires an ODDS_API_KEY environment variable / GitHub Actions secret.

Sample mode (automatic fallback): if no API key is set, or the API call
fails, this generates clearly-labeled sample odds derived from each
player's own recent stat average with a randomized line/vig, so the app
has something to show without any account signup. The output JSON always
records which mode produced it (`meta.source`) and the frontend surfaces
that to the user.

Either way the output is a flat list of "quotes":
{
  player_name, team, opponent, market, point,
  price_over, price_under,   # American odds; price_over/price_under are
                              # reused as price_yes/price_no for the
                              # binary "anytime_td" market
  book
}
written to data/odds_quotes.json alongside data/odds_meta.json.
"""
import json
import os
import random
import time

import pandas as pd
import requests

from common import DATA_DIR, MARKETS, TEAM_CODE_TO_NAME, TEAM_NAME_TO_CODE, utcnow_iso

ODDS_API_BASE = "https://api.the-odds-api.com/v4"
SPORT_KEY = "americanfootball_nfl"
REGIONS = "us"
ODDS_FORMAT = "american"


def load_upcoming_slate():
    with open(os.path.join(DATA_DIR, "season_week.json")) as f:
        meta = json.load(f)
    season, week = meta["upcoming_season"], meta["upcoming_week"]
    if season is None:
        return meta, pd.DataFrame()
    games = pd.read_csv(os.path.join(DATA_DIR, "games_recent.csv"), low_memory=False)
    slate = games[(games["season"] == season) & (games["week"] == week)].copy()
    return meta, slate


def fetch_live(slate, api_key):
    quotes = []
    events_url = f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events"
    resp = requests.get(events_url, params={"apiKey": api_key}, timeout=30)
    resp.raise_for_status()
    events = resp.json()

    slate_team_names = set(slate["home_team"].map(TEAM_CODE_TO_NAME)) | set(
        slate["away_team"].map(TEAM_CODE_TO_NAME)
    )
    relevant_events = [
        e for e in events if e["home_team"] in slate_team_names and e["away_team"] in slate_team_names
    ]
    print(f"Found {len(relevant_events)} relevant events out of {len(events)} total")

    market_keys = ",".join(MARKETS.keys())
    for event in relevant_events:
        url = f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events/{event['id']}/odds"
        params = {
            "apiKey": api_key,
            "regions": REGIONS,
            "markets": market_keys,
            "oddsFormat": ODDS_FORMAT,
        }
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
        except requests.RequestException as exc:
            print(f"  skipping event {event['id']} ({exc})")
            continue
        payload = r.json()
        quotes.extend(_parse_event_odds(payload))
        time.sleep(0.25)  # be polite / stay well under rate limits
    return quotes


def _parse_event_odds(payload):
    """Flatten one event's bookmaker odds into per-(player, market) quotes,
    keeping the best (most favorable to the bettor) price at the most
    common line across books.
    """
    home = payload.get("home_team")
    away = payload.get("away_team")
    home_code = TEAM_NAME_TO_CODE.get(home)
    away_code = TEAM_NAME_TO_CODE.get(away)

    # market -> player -> side -> list of (point, price, book)
    buckets = {}
    for bm in payload.get("bookmakers", []):
        for market in bm.get("markets", []):
            mkey = market["key"]
            if mkey not in MARKETS:
                continue
            for outcome in market.get("outcomes", []):
                player = outcome.get("description")
                if not player:
                    continue
                side = outcome.get("name", "").lower()  # "over"/"under" or "yes"/"no"
                point = outcome.get("point")
                price = outcome.get("price")
                buckets.setdefault(mkey, {}).setdefault(player, {}).setdefault(side, []).append(
                    (point, price, bm.get("key"))
                )

    quotes = []
    for mkey, players in buckets.items():
        binary = MARKETS[mkey].get("binary", False)
        for player, sides in players.items():
            if binary:
                yes = sides.get("yes", [])
                no = sides.get("no", [])
                if not yes:
                    continue
                price_yes = max(p for _, p, _ in yes)
                price_no = max((p for _, p, _ in no), default=None)
                quotes.append(
                    {
                        "player_name": player,
                        "home_team": home_code,
                        "away_team": away_code,
                        "market": mkey,
                        "point": None,
                        "price_over": price_yes,
                        "price_under": price_no,
                        "book": "best_available",
                    }
                )
                continue

            over = sides.get("over", [])
            under = sides.get("under", [])
            if not over or not under:
                continue
            points = [p for p, _, _ in over + under if p is not None]
            if not points:
                continue
            consensus_point = sorted(points)[len(points) // 2]  # median
            over_at_point = [pr for pt, pr, _ in over if pt == consensus_point]
            under_at_point = [pr for pt, pr, _ in under if pt == consensus_point]
            if not over_at_point or not under_at_point:
                continue
            quotes.append(
                {
                    "player_name": player,
                    "home_team": home_code,
                    "away_team": away_code,
                    "market": mkey,
                    "point": consensus_point,
                    "price_over": max(over_at_point),
                    "price_under": max(under_at_point),
                    "book": "best_available",
                }
            )
    return quotes


def generate_sample(slate, stats_df):
    """Build plausible-looking sample odds from real recent player stats so
    the app is fully demo-able without any API key. Clearly not real
    sportsbook lines -- the frontend labels this mode prominently.
    """
    rng = random.Random(42)
    quotes = []
    team_codes = set(slate["home_team"]) | set(slate["away_team"])
    opponent_of = {}
    for _, g in slate.iterrows():
        opponent_of[g["home_team"]] = g["away_team"]
        opponent_of[g["away_team"]] = g["home_team"]

    recent_teams = stats_df.sort_values(["season", "week"]).groupby("player_id").tail(1)
    active = recent_teams[recent_teams["recent_team"].isin(team_codes)]

    for _, row in active.iterrows():
        team = row["recent_team"]
        if team not in opponent_of:
            continue
        player_games = stats_df[stats_df["player_id"] == row["player_id"]]
        for mkey, cfg in MARKETS.items():
            if row["position"] not in cfg["position_group"]:
                continue
            if cfg.get("binary"):
                rate = (player_games[cfg["stat_cols"]].sum(axis=1) > 0).mean()
                if pd.isna(rate) or len(player_games) < 2:
                    continue
                price_yes = _prob_to_american(min(max(rate * rng.uniform(0.85, 1.15), 0.05), 0.9))
                quotes.append(
                    {
                        "player_name": row["player_display_name"],
                        "home_team": team,
                        "away_team": opponent_of[team],
                        "market": mkey,
                        "point": None,
                        "price_over": price_yes,
                        "price_under": None,
                        "book": "sample",
                    }
                )
                continue

            values = player_games[cfg["stat_cols"]].sum(axis=1)
            if len(values) < 2 or values.mean() <= 0:
                continue
            avg = values.mean()
            increment = 0.5 if avg < 30 else 5.0 if avg < 150 else 10.0
            noisy_line = avg * rng.uniform(0.88, 1.12)
            line = round(noisy_line / increment) * increment
            price_over = rng.choice([-110, -115, -105, 100, -120])
            price_under = rng.choice([-110, -105, -115, -105])
            quotes.append(
                {
                    "player_name": row["player_display_name"],
                    "home_team": team,
                    "away_team": opponent_of[team],
                    "market": mkey,
                    "point": line,
                    "price_over": price_over,
                    "price_under": price_under,
                    "book": "sample",
                }
            )
    return quotes


def _prob_to_american(p):
    if p >= 0.5:
        return round(-100 * p / (1 - p))
    return round(100 * (1 - p) / p)


def main():
    meta, slate = load_upcoming_slate()
    stats_df = pd.read_csv(os.path.join(DATA_DIR, "player_stats_recent.csv"), low_memory=False)

    api_key = os.environ.get("ODDS_API_KEY")
    source = "sample"
    quotes = []

    if slate.empty:
        print("No upcoming slate found; writing empty odds file.")
    elif api_key:
        try:
            quotes = fetch_live(slate, api_key)
            if quotes:
                source = "live"
            else:
                print("Live odds call returned no player-prop quotes; falling back to sample data.")
        except requests.RequestException as exc:
            print(f"Live odds fetch failed ({exc}); falling back to sample data.")

    if source == "sample" and not slate.empty:
        quotes = generate_sample(slate, stats_df)

    with open(os.path.join(DATA_DIR, "odds_quotes.json"), "w") as f:
        json.dump(quotes, f)

    with open(os.path.join(DATA_DIR, "odds_meta.json"), "w") as f:
        json.dump({"source": source, "fetched_at": utcnow_iso(), "quote_count": len(quotes)}, f)

    print(f"Wrote {len(quotes)} odds quotes (source={source})")


if __name__ == "__main__":
    main()
