"""Testes — auto-tune de min_score com base em greens/reds."""

import json
import sys
from datetime import datetime, timedelta, timezone
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
from history.learning import build_learning_insights, build_tune_dataset


def _write_log(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def _weak_market_rows(n: int = 8) -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        {
            "logged_at": (now - timedelta(days=i)).isoformat(),
            "market": "BTTS Sim",
            "league": "Liga X",
            "mode": "prematch",
            "score": 0.62,
            "outcome": "loss",
            "ev_pct": 5,
            "pnl": -5.0,
            "stake_amount": 5.0,
        }
        for i in range(n)
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
        "hit_rate_pct": 20.0,
        "by_market": [
            {
                "market": "BTTS Sim",
                "wins": 1,
                "losses": 4,
                "hit_rate_pct": 20.0,
                "weighted_wins": 1,
                "weighted_losses": 4,
            },
        ],
        "by_league": [],
        "by_mode": [],
        "by_combo": [],
        "by_score_bucket": [],
        "ev_calibration": {},
        "recent": {},
    }
    state = compute_tune_state(insights)
    assert state.active is True
    assert state.market_deltas.get("BTTS Sim", 0) > 0.04
    assert any("BTTS Sim" in a for a in state.adjustments)


def test_strong_market_lowers_min_score():
    insights = {
        "resolved": 10,
        "hit_rate_pct": 80.0,
        "by_market": [
            {"market": "Over 2.5", "wins": 5, "losses": 1, "hit_rate_pct": 83.3},
        ],
        "by_league": [],
        "by_mode": [],
        "by_combo": [],
        "by_score_bucket": [],
        "ev_calibration": {},
        "recent": {},
    }
    state = compute_tune_state(insights)
    assert state.market_deltas.get("Over 2.5") == -0.02


def test_weak_league_raises_min_score():
    insights = {
        "resolved": 10,
        "hit_rate_pct": 20.0,
        "by_market": [],
        "by_league": [
            {
                "league": "Segunda Liga",
                "wins": 1,
                "losses": 4,
                "hit_rate_pct": 20.0,
                "weighted_wins": 1,
                "weighted_losses": 4,
            },
        ],
        "by_mode": [],
        "by_combo": [],
        "by_score_bucket": [],
        "ev_calibration": {},
        "recent": {},
    }
    state = compute_tune_state(insights)
    assert state.league_deltas.get("Segunda Liga", 0) > 0.02


def test_weak_mode_raises_min_score():
    insights = {
        "resolved": 12,
        "hit_rate_pct": 30.0,
        "by_market": [],
        "by_league": [],
        "by_mode": [
            {
                "mode": "live",
                "wins": 2,
                "losses": 6,
                "hit_rate_pct": 25.0,
                "weighted_wins": 2,
                "weighted_losses": 6,
            },
        ],
        "by_combo": [],
        "by_score_bucket": [],
        "ev_calibration": {},
        "recent": {},
    }
    state = compute_tune_state(insights)
    assert state.mode_deltas.get("live", 0) > 0.02


def test_weak_combo_raises_min_score():
    insights = {
        "resolved": 10,
        "hit_rate_pct": 20.0,
        "by_market": [],
        "by_league": [],
        "by_mode": [],
        "by_combo": [
            {
                "combo": "BTTS Sim|Liga X",
                "wins": 0,
                "losses": 4,
                "hit_rate_pct": 0.0,
                "weighted_wins": 0,
                "weighted_losses": 4,
            },
        ],
        "by_score_bucket": [],
        "ev_calibration": {},
        "recent": {},
    }
    state = compute_tune_state(insights)
    assert state.combo_deltas.get("BTTS Sim|Liga X", 0) > 0.03


def test_ev_overconfidence_bumps_base():
    insights = {
        "resolved": 12,
        "hit_rate_pct": 40.0,
        "by_market": [],
        "by_league": [],
        "by_mode": [],
        "by_combo": [],
        "by_score_bucket": [],
        "ev_calibration": {"gap_pct": 6.0, "avg_ev_win_pct": 6.0, "avg_ev_loss_pct": 12.0},
        "recent": {},
    }
    state = compute_tune_state(insights)
    assert state.base_delta >= 0.03
    assert any("EV" in a for a in state.adjustments)


def test_low_score_bucket_bumps_base_delta():
    insights = {
        "resolved": 10,
        "hit_rate_pct": 14.0,
        "by_market": [],
        "by_league": [],
        "by_mode": [],
        "by_combo": [],
        "by_score_bucket": [
            {"bucket": "low", "wins": 1, "losses": 6, "hit_rate_pct": 14.3},
        ],
        "ev_calibration": {},
        "recent": {},
    }
    state = compute_tune_state(insights)
    assert state.base_delta == 0.04


def test_tuned_min_score_applies_deltas():
    state = LearningTuneState(
        active=True,
        base_delta=0.04,
        market_deltas={"BTTS Sim": 0.05},
        league_deltas={"Liga X": 0.03},
        mode_deltas={"prematch": 0.02},
        combo_deltas={"BTTS Sim|Liga X": 0.04},
    )
    assert tuned_min_score(0.55, "BTTS Sim", "Liga X", "prematch", state=state) == 0.73


def test_tuned_min_score_clamps_bounds():
    state = LearningTuneState(
        active=True,
        base_delta=0.08,
        market_deltas={"Over 2.5": 0.10},
        league_deltas={"Liga": 0.06},
    )
    assert tuned_min_score(0.80, "Over 2.5", "Liga", "prematch", state=state) == 0.88
    state2 = LearningTuneState(active=True, base_delta=-0.20)
    assert tuned_min_score(0.52, "X", state=state2) == 0.50


def test_save_and_load_tune_state(tmp_path):
    state = LearningTuneState(
        active=True,
        resolved=12,
        base_delta=0.04,
        market_deltas={"BTTS Sim": 0.05},
        mode_deltas={"live": 0.03},
        combo_deltas={"BTTS Sim|Liga X": 0.04},
        adjustments=["BTTS Sim: 20% → +0.05 min_score"],
        reason="1 ajuste(s) activos",
    )
    path = tmp_path / "learning_tune.json"
    save_tune_state(state, path=path)
    loaded = load_tune_state(path=path)
    assert loaded is not None
    assert loaded.active is True
    assert loaded.mode_deltas.get("live") == 0.03
    assert loaded.combo_deltas.get("BTTS Sim|Liga X") == 0.04


def test_build_tune_dataset_weighted_recent(tmp_path):
    now = datetime.now(timezone.utc)
    log = tmp_path / "tips.jsonl"
    rows = [
        {
            "logged_at": now.isoformat(),
            "market": "Over 2.5",
            "league": "Liga A",
            "mode": "prematch",
            "score": 0.7,
            "outcome": "win",
            "ev_pct": 8,
            "pnl": 5.0,
            "stake_amount": 5.0,
        },
        {
            "logged_at": (now - timedelta(days=120)).isoformat(),
            "market": "Over 2.5",
            "league": "Liga A",
            "mode": "prematch",
            "score": 0.7,
            "outcome": "loss",
            "ev_pct": 8,
            "pnl": -5.0,
            "stake_amount": 5.0,
        },
    ]
    _write_log(log, rows)
    data = build_tune_dataset(log)
    assert data["resolved"] == 2
    assert data["recent"]["hit_rate_pct"] is not None
    assert data["recent"]["hit_rate_pct"] > 50


def test_build_learning_insights_includes_auto_tune(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_TUNE", "1")
    log = tmp_path / "tips.jsonl"
    _write_log(log, _weak_market_rows(10))
    insights = build_learning_insights(log)
    assert insights["auto_tune"]["active"] is True
    assert insights["auto_tune"]["market_deltas"].get("BTTS Sim", 0) > 0
    assert insights["auto_tune_active"] is True
    assert insights.get("ev_gap_pct") is not None or insights.get("recent")


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