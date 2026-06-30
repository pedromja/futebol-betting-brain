"""Testes — aprendizagem (greens/reds) e cooldown de resolução."""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from history.learning import build_learning_insights
from history.resolve_scheduler import (
    _STATE,
    mark_resolved,
    maybe_resolve_pending,
    should_resolve,
)
from history.tips_history import build_history_payload


def _write_log(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def test_build_learning_insights_hit_rates(tmp_path):
    log = tmp_path / "tips.jsonl"
    _write_log(
        log,
        [
            {"market": "Over 2.5", "league": "Liga A", "score": 0.72, "outcome": "win", "ev_pct": 10},
            {"market": "Over 2.5", "league": "Liga A", "score": 0.68, "outcome": "win", "ev_pct": 8},
            {"market": "Over 2.5", "league": "Liga A", "score": 0.50, "outcome": "loss", "ev_pct": 6},
            {"market": "BTTS Sim", "league": "Liga B", "score": 0.40, "outcome": "loss", "ev_pct": 5},
            {"market": "BTTS Sim", "league": "Liga B", "score": 0.38, "outcome": "loss", "ev_pct": 4},
            {"outcome": "pending"},
        ],
    )
    insights = build_learning_insights(log)
    assert insights["totals"]["win"] == 2
    assert insights["totals"]["loss"] == 3
    assert insights["totals"]["pending"] == 1
    assert insights["resolved"] == 5
    assert insights["hit_rate_pct"] == 40.0
    assert insights["by_market"][0]["market"] == "Over 2.5"
    assert insights["by_market"][0]["hit_rate_pct"] == round(100 * 2 / 3, 1)
    assert insights["auto_tune_active"] is False
    assert any("min_score" in s for s in insights["suggestions"])


def test_performance_uses_full_log_not_ui_limit(tmp_path):
    log = tmp_path / "tips.jsonl"
    rows = [
        {
            "logged_at": f"2026-06-30T{10 + i:02d}:00:00+00:00",
            "mode": "prematch",
            "home": f"H{i}",
            "away": f"A{i}",
            "market": "Over 2.5",
            "outcome": "win" if i % 2 == 0 else "loss",
            "pnl": 5.0 if i % 2 == 0 else -5.0,
            "stake_amount": 5.0,
        }
        for i in range(20)
    ]
    _write_log(log, rows)
    payload = build_history_payload(log, limit=5)
    assert len(payload["tips"]) == 5
    perf = payload["performance"]
    assert perf["total"] == 20
    assert perf["wins"] == 10
    assert perf["losses"] == 10
    assert perf["hit_rate_pct"] == 50.0


def test_should_resolve_respects_cooldown(tmp_path, monkeypatch):
    state = tmp_path / "last_resolve.json"
    monkeypatch.setattr("history.resolve_scheduler._STATE", state)
    assert should_resolve() is True
    mark_resolved(resolved_count=1)
    assert should_resolve(cooldown_sec=900) is False
    state.write_text(json.dumps({"at": time.time() - 901}), encoding="utf-8")
    assert should_resolve(cooldown_sec=900) is True


def test_maybe_resolve_pending_skips_within_cooldown(tmp_path, monkeypatch):
    state = tmp_path / "last_resolve.json"
    monkeypatch.setattr("history.resolve_scheduler._STATE", state)
    mark_resolved(resolved_count=0)
    called = {"n": 0}

    def _boom():
        called["n"] += 1
        raise AssertionError("resolve should not run")

    monkeypatch.setattr(
        "history.outcome_resolver.resolve_predictions",
        lambda *a, **k: _boom(),
    )
    assert maybe_resolve_pending() == 0
    assert called["n"] == 0


def test_fixture_id_from_hint_on_prematch_append(tmp_path):
    from history.predictions import append_scan_predictions

    class _Fx:
        home = "Benfica"
        away = "Porto"
        league = "Primeira Liga"
        kickoff = "2026-07-01T20:00:00Z"
        stage = ""
        espn_event_id = "760490"
        espn_league_code = "por.1"
        stats_hint = {"api_football_fixture_id": 123456}

    class _Best:
        odd = 2.1
        model_prob = 0.48

    class _Rec:
        best = _Best()

    class _Decision:
        recommendation = _Rec()

    class _Ranked:
        should_bet = True
        fixture = _Fx()
        decision = _Decision()
        best_market = "Over 2.5"
        best_ev = 0.08
        best_score = 0.62
        effective_min_score = 0.55
        kelly_stake = 5.0
        stake_plan = None

    class _Result:
        scanned_at = "2026-06-30T12:00:00"
        ranked = [_Ranked()]

    log = tmp_path / "tips.jsonl"
    assert append_scan_predictions(_Result(), log_path=log) == 1
    row = json.loads(log.read_text(encoding="utf-8").strip())
    assert row["fixture_id"] == 123456
    assert row["espn_event_id"] == "760490"
    assert row["espn_league_code"] == "por.1"


def test_default_resolve_cooldown_is_three_minutes():
    from history.resolve_scheduler import _DEFAULT_COOLDOWN_SEC

    assert _DEFAULT_COOLDOWN_SEC == 180