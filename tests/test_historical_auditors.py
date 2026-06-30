"""Testes — perfis históricos e auditores fecho/estilo."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prematch.historical.aggregate import aggregate_csv_rows
from prematch.historical.auditors import audit_market_closing, audit_style_profile
from prematch.historical.names import canonical_team
from prematch.historical.store import HistoricalStore
from prematch.historical.types import TeamHistoricalProfile, VenueSlice


def _sample_rows():
    return [
        {
            "HomeTeam": "Benfica",
            "AwayTeam": "Sp Lisbon",
            "FTHG": "2",
            "FTAG": "1",
            "HS": "15",
            "AS": "10",
            "HST": "6",
            "AST": "3",
            "HC": "7",
            "AC": "4",
            "HF": "12",
            "AF": "14",
            "B365CH": "1.55",
            "B365CA": "5.50",
            "B365C>2.5": "1.70",
        },
        {
            "HomeTeam": "Sp Lisbon",
            "AwayTeam": "Benfica",
            "FTHG": "1",
            "FTAG": "1",
            "HS": "14",
            "AS": "13",
            "HST": "5",
            "AST": "4",
            "HC": "6",
            "AC": "5",
            "HF": "11",
            "AF": "10",
            "B365CH": "2.40",
            "B365CA": "2.90",
            "B365C>2.5": "1.65",
        },
    ]


def test_canonical_team_csv_names():
    assert canonical_team("Sp Lisbon") == "Sporting"
    assert canonical_team("Sp Braga") == "SC Braga"
    assert canonical_team("Porto") == "FC Porto"


def test_aggregate_builds_profiles():
    profiles = aggregate_csv_rows(_sample_rows(), league_code="PPL", season="2526")
    by_name = {p.team: p for p in profiles}
    assert "Benfica" in by_name
    assert "Sporting" in by_name
    assert by_name["Benfica"].home.closing_win_odd_avg == 1.55
    assert by_name["Sporting"].home.shots_avg == 14.0


def test_market_closing_value_vote():
    store = HistoricalStore()
    store._index = {
        "Benfica": TeamHistoricalProfile(
            team="Benfica",
            league="PPL",
            season="2526",
            home=VenueSlice(matches=10, closing_win_odd_avg=1.50),
        )
    }
    import prematch.historical.auditors as aud

    old = aud.get_store
    aud.get_store = lambda: store
    try:
        vote, payload = audit_market_closing(
            "Benfica",
            "Sporting",
            bet_side="home",
            odds_hint={"home_win": 1.65},
            league="Primeira Liga",
        )
    finally:
        aud.get_store = old
    assert vote is not None
    assert vote.auditor_id == "market_closing"
    assert payload["delta_pct"] > 4


def test_style_profile_over():
    store = HistoricalStore()
    store._index = {
        "Benfica": TeamHistoricalProfile(
            team="Benfica",
            league="PPL",
            season="2526",
            home=VenueSlice(matches=10, shots_avg=14, sot_avg=5),
            goals_total_avg=2.8,
        ),
        "Sporting": TeamHistoricalProfile(
            team="Sporting",
            league="PPL",
            season="2526",
            away=VenueSlice(matches=10, shots_avg=13, sot_avg=4.5),
            goals_total_avg=2.7,
        ),
    }
    import prematch.historical.auditors as aud

    aud.get_store = lambda: store
    vote = audit_style_profile("Benfica", "Sporting", bet_side="over", league="Primeira Liga")
    assert vote is not None
    assert vote.market_side == "over"