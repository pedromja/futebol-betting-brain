"""Testes — auto-tune de min_score com base em greens/reds."""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from history.auto_tune import (
    LearningTuneState,
    compute_tune_state,
    load_tune_state,
    refresh_tune_state,
    save_tune_state,
    tuned_min_score,
)
from history.learning import build_learning_insights


def _write_log(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def _weak_market_rows(n: int = 8) -> list[dict]:
    """Gera tips com mercado fraco (0 wins, n losses) para activar penalty."""
    return [
        {
            "market": "BTTS Sim",
            "league": "Liga X",
            "score": 0.62,
            "outcome": "loss",
            "ev_pct": 5,
        }
        for _ in range(n)
    ]


def test_compute_tune_inactive_below_min_resolved():
    state = compute_tune_state({"resolved": 5, "by_market": [], "by_league": [], "by_score_bucket": []})
    assert state.active is False
    assert "insuficientes" in state.reason.lower()


def test_compute_tune_disabled_via_env(monkeypatch):
    monkeypatch.setenv("AUTO_TUNE", "0")
    state = compute_tune_state({"resolved": 20, "by_market": [], "by_league": [], "by_score_bucket": []})
    assert state.active is False
    assert "desactivado" in state.reason.lower()


def test_weak_market_raises_min_score():
    insights = {
        "resolved": 10,
        "by_market": [
            {"market": "BTTS Sim", "wins": 1, "losses": 4, "hit_rate_pct": 20.0},
        ],
        "by_league": [],
        "by_score_bucket": [],
    }
    state = compute_tune_state(insights)
    assert state.active is True
    assert state.market_deltas.get("BTTS Sim") == 0.05
    assert any("BTTS Sim" in a for a in state.adjustments)


def test_strong_market_lowers_min_score():
    insights = {
        "resolved": 10,
        "by_market": [
            {"market": "Over 2.5", "wins": 5, "losses": 1, "hit_rate_pct": 83.3},
        ],
        "by_league": [],
        "by_score_bucket": [],
    }
    state = compute_tune_state(insights)
    assert state.market_deltas.get("Over 2.5") == -0.02


def test_weak_league_raises_min_score():
    insights = {
        "resolved": 10,
        "by_market": [],
        "by_league": [
            {"league": "Segunda Liga", "wins": 1, "losses": 4, "hit_rate_pct": 20.0},
        ],
        "by_score_bucket": [],
    }
    state = compute_tune_state(insights)
    assert state.league_deltas.get("Segunda Liga") == 0.03


def test_low_score_bucket_bumps_base_delta():
    insights = {
        "resolved": 10,
        "by_market": [],
        "by_league": [],
        "by_score_bucket": [
            {"bucket": "low", "wins": 1, "losses": 6, "hit_rate_pct": 14.3},
        ],
    }
    state = compute_tune_state(insights)
    assert state.base_delta == 0.04


def test_tuned_min_score_applies_deltas():
    state = LearningTuneState(
        active=True,
        base_delta=0.04,
        market_deltas={"BTTS Sim": 0.05},
        league_deltas={"Liga X": 0.03},
    )
    assert tuned_min_score(0.55, "BTTS Sim", "Liga X", state=state) == 0.67


def test_tuned_min_score_clamps_bounds():
    state = LearningTuneState(
        active=True,
        base_delta=0.08,
        market_deltas={"Over 2.5": 0.10},
        league_deltas={"Liga": 0.06},
    )
    assert tuned_min_score(0.80, "Over 2.5", "Liga", state=state) == 0.88
    state2 = LearningTuneState(active=True, base_delta=-0.20)
    assert tuned_min_score(0.52, "X", state=state2) == 0.50


def test_save_and_load_tune_state(tmp_path):
    state = LearningTuneState(
        active=True,
        resolved=12,
        base_delta=0.04,
        market_deltas={"BTTS Sim": 0.05},
        adjustments=["BTTS Sim: 20% → +0.05 min_score"],
        reason="1 ajuste(s) activos",
    )
    path = tmp_path / "learning_tune.json"
    save_tune_state(state, path=path)
    loaded = load_tune_state(path=path)
    assert loaded is not None
    assert loaded.active is True
    assert loaded.base_delta == 0.04
    assert loaded.market_deltas["BTTS Sim"] == 0.05


def test_build_learning_insights_includes_auto_tune(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_TUNE", "1")
    log = tmp_path / "tips.jsonl"
    _write_log(log, _weak_market_rows(10))
    insights = build_learning_insights(log)
    assert insights["auto_tune"]["active"] is True
    assert insights["auto_tune"]["market_deltas"].get("BTTS Sim") == 0.05
    assert insights["auto_tune_active"] is True


def test_refresh_tune_state_persists_when_active(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_TUNE", "1")
    import history.auto_tune as auto_tune_mod

    log = tmp_path / "tips.jsonl"
    tune_file = tmp_path / "learning_tune.json"
    monkeypatch.setattr(auto_tune_mod, "TUNE_FILE", tune_file)
    _write_log(log, _weak_market_rows(10))

    auto_tune_mod._cache = None
    auto_tune_mod._cache_at = 0.0
    auto_tune_mod._cache_mtime = 0.0

    state = refresh_tune_state(log_path=log, force=True)
    assert state.active is True
    assert tune_file.exists()
    assert load_tune_state(path=tune_file) is not None