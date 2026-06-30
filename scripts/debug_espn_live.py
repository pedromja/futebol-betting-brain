#!/usr/bin/env python3
import json
import urllib.request
from datetime import datetime, timezone

codes = [
    "fifa.world", "fifa.cwc", "eng.1", "esp.1", "ita.1", "ger.1", "fra.1", "por.1",
    "uefa.champions", "uefa.europa", "usa.1", "mex.1", "bra.1", "arg.1",
]
live = []
for code in codes:
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.loads(r.read().decode())
    except Exception:
        continue
    for ev in data.get("events") or []:
        st = (ev.get("status") or {}).get("type") or {}
        if st.get("state") != "in":
            continue
        comp = ev.get("competitions", [{}])[0]
        teams = {}
        for c in comp.get("competitors", []):
            teams[c.get("homeAway")] = c.get("team", {}).get("displayName", "?")
        live.append((code, teams.get("home","?"), teams.get("away","?"), ev.get("name","")))

print("espn_live_count:", len(live))
for row in live:
    print(" ", row)