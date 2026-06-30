"""Testes — auditoria IA, restrições e gate."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.evaluator import evaluate_bots_for_scan
from bots.ia_audit import (
    build_ia_audit_dataset,
    check_ia_blocked,
    is_ia_bot,
    refresh_ia_audit,
)
from bots.ia_gate import apply_ia_gate_to_hits
from bots.types import BotConfig
from tests.test_history_resolve import _write_log


def _ia_signals_log(path: Path) -> None:
    rows = [
        {
            "logged_at": "2026-06-28T20:00:00+00:00",
            "bot_id": "ia1",
            "bot_name": "IA — Padrão vs live",
            "template": "live_pattern_discrepancy",
            "mode": "live",
            "home": "Benfica",
            "away": "Porto",
            "market": "Cantos Over",
            "odd": 1.9,
            "ev_pct": 6,
            "outcome": "loss",
            "pnl": -5,
            "stake_amount": 5,
            "ia_context": {
                "scenario_id": "fav_push_post_ht",
                "pattern_window": "post_ht_0_15",
                "pattern_source": "situation",
            },
        },
        {
            "logged_at": "2026-06-28T19:00:00+00:00",
            "bot_id": "ia1",
            "bot_name": "IA — Padrão vs live",
            "template": "live_pattern_discrepancy",
            "mode": "live",
            "home": "Sporting",
            "away": "Braga",
            "market": "Over 1.5",
            "odd": 1.85,
            "ev_pct": 5,
            "outcome": "loss",
            "pnl": -5,
            "stake_amount": 5,
            "ia_context": {"scenario_id": "fav_push_post_ht", "pattern_window": "post_ht_0_15"},
        },
        {
            "logged_at": "2026-06-28T18:00:00+00:00",
            "bot_id": "ia1",
            "bot_name": "IA — Padrão vs live",
            "template": "live_pattern_discrepancy",
            "mode": "live",
            "home": "A",
            "away": "B",
            "market": "Over 2.5",
            "odd": 2.0,
            "ev_pct": 7,
            "outcome": "loss",
            "pnl": -5,
            "stake_amount": 5,
        },
        {
            "logged_at": "2026-06-28T17:00:00+00:00",
            "bot_id": "ia1",
            "bot_name": "IA — Padrão vs live",
            "template": "live_pattern_discrepancy",
            "mode": "live",
            "home": "C",
            "away": "D",
            "market": "Over 2.5",
            "odd": 2.0,
            "ev_pct": 7,
            "outcome": "loss",
            "pnl": -5,
            "stake_amount": 5,
        },
        {
            "logged_at": "2026-06-28T16:00:00+00:00",
            "bot_id": "ia1",
            "bot_name": "IA — Padrão vs live",
            "template": "live_pattern_discrepancy",
            "mode": "live",
            "home": "E",
            "away": "F",
            "market": "Over 2.5",
            "odd": 2.0,
            "ev_pct": 7,
            "outcome": "loss",
            "pnl": -5,
            "stake_amount": 5,
        },
        {
            "logged_at": "2026-06-28T15:00:00+00:00",
            "bot_id": "ia1",
            "bot_name": "IA — Padrão vs live",
            "template": "live_pattern_discrepancy",
            "mode": "live",
            "home": "G",
            "away": "H",
            "market": "Over 2.5",
            "odd": 2.0,
            "ev_pct": 7,
            "outcome": "win",
            "pnl": 5,
            "stake_amount": 5,
        },
    ]
    _write_log(path, rows)


def test_is_ia_bot():
    assert is_ia_bot("live_pattern_discrepancy")
    assert is_ia_bot(None, "IA — EV cenário")
    assert not is_ia_bot("prematch_over")


def test_audit_restricts_weak_template(tmp_path, monkeypatch):
    log = tmp_path / "bot_signals.jsonl"
    audit_file = tmp_path / "ia_audit.json"
    _ia_signals_log(log)

    monkeypatch.setattr("bots.ia_audit.BOT_SIGNALS_LOG", log)
    monkeypatch.setattr("bots.ia_audit.IA_AUDIT_FILE", audit_file)

    state = refresh_ia_audit(log_path=log)
    assert state.resolved_ia == 6
    blocked_keys = {r["key"] for r in state.restrictions if r.get("blocked")}
    assert "template:live_pattern_discrepancy" in blocked_keys

    match = {"scenario_id": "fav_push_post_ht", "pattern_window": "post_ht_0_15"}
    hit, reason = check_ia_blocked(template="live_pattern_discrepancy", match=match, audit=state)
    assert hit is True
    assert "fraco" in reason.lower() or "hit rate" in reason.lower()


def test_ia_gate_filters_hits(tmp_path, monkeypatch):
    log = tmp_path / "bot_signals.jsonl"
    audit_file = tmp_path / "ia_audit.json"
    _ia_signals_log(log)
    monkeypatch.setattr("bots.ia_audit.BOT_SIGNALS_LOG", log)
    monkeypatch.setattr("bots.ia_audit.IA_AUDIT_FILE", audit_file)
    state = refresh_ia_audit(log_path=log)

    hits = [
        {
            "bot_id": "ia1",
            "bot_name": "IA — Padrão",
            "template": "live_pattern_discrepancy",
            "mode": "live",
            "notify": True,
            "matches": [{"home": "X", "away": "Y", "best_market": "Over 2.5"}],
        }
    ]
    out = apply_ia_gate_to_hits(hits, audit=state)
    assert out == []


def test_append_bot_hits_stores_ia_context(tmp_path):
    from history.bot_signals import append_bot_hits

    log = tmp_path / "bot_signals.jsonl"
    hits = [
        {
            "bot_id": "b1",
            "bot_name": "IA — Teste",
            "template": "live_scenario_ev_confirmed",
            "mode": "live",
            "matches": [
                {
                    "home": "Benfica",
                    "away": "Porto",
                    "league": "Primeira Liga",
                    "kickoff": "2026-06-28T20:00:00Z",
                    "best_market": "Cantos Over",
                    "best_ev_pct": 8.0,
                    "best_score": 0.62,
                    "odd": 2.1,
                    "minute": 58,
                    "score": "0-1",
                    "scenario_id": "fav_push_post_ht",
                    "pattern_source": "situation",
                    "pattern_window": "post_ht_0_15",
                }
            ],
        }
    ]
    append_bot_hits(hits, scanned_at="2026-06-28T19:00:00Z", bankroll=200, log_path=log)
    row = json.loads(log.read_text(encoding="utf-8").strip().splitlines()[0])
    assert row["template"] == "live_scenario_ev_confirmed"
    assert row["ia_context"]["scenario_id"] == "fav_push_post_ht"
    assert row["ia_context"]["pattern_source"] == "situation"