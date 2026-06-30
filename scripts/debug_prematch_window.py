#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.fixture_scanner import FixtureScanner

for h in (12, 24):
    fx = FixtureScanner(hours_ahead=h).scan()
    print(f"hours={h} found={len(fx)}")
    for f in fx[:10]:
        ko = (f.kickoff or "?")[:16]
        print(f"  {ko} {f.home} vs {f.away} ({f.league}) [{f.source}]")