"""Best-effort NFL player-prop quotes from Kalshi, a CFTC-regulated
prediction market (not a sportsbook -- its "odds" are contract prices,
which we convert to an equivalent American-odds figure so they flow
through the same value model as sportsbook quotes).

IMPORTANT: Kalshi's domains are blocked by this project's development
sandbox network policy, so this module was written from documented API
knowledge and could not be tested locally -- unlike scripts/fetch_stats.py
and scripts/fetch_odds.py, which were verified against live responses
before being relied on. The first real signal on whether this actually
works is the "Kalshi:" log lines this prints when scripts/generate_data.py
runs in GitHub Actions (which has full, unrestricted internet access).
Wrapped by its caller in fetch_odds.py so any failure here -- a changed
endpoint, an unexpected response shape, anything -- never breaks the rest
of the pipeline; this is purely additive on top of sportsbook/sample odds.
"""
import re

import requests

from common import normalize_name, prob_to_american

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
MAX_EVENT_PAGES = 3
EVENTS_PER_PAGE = 200

# Phrase found in a market's title -> one of our MARKETS keys. Order
# matters: more specific phrases must be checked before shorter ones they
# contain (e.g. "passing touchdown" before "touchdown").
STAT_KEYWORDS = [
    ("passing touchdown", "player_pass_tds"),
    ("passing yard", "player_pass_yds"),
    ("rushing yard", "player_rush_yds"),
    ("receiving yard", "player_reception_yds"),
    ("reception", "player_receptions"),
    ("touchdown", "player_anytime_td"),
]

THRESHOLD_RE = re.compile(r"(\d+(?:\.\d+)?)")
NFL_HINT_WORDS = ("nfl", "reception", "receiving yard", "rushing yard", "passing yard", "touchdown")


def fetch_kalshi_quotes(slate, stats_df):
    events = _fetch_candidate_events()
    print(f"Kalshi: found {len(events)} candidate events after keyword filtering")
    if not events:
        return []

    team_codes = set(slate["home_team"]) | set(slate["away_team"])
    opponent_of = {}
    for g in slate.itertuples():
        opponent_of[g.home_team] = g.away_team
        opponent_of[g.away_team] = g.home_team

    player_lookup = _build_player_lookup(stats_df, team_codes)
    print(f"Kalshi: matching against {len(player_lookup)} active players from this week's teams")

    quotes = []
    logged_sample = False
    for event in events:
        for market in event.get("markets", []):
            if not logged_sample:
                print(f"Kalshi: sample market payload -> {market}")
                logged_sample = True

            title = market.get("title") or market.get("subtitle") or market.get("yes_sub_title") or ""
            match = _match_market(title, player_lookup)
            if match is None:
                continue
            player_row, market_key, threshold = match

            team = player_row["recent_team"]
            if team not in opponent_of:
                continue

            prob = _extract_probability(market)
            if prob is None:
                continue

            quotes.append(
                {
                    "player_name": player_row["player_display_name"],
                    "home_team": team,
                    "away_team": opponent_of[team],
                    "market": market_key,
                    "point": threshold,
                    "price_over": prob_to_american(prob),
                    "price_under": prob_to_american(1 - prob),
                    "book_over": "kalshi",
                    "book_under": "kalshi",
                }
            )

    print(f"Kalshi: matched {len(quotes)} player-prop quotes")
    return quotes


def _fetch_candidate_events():
    events = []
    cursor = None
    for _ in range(MAX_EVENT_PAGES):
        params = {"status": "open", "with_nested_markets": "true", "limit": EVENTS_PER_PAGE}
        if cursor:
            params["cursor"] = cursor
        resp = requests.get(f"{KALSHI_BASE}/events", params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        page = payload.get("events", [])
        events.extend(page)
        cursor = payload.get("cursor")
        if not cursor or not page:
            break

    def is_relevant(event):
        haystack = " ".join(
            str(event.get(field, "")) for field in ("title", "category", "sub_title", "series_ticker")
        ).lower()
        return any(word in haystack for word in NFL_HINT_WORDS)

    return [e for e in events if is_relevant(e)]


def _build_player_lookup(stats_df, team_codes):
    recent = stats_df.sort_values(["season", "week"]).groupby("player_id").tail(1)
    active = recent[recent["recent_team"].isin(team_codes)]
    lookup = []
    for _, row in active.iterrows():
        if row["position"] not in ("QB", "RB", "WR", "TE"):
            continue
        lookup.append((normalize_name(row["player_display_name"]), row))
    # Longest names first so e.g. "Josh Allen" doesn't get shadowed by a
    # coincidental shorter match.
    return sorted(lookup, key=lambda item: -len(item[0]))


def _match_market(title, player_lookup):
    if not title:
        return None
    norm_title = normalize_name(title)
    lower_title = title.lower()

    player_row = None
    for norm_name, row in player_lookup:
        if norm_name and norm_name in norm_title:
            player_row = row
            break
    if player_row is None:
        return None

    for phrase, market_key in STAT_KEYWORDS:
        if phrase not in lower_title:
            continue
        binary = market_key == "player_anytime_td"
        threshold_match = THRESHOLD_RE.search(title)
        if binary:
            return player_row, market_key, None
        if not threshold_match:
            continue
        # Kalshi's "X+" threshold markets pay out on X or more; our
        # over/under model uses a strict ">", so shift down half a unit to
        # keep "6+" behaving like "over 5.5".
        threshold = float(threshold_match.group(1)) - 0.5
        return player_row, market_key, threshold

    return None


def _extract_probability(market):
    """Returns a 0-1 probability from whichever price field is populated,
    preferring the last traded price over a resting bid/ask quote."""
    for field in ("last_price", "yes_bid", "yes_ask"):
        value = market.get(field)
        if value:
            return max(0.01, min(0.99, value / 100.0))
    return None
