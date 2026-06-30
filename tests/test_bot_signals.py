"""Testes — registo e resolução de sinais de bots."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.performance import build_bot_history_payload, build_performance_payload
from history.bot_signals import append_bot_hits
from history.outcome_resolver import resolve_predictions
from history.result_fetcher import FinalScore
from tests.test_history_resolve import _MockFetcher, _write_log


def test_append_bot_hits_dedup(tmp_path):
    log = tmp_path / "bot_signals.jsonl"
    hits = [
        {
            "bot_id": "b1",
            "bot_name": "Over live",
            "mode": "live",
            "matches": [
                {
                    "home": "Benfica",
                    "away": "Porto",
                    "league": "Primeira Liga",
                    "kickoff": "2026-06-28T20:00:00Z",
                    "best_market": "Over 2.5",
                    "best_ev_pct": 8.0,
                    "best_score": 0.62,
                    "odd": 2.1,
                    "minute": 35,
                    "score": "1-0",
                    "fixture_id": 99,
                }
            ],
        }
    ]
    n1 = append_bot_hits(hits, scanned_at="2026-06-28T19:00:00Z", bankroll=200, log_path=log)
    n2 = append_bot_hits(hits, scanned_at="2026-06-28T19:05:00Z", bankroll=200, log_path=log)
    assert n1 == 1
    assert n2 == 0
    rows = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row["bot_id"] == "b1"
    assert row["market"] == "Over 2.5"
    assert row["outcome"] == "pending"
    assert row["stake_amount"] is not None


def test_resolve_bot_signal_win(tmp_path):
    log = tmp_path / "bot_signals.jsonl"
    kickoff = "2026-06-28T20:00:00Z"
    _write_log(
        log,
        [
            {
                "logged_at": "2026-06-28T19:00:00+00:00",
                "bot_id": "b1",
                "bot_name": "Cards",
                "mode": "live",
                "home": "Brasil",
                "away": "Japão",
                "kickoff": kickoff,
                "market": "Over 2.5",
                "odd": 2.0,
                "ev_pct": 8.0,
                "outcome": "pending",
                "stake_amount": 10.0,
                "fixture_id": 42,
            }
        ],
    )
    fetcher = _MockFetcher(
        {
            "id:42": FinalScore(
                home="Brasil",
                away="Japão",
                home_goals=2,
                away_goals=1,
                score_label="2-1",
                status="FT",
                fixture_id=42,
            )
        }
    )
    rows, stats = resolve_predictions(log, dry_run=False, fetcher=fetcher)
    assert stats.resolved == 1
    assert stats.wins == 1
    assert rows[0]["outcome"] == "win"
    assert rows[0]["pnl"] == 10.0


def test_bot_performance_payload(tmp_path):
    log = tmp_path / "bot_signals.jsonl"
    _write_log(
        log,
        [
            {
                "logged_at": "2026-06-28T19:00:00+00:00",
                "bot_id": "b1",
                "bot_name": "Bot A",
                "mode": "prematch",
                "home": "A",
                "away": "B",
                "market": "Over 2.5",
                "odd": 2.0,
                "ev_pct": 6,
                "outcome": "win",
                "pnl": 5.0,
                "stake_amount": 5.0,
            },
            {
                "logged_at": "2026-06-28T18:00:00+00:00",
                "bot_id": "b1",
                "bot_name": "Bot A",
                "mode": "prematch",
                "home": "C",
                "away": "D",
                "market": "BTTS Sim",
                "odd": 1.9,
                "ev_pct": 4,
                "outcome": "loss",
                "pnl": -5.0,
                "stake_amount": 5.0,
            },
        ],
    )
    summary = build_performance_payload(log)
    assert summary["total_signals"] == 2
    assert summary["by_bot"]["b1"]["wins"] == 1
    assert summary["by_bot"]["b1"]["losses"] == 1
    assert summary["by_bot"]["b1"]["hit_rate_pct"] == 50.0

    hist = build_bot_history_payload("b1", log_path=log, limit=10)
    assert hist["bot_name"] == "Bot A"
    assert hist["performance"]["resolved"] == 2
    assert len(hist["signals"]) == 2