import json
import os

import pandas as pd
import requests

API_KEY = os.environ["ODDS_API_KEY"]
BASE = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"

resp = requests.get(f"{BASE}/sports/{SPORT}/events", params={"apiKey": API_KEY}, timeout=30)
resp.raise_for_status()
events = resp.json()
print(f"{len(events)} upcoming events")
if not events:
    raise SystemExit("no events to test against")

event = events[0]
print("Testing against:", event["home_team"], "vs", event["away_team"], event["id"])

candidate_markets = ["spreads", "totals", "spreads_h1", "totals_h1", "spreads_h2", "totals_h2", "h2h"]
r = requests.get(
    f"{BASE}/sports/{SPORT}/events/{event['id']}/odds",
    params={
        "apiKey": API_KEY,
        "bookmakers": "draftkings,fanduel",
        "markets": ",".join(candidate_markets),
        "oddsFormat": "american",
    },
    timeout=30,
)
print("HTTP", r.status_code)
print("remaining credits header:", r.headers.get("x-requests-remaining"))
if r.status_code != 200:
    print(r.text[:1000])
    raise SystemExit(1)

payload = r.json()
found_markets = set()
for bm in payload.get("bookmakers", []):
    for m in bm.get("markets", []):
        found_markets.add(m["key"])
        if m["key"] in ("spreads_h1", "totals_h1", "spreads_h2", "totals_h2"):
            print(f"  {bm['key']} / {m['key']}:", json.dumps(m["outcomes"], indent=2)[:500])

print("Markets actually returned:", sorted(found_markets))
print("Missing from request:", sorted(set(candidate_markets) - found_markets))
