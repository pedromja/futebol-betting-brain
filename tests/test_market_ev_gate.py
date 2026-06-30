"""Testes — gate EV IA vs odds ESPN."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ia.market_ev_gate import apply_ev_gate, resolve_book_odd


def _odds():
    return {
        "home_win": 1.35,
        "draw": 5.0,
        "away_win": 9.0,
        "over_25": 2.05,
        "under_25": 1.77,
        "btts_yes": 1.86,
        "btts_no": 1.74,
    }


def test_resolve_over25_book_odd():
    r = resolve_book_odd("Over 2.5", _odds(), home_score=1, away_score=0, minute=50)
    assert r["odd"] is not None
    assert r["odd"] < 2.05
    assert "espn" in r["source"]


def test_reject_over15_when_already_two_goals():
    r = resolve_book_odd("Over 1.5", _odds(), home_score=2, away_score=0, minute=40)
    assert r["odd"] is None
    assert r["reject_reason"] == "linha_ja_bateu"


def test_apply_ev_gate_accepts_value_tip():
    tip = {
        "market": "Over 2.5",
        "confidence_pct": 72,
        "prematch_alignment": "convergent",
    }
    out, reason = apply_ev_gate(
        tip, _odds(), home_score=1, away_score=0, minute=50, min_ev=0.02
    )
    assert reason is None
    assert out is not None
    assert out["book_odd"] >= 1.5
    assert out["ev_pct"] is not None


def test_apply_ev_gate_rejects_low_confidence():
    tip = {
        "market": "Over 2.5",
        "confidence_pct": 35,
        "prematch_alignment": "neutral",
    }
    out, reason = apply_ev_gate(
        tip, _odds(), home_score=1, away_score=0, minute=50, min_ev=0.04
    )
    assert out is None
    assert reason and "ev_baixo" in reason


def test_apply_ev_gate_rejects_unmapped_market():
    tip = {"market": "Cantos Over", "confidence_pct": 80}
    out, reason = apply_ev_gate(tip, _odds(), home_score=0, away_score=0, minute=20)
    assert out is None
    assert reason == "mercado_sem_mapeamento_odd"