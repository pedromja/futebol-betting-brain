"""Testes — API payload dicas IA."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.ia_tips import build_ia_tips_payload
from tests.test_history_resolve import _write_log


def test_build_ia_tips_by_market(tmp_path):
    log = tmp_path / "bot_signals.jsonl"
    _write_log(
        log,
        [
            {
                "logged_at": "2026-06-28T20:00:00+00:00",
                "bot_id": "ia1",
                "bot_name": "IA — Teste",
                "template": "live_scenario_ev_confirmed",
                "mode": "live",
                "home": "Benfica",
                "away": "Porto",
                "market": "Cantos Over",
                "odd": 1.9,
                "ev_pct": 6,
                "outcome": "win",
                "pnl": 5,
                "stake_amount": 5,
            },
            {
                "logged_at": "2026-06-28T19:00:00+00:00",
                "bot_id": "ia1",
                "bot_name": "IA — Teste",
                "template": "live_scenario_ev_confirmed",
                "mode": "live",
                "home": "Sporting",
                "away": "Braga",
                "market": "Cantos Over",
                "odd": 1.85,
                "ev_pct": 5,
                "outcome": "loss",
                "pnl": -5,
                "stake_amount": 5,
            },
            {
                "logged_at": "2026-06-28T18:00:00+00:00",
                "bot_id": "ia1",
                "bot_name": "IA — Teste",
                "template": "live_pattern_discrepancy",
                "mode": "live",
                "home": "A",
                "away": "B",
                "market": "Over 1.5",
                "odd": 1.7,
                "ev_pct": 4,
                "outcome": "win",
                "pnl": 4,
                "stake_amount": 5,
            },
        ],
    )
    payload = build_ia_tips_payload(log_path=log, auto_audit=False)
    assert payload["totals"]["wins"] == 2
    assert payload["totals"]["losses"] == 1
    assert payload["totals"]["hit_rate_pct"] == 66.7
    markets = {m["market"]: m for m in payload["by_market"]}
    assert markets["Cantos Over"]["hit_rate_pct"] == 50.0
    assert markets["Over 1.5"]["hit_rate_pct"] == 100.0
    assert len(payload["tips"]) == 3