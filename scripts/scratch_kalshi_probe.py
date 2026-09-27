"""Scratch probe: dump real Kalshi API shape for NFL passing-yards markets
to see why fetch_kalshi_quotes is producing thresholds/lines that don't
match what Kalshi's own UI shows. Deleted after use.
"""
import json

import requests

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"


def fetch_open_events():
    events = []
    cursor = None
    for _ in range(5):
        params = {
            "status": "open",
            "with_nested_markets": "true",
            "limit": 200,
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


def main():
    events = fetch_open_events()
    print(f"Fetched {len(events)} open Sports events")

    mahomes_events = [
        e for e in events if "mahomes" in json.dumps(e).lower() and "pass" in json.dumps(e).lower()
    ]
    print(f"Found {len(mahomes_events)} events mentioning mahomes+pass")

    for e in mahomes_events[:3]:
        print("=" * 80)
        print("EVENT title:", e.get("title"))
        print("EVENT ticker:", e.get("event_ticker"))
        print("EVENT keys:", sorted(e.keys()))
        markets = e.get("markets", [])
        print(f"  {len(markets)} nested markets")
        for m in markets[:15]:
            print("  ---")
            print("  market title:", m.get("title"))
            print("  market subtitle:", m.get("subtitle"))
            print("  market yes_sub_title:", m.get("yes_sub_title"))
            print("  market ticker:", m.get("ticker"))
            print("  market strike_type:", m.get("strike_type"))
            print("  market floor_strike:", m.get("floor_strike"))
            print("  market cap_strike:", m.get("cap_strike"))
            print("  market last_price_dollars:", m.get("last_price_dollars"))
            print("  market yes_bid_dollars:", m.get("yes_bid_dollars"))
            print("  market yes_ask_dollars:", m.get("yes_ask_dollars"))
            print("  market keys:", sorted(m.keys()))

    # Also: broader scan for any passing-yard market regardless of player,
    # to see the real threshold ladder / spacing Kalshi actually offers.
    print("=" * 80)
    print("Broader scan: any 'passing yard' market title/subtitle text")
    seen = 0
    for e in events:
        for m in e.get("markets", []):
            title = m.get("title") or m.get("subtitle") or m.get("yes_sub_title") or ""
            if "passing yard" in title.lower():
                print(
                    "  title=%r subtitle=%r yes_sub_title=%r floor_strike=%r cap_strike=%r"
                    % (
                        m.get("title"),
                        m.get("subtitle"),
                        m.get("yes_sub_title"),
                        m.get("floor_strike"),
                        m.get("cap_strike"),
                    )
                )
                seen += 1
                if seen >= 25:
                    break
        if seen >= 25:
            break
    print(f"Printed {seen} passing-yard markets")


if __name__ == "__main__":
    main()
