#!/usr/bin/env python3
"""Debug: resposta bruta API-Football live=all vs filtro interno."""

import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.env import load_dotenv
from discovery.api_football_client import ApiFootballClient, _LIVE_ACTIVE

load_dotenv(ROOT / ".env")

key = os.getenv("API_FOOTBALL_KEY", "")
if not key:
    print("API_FOOTBALL_KEY missing")
    sys.exit(1)

req = urllib.request.Request(
    "https://v3.football.api-sports.io/fixtures?live=all",
    headers={"x-apisports-key": key},
)
with urllib.request.urlopen(req, timeout=25) as r:
    data = json.loads(r.read().decode())

print("errors:", data.get("errors"))
raw = data.get("response") or []
print("total_raw:", len(raw))

client = ApiFootballClient()
filtered = client.scan_live()
print("total_filtered:", len(filtered))
print("LIVE_ACTIVE:", sorted(_LIVE_ACTIVE))

for item in raw:
    fix = item.get("fixture") or {}
    status = fix.get("status") or {}
    short = str(status.get("short") or "").upper()
    teams = item.get("teams") or {}
    h = (teams.get("home") or {}).get("name", "?")
    a = (teams.get("away") or {}).get("name", "?")
    lg = (item.get("league") or {}).get("name", "?")
    kept = "KEEP" if short in _LIVE_ACTIVE else "DROP"
    print(f"  [{kept}] {short} {status.get('elapsed')}' {h} vs {a} | {lg}")