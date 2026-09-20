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
# Used to decide whether a *market* (not just its parent event) is even a
# candidate stat-threshold prop worth trying to match a player against --
# deliberately the same phrases _match_market looks for, since a market
# without one of these can never match anyway. Filtering on this instead
# of a bare "nfl" substring matters: NFL-adjacent tickers like
# "KXNFLENDSTREAK" (a team playoff-drought market) contain "nfl" as a
# coincidental substring but aren't player props, and were being pulled in
# as false positives before this was tightened.
STAT_PHRASES = tuple(phrase for phrase, _ in STAT_KEYWORDS)


def fetch_kalshi_quotes(slate, stats_df):
    events = _fetch_open_events()
    print(f"Kalshi: fetched {len(events)} open events total")

    team_codes = set(slate["home_team"]) | set(slate["away_team"])
    opponent_of = {}
    for g in slate.itertuples():
        opponent_of[g.home_team] = g.away_team
        opponent_of[g.away_team] = g.home_team

    player_lookup = _build_player_lookup(stats_df, team_codes)
    print(f"Kalshi: matching against {len(player_lookup)} active players from this week's teams")

    candidate_titles = []
    quotes = []
    for event in events:
        for market in event.get("markets", []):
            title = market.get("title") or market.get("subtitle") or market.get("yes_sub_title") or ""
            lower_title = title.lower()
            if not any(phrase in lower_title for phrase in STAT_PHRASES):
                continue
            if len(candidate_titles) < 30:
                candidate_titles.append(title)

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

    print(f"Kalshi: {len(candidate_titles)} markets mention a tracked stat; sample titles: {candidate_titles[:10]}")
    print(f"Kalshi: matched {len(quotes)} player-prop quotes")
    return quotes


def _fetch_open_events():
    events = []
    cursor = None
    for _ in range(MAX_EVENT_PAGES):
        params = {
            "status": "open",
            "with_nested_markets": "true",
            "limit": EVENTS_PER_PAGE,
            "category": "Sports",
        }
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
    return events


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
    preferring the last traded price over a resting bid/ask quote. Kalshi
    returns these as dollar-denominated strings, e.g. "0.2500" for a
    market trading at 25 cents (25% implied), not raw integer cents."""
    for field in ("last_price_dollars", "previous_price_dollars", "yes_bid_dollars", "yes_ask_dollars"):
        value = market.get(field)
        if not value:
            continue
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price > 0:
            return max(0.01, min(0.99, price))
    return None
