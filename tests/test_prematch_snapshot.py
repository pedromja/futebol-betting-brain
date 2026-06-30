"""Testes — snapshot pré-jogo para IA live."""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.fixture_types import UpcomingFixture
from ia import prematch_snapshot as snap


@dataclass
class _FakeMarket:
    label: str
    total_score: float
    expected_value: float
    odd: float


@dataclass
class _FakeRec:
    best_market: _FakeMarket
    all_markets: list = field(default_factory=list)


@dataclass
class _FakeDecision:
    recommendation: _FakeRec


@dataclass
class _FakeStake:
    level: int = 5
    label: str = "Moderada"
    bankroll_pct: float = 2.5
    suggested_amount: float | None = 25.0


@dataclass
class _FakeRanked:
    fixture: UpcomingFixture
    decision: _FakeDecision
    best_ev: float
    best_market: str
    best_score: float
    should_bet: bool
    rank: int = 1
    effective_min_score: float = 0.55
    stake_plan: _FakeStake | None = None
    transfermarkt: dict | None = None
    motivation: dict | None = None
    competition_progress: dict | None = None
    block_reason: str | None = None


@dataclass
class _FakeScan:
    scanned_at: str
    ranked: list


def test_build_snapshot_from_ranked(tmp_path, monkeypatch):
    monkeypatch.setattr(snap, "IA_PREMATCH_SNAPSHOTS", tmp_path / "snaps.jsonl")

    fixture = UpcomingFixture(
        home="Ivory Coast",
        away="Norway",
        league="FIFA World Cup",
        kickoff="2026-06-30T17:00:00Z",
        source="espn_web",
        espn_event_id="760490",
        espn_league_code="fifa.world",
        odds_hint={"home_odd": 2.4, "away_odd": 1.9},
    )
    market = _FakeMarket("Norway vitória", 0.72, 0.11, 1.95)
    ranked = _FakeRanked(
        fixture=fixture,
        decision=_FakeDecision(_FakeRec(market, [market])),
        best_ev=0.11,
        best_market="Norway vitória",
        best_score=0.72,
        should_bet=True,
        stake_plan=_FakeStake(),
        motivation={"should_bet": True, "score": 0.8},
    )
    result = _FakeScan(scanned_at="2026-06-30T12:00:00", ranked=[ranked])

    n = snap.save_snapshots_from_scan(result)
    assert n == 1

    loaded = snap.load_snapshot_by_espn_event("760490")
    assert loaded is not None
    assert loaded["home"] == "Ivory Coast"
    assert loaded["espn_league_code"] == "fifa.world"
    assert loaded["prematch_assumptions"]["favorite_side"] == "away"
    assert loaded["best_market"] == "Norway vitória"

    rows = json.loads((tmp_path / "snaps.jsonl").read_text(encoding="utf-8").strip())
    assert rows["match_key"] == "espn:760490"


def test_infer_favorite_espn_odds_keys():
    from ia.prematch_snapshot import _infer_favorite

    assert _infer_favorite({"home_win": 1.29, "away_win": 10.0}) == "home"
    assert _infer_favorite({"home_win": 4.0, "away_win": 1.8}) == "away"


def test_ensure_snapshot_live_fallback(tmp_path, monkeypatch):
    from discovery.live_fixture_types import LiveFixture

    monkeypatch.setattr(snap, "IA_PREMATCH_SNAPSHOTS", tmp_path / "snaps.jsonl")
    fx = LiveFixture(
        home="France",
        away="Sweden",
        league="FIFA World Cup",
        home_score=1,
        away_score=0,
        minute=50,
        status_short="2H",
        espn_event_id="760492",
        espn_league_code="fifa.world",
        odds_hint={"home_win": 1.3, "away_win": 9.5},
    )
    loaded = snap.ensure_snapshot_for_live(fx)
    assert loaded is not None
    assert loaded["source"] == "live_fallback"
    assert loaded["prematch_assumptions"]["favorite_name"] == "France"
    again = snap.ensure_snapshot_for_live(fx)
    assert again["espn_event_id"] == "760492"