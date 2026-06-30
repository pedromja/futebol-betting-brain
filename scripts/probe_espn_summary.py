"""Probe ESPN summary API — list stat keys available."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.web_browser import WebBrowser

br = WebBrowser()
codes = ["fifa.world", "uefa.nations", "eng.1", "esp.1", "usa.1", "ger.1", "ita.1"]
found = None
for code in codes:
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard"
    data = br.fetch_json(url, cache_ns="probe_espn", cache_ttl=60)
    if not data:
        continue
    for ev in data.get("events") or []:
        st = (ev.get("competitions") or [{}])[0].get("status", {}).get("type", {})
        if st.get("state") == "in" or st.get("completed"):
            found = (code, str(ev.get("id")), ev.get("name", ""))
            break
    if found:
        break

if not found:
    print("No event found")
    sys.exit(0)

code, eid, name = found
print(f"Event: {name} ({code}/{eid})")
sum_url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/summary?event={eid}"
payload = br.fetch_json(sum_url, cache_ns="probe_espn_sum", cache_ttl=60)
if not payload:
    print("No summary")
    sys.exit(0)

teams = (payload.get("boxscore") or {}).get("teams") or []
for row in teams:
    side = row.get("homeAway")
    team = (row.get("team") or {}).get("displayName")
    print(f"\n=== {side} {team} ===")
    for item in row.get("statistics") or []:
        print(f"  {item.get('name')}: {item.get('displayValue')}")

# extra sections
for key in ("predictor", "plays", "format", "pickcenter"):
    if key in payload:
        print(f"\nTop-level key: {key}")

pred = payload.get("predictor") or {}
if pred:
    print("\nPredictor:", json.dumps(pred, indent=2)[:1200])

# search all keys for xg
blob = json.dumps(payload).lower()
for token in ("expected", "xg", "bigchance", "big chance", "duel"):
    if token in blob:
        print(f"Found token in payload: {token}")