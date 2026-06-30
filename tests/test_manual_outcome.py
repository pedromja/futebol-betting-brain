"""Testes — correcção manual de GREEN/RED."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from history.manual_outcome import correct_outcome, find_row_index
from tests.test_history_resolve import _write_log


def test_correct_outcome_win_to_loss(tmp_path):
    log = tmp_path / "tips.jsonl"
    _write_log(
        log,
        [
            {
                "signature": "tip|abc",
                "logged_at": "2026-06-28T19:00:00+00:00",
                "home": "A",
                "away": "B",
                "market": "Over 2.5",
                "odd": 2.0,
                "outcome": "win",
                "final_score": "3-1",
                "pnl": 10.0,
                "stake_amount": 10.0,
            }
        ],
    )
    row = correct_outcome(
        kind="tip",
        entry_id="tip|abc",
        outcome="loss",
        final_score="1-0",
        note="resultado errado na API",
        log_path=log,
    )
    assert row["outcome"] == "loss"
    assert row["pnl"] == -10.0
    assert row["final_score"] == "1-0"
    assert row["manual_correction"]["previous_outcome"] == "win"
    assert row["review"]["status"] == "manual"

    saved = json.loads(log.read_text(encoding="utf-8").strip())
    assert saved["outcome"] == "loss"


def test_find_row_by_fallback_id(tmp_path):
    log = tmp_path / "bots.jsonl"
    rows = [
        {
            "bot_id": "b1",
            "logged_at": "2026-06-28T19:00:00+00:00",
            "home": "X",
            "away": "Y",
            "outcome": "pending",
        }
    ]
    _write_log(log, rows)
    loaded = log.read_text(encoding="utf-8").splitlines()
    parsed = [json.loads(x) for x in loaded]
    idx = find_row_index(parsed, "b1|2026-06-28T19:00:00+00:00", kind="bot")
    assert idx == 0