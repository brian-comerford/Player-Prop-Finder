"""Fetch full-game and 1st/2nd-half spread and total odds for the upcoming
week's games from The Odds API (https://the-odds-api.com) -- the same
account/key used for player props (see fetch_odds.py), just different
market keys. No sample-data fallback here: unlike player props, there's no
good way to fake a plausible spread/total line from stats alone, so if no
API key is configured (or the call fails) this simply writes an empty
quote list and the Games tab has nothing to show, same as it would if a
player-prop book had no lines posted.

Output: data/game_odds_quotes.json, a flat list of:
{
  home_team, away_team, segment ("full"/"h1"/"h2"), market ("spread"/"total"),
  # spread:
  home_point, home_price, home_book, away_point, away_price, away_book,
  # total:
  point, over_price, over_book, under_price, under_book,
}
"""
import json
import os
import time

import pandas as pd
import requests

from common import DATA_DIR, TEAM_CODE_TO_NAME, TEAM_NAME_TO_CODE, utcnow_iso

ODDS_API_BASE = "https://api.the-odds-api.com/v4"
SPORT_KEY = "americanfootball_nfl"
BOOKMAKERS = "draftkings,fanduel"
ODDS_FORMAT = "american"

SEGMENT_MARKET_KEYS = {
    "full": {"spread": "spreads", "total": "totals"},
    "h1": {"spread": "spreads_h1", "total": "totals_h1"},
    "h2": {"spread": "spreads_h2", "total": "totals_h2"},
}
MARKET_KEY_TO_SEGMENT = {
    key: (segment, market)
    for segment, markets in SEGMENT_MARKET_KEYS.items()
    for market, key in markets.items()
}


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

    slate_matchups = {
        frozenset((TEAM_CODE_TO_NAME.get(g.home_team), TEAM_CODE_TO_NAME.get(g.away_team)))
        for g in slate.itertuples()
    }
    relevant_events = [
        e for e in events if frozenset((e["home_team"], e["away_team"])) in slate_matchups
    ]
    print(f"Found {len(relevant_events)} relevant events out of {len(events)} total")

    market_keys = ",".join(MARKET_KEY_TO_SEGMENT.keys())
    for event in relevant_events:
        url = f"{ODDS_API_BASE}/sports/{SPORT_KEY}/events/{event['id']}/odds"
        params = {
            "apiKey": api_key,
            "bookmakers": BOOKMAKERS,
            "markets": market_keys,
            "oddsFormat": ODDS_FORMAT,
        }
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            body = exc.response.text[:300] if exc.response is not None else ""
            print(f"  skipping event {event['id']} ({status}: {body})")
            if status == 401:
                print("  401 -- likely out of monthly credits or an invalid key; stopping.")
                break
            continue
        except requests.RequestException as exc:
            print(f"  skipping event {event['id']} ({exc})")
            continue
        payload = r.json()
        quotes.extend(_parse_event_odds(payload))
        time.sleep(0.25)
    return quotes


def _parse_event_odds(payload):
    home = payload.get("home_team")
    away = payload.get("away_team")
    home_code = TEAM_NAME_TO_CODE.get(home)
    away_code = TEAM_NAME_TO_CODE.get(away)
    if home_code is None or away_code is None:
        return []

    # (segment, market) -> side -> list of (point, price, book)
    buckets = {}
    for bm in payload.get("bookmakers", []):
        for market in bm.get("markets", []):
            seg_market = MARKET_KEY_TO_SEGMENT.get(market["key"])
            if seg_market is None:
                continue
            for outcome in market.get("outcomes", []):
                side = outcome.get("name")
                point = outcome.get("point")
                price = outcome.get("price")
                buckets.setdefault(seg_market, {}).setdefault(side, []).append(
                    (point, price, bm.get("key"))
                )

    quotes = []
    for (segment, market), sides in buckets.items():
        if market == "spread":
            home_entries = sides.get(home, [])
            away_entries = sides.get(away, [])
            if not home_entries or not away_entries:
                continue
            home_point, home_price, home_book = _consensus_pick(home_entries)
            away_point, away_price, away_book = _consensus_pick(away_entries)
            quotes.append(
                {
                    "home_team": home_code,
                    "away_team": away_code,
                    "segment": segment,
                    "market": market,
                    "home_point": home_point,
                    "home_price": home_price,
                    "home_book": home_book,
                    "away_point": away_point,
                    "away_price": away_price,
                    "away_book": away_book,
                }
            )
        else:  # total
            over_entries = sides.get("Over", [])
            under_entries = sides.get("Under", [])
            if not over_entries or not under_entries:
                continue
            point, over_price, over_book = _consensus_pick(over_entries)
            _, under_price, under_book = _consensus_pick(under_entries)
            quotes.append(
                {
                    "home_team": home_code,
                    "away_team": away_code,
                    "segment": segment,
                    "market": market,
                    "point": point,
                    "over_price": over_price,
                    "over_book": over_book,
                    "under_price": under_price,
                    "under_book": under_book,
                }
            )
    return quotes


def _consensus_pick(entries):
    """`entries` is [(point, price, book), ...] for one side across books.
    Picks the median line, then the best (most bettor-favorable) price
    among books posting that exact line -- same approach as the player-prop
    odds parser."""
    points = [p for p, _, _ in entries if p is not None]
    consensus_point = sorted(points)[len(points) // 2] if points else None
    at_point = [(pr, bk) for pt, pr, bk in entries if pt == consensus_point]
    if not at_point:
        at_point = [(pr, bk) for _, pr, bk in entries]
    price, book = max(at_point, key=lambda x: x[0])
    return consensus_point, price, book


def main():
    meta, slate = load_upcoming_slate()
    api_key = os.environ.get("ODDS_API_KEY")
    quotes = []
    source = "none"

    if slate.empty:
        print("No upcoming slate found; writing empty game odds file.")
    elif not api_key:
        print("No ODDS_API_KEY configured; game odds have no sample-data fallback, skipping.")
    else:
        try:
            quotes = fetch_live(slate, api_key)
            source = "live" if quotes else "none"
        except requests.RequestException as exc:
            print(f"Live game odds fetch failed ({exc}); writing empty game odds file.")

    with open(os.path.join(DATA_DIR, "game_odds_quotes.json"), "w") as f:
        json.dump(quotes, f)
    with open(os.path.join(DATA_DIR, "game_odds_meta.json"), "w") as f:
        json.dump({"source": source, "fetched_at": utcnow_iso(), "quote_count": len(quotes)}, f)

    print(f"Wrote {len(quotes)} game odds quotes (source={source})")


if __name__ == "__main__":
    main()
