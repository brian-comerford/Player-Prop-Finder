import json
import os

import pandas as pd
import requests

RAW_DIR = "/tmp/espn_probe_raw"
os.makedirs(RAW_DIR, exist_ok=True)

SEASON = 2026
WEEK = 3

CROSSWALK_URL = "https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv"
ESPN_URL = (
    f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/players"
    f"?view=kona_player_info&scoringPeriodId={WEEK}"
)

ESPN_STAT_IDS = {
    3: "pass_yd", 4: "pass_td",
    24: "rush_yd", 25: "rush_td",
    41: "rec", 42: "rec_yd", 43: "rec_td",
}

print("== downloading crosswalk ==")
cw_path = os.path.join(RAW_DIR, "crosswalk.csv")
r = requests.get(CROSSWALK_URL, timeout=60)
r.raise_for_status()
with open(cw_path, "wb") as f:
    f.write(r.content)
crosswalk = pd.read_csv(cw_path, low_memory=False, usecols=["name", "position", "gsis_id", "espn_id"])
crosswalk = crosswalk.dropna(subset=["gsis_id", "espn_id"])
espn_to_gsis = {str(int(row["espn_id"])): row["gsis_id"] for _, row in crosswalk.iterrows()}
name_by_gsis = {row["gsis_id"]: row["name"] for _, row in crosswalk.iterrows()}
print(f"crosswalk rows with both ids: {len(espn_to_gsis)}")

print("== downloading ESPN players endpoint ==")
resp = requests.get(
    ESPN_URL,
    headers={"x-fantasy-filter": json.dumps({"players": {"filterActive": {"value": True}}})},
    timeout=180,
)
print("HTTP", resp.status_code)
print("bytes:", len(resp.content))
data = resp.json()
print("top-level type:", type(data))
if isinstance(data, dict):
    print("top-level keys:", list(data.keys())[:20])
    espn_players = data.get("players", data)
else:
    espn_players = data
print("num player entries:", len(espn_players))
print("sample entry keys:", list(espn_players[0].keys())[:30] if espn_players else None)

projections = {}
matched = 0
for player in espn_players:
    pid = player.get("id")
    gsis_id = espn_to_gsis.get(str(pid))
    if gsis_id is None:
        continue
    matched += 1
    stats_list = player.get("stats", [])
    entry = next(
        (
            s for s in stats_list
            if s.get("scoringPeriodId") == WEEK and s.get("seasonId") == SEASON
            and s.get("statSourceId") == 1 and s.get("statSplitTypeId") == 1
        ),
        None,
    )
    if entry is None or not entry.get("stats"):
        continue
    stats = {
        name: entry["stats"][str(sid)]
        for sid, name in ESPN_STAT_IDS.items()
        if str(sid) in entry["stats"]
    }
    if stats:
        projections[gsis_id] = stats

print(f"matched by espn_id crosswalk: {matched}")
print(f"players with a usable week-{WEEK} projection entry: {len(projections)}")
print("--- sample projections ---")
for gsis_id, stats in list(projections.items())[:10]:
    print(name_by_gsis.get(gsis_id, gsis_id), stats)

print("--- looking for specific known players by name ---")
for target in ["Josh Allen", "Justin Jefferson", "Ja'Marr Chase", "Christian McCaffrey"]:
    hit = [gsis_id for gsis_id, nm in name_by_gsis.items() if nm == target]
    for gsis_id in hit:
        print(target, "gsis_id=", gsis_id, "->", projections.get(gsis_id, "NO PROJECTION FOUND"))
