"""Testes — merge conservador ESPN vs casas de nicho."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from odds.conservative_merge import (
    less_favorable_odd,
    merge_conservative_odds,
    public_odds_compare,
    public_odds_hint,
)


def test_less_favorable_picks_lower_decimal():
    used, picked = less_favorable_odd(2.05, 1.92)
    assert used == 1.92
    assert picked == "niche"


def test_merge_uses_worst_per_market():
    espn = {
        "home_win": 1.35,
        "draw": 5.0,
        "away_win": 9.0,
        "over_25": 2.05,
        "under_25": 1.77,
    }
    niche = {
        "home_win": 1.30,
        "draw": 5.2,
        "away_win": 8.5,
        "over_25": 2.10,
        "under_25": 1.72,
    }
    merged = merge_conservative_odds(espn, niche, niche_book="onexbet")

    assert merged["home_win"] == 1.30
    assert merged["draw"] == 5.0
    assert merged["away_win"] == 8.5
    assert merged["over_25"] == 2.05
    assert merged["under_25"] == 1.72
    assert merged["_odds_enriched"] is True

    compare = merged["_odds_compare"]["over_25"]
    assert compare["espn"] == 2.05
    assert compare["niche"] == 2.10
    assert compare["used"] == 2.05
    assert compare["picked"] == "espn"


def test_public_odds_hint_strips_internal():
    merged = merge_conservative_odds({"home_win": 1.5}, {"home_win": 1.4}, niche_book="onexbet")
    pub = public_odds_hint(merged)
    assert "_odds_compare" not in pub
    assert pub["home_win"] == 1.4


def test_public_odds_compare_summary():
    merged = merge_conservative_odds(
        {"over_25": 2.0},
        {"over_25": 1.85},
        niche_book="onexbet",
    )
    summary = public_odds_compare(merged)
    assert summary["niche_book"] == "onexbet"
    assert summary["markets"]["over_25"]["used"] == 1.85