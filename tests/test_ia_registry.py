"""Testes — registo unificado IA pré-jogo / ao vivo."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from history.ia_registry import load_ia_tip_rows, load_trackable_tip_rows


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def test_load_ia_tip_rows_merges_live_bot_and_predictions(tmp_path):
    pred = tmp_path / "predictions.jsonl"
    bots = tmp_path / "bot_signals.jsonl"
    live = tmp_path / "ia_live_signals.jsonl"

    _write(
        live,
        [
            {
                "id": "a1",
                "logged_at": "2026-06-30T20:00:00+00:00",
                "home": "France",
                "away": "Sweden",
                "market": "Over 2.5",
                "odd": 2.0,
                "minute": 55,
                "espn_event_id": "99",
                "outcome": "win",
                "signature": "ia_live|99|France|Sweden|Over 2.5|55|2026-06-30T20:00:00+00:00",
            }
        ],
    )
    _write(
        bots,
        [
            {
                "logged_at": "2026-06-30T10:00:00+00:00",
                "home": "A",
                "away": "B",
                "market": "Vitória Casa",
                "template": "prematch_underdog_raca_ia",
                "bot_name": "IA — Test",
                "mode": "prematch",
                "outcome": "loss",
                "signature": "bot|x|prematch|A|B|Vitória Casa|k|0.7",
            }
        ],
    )
    _write(
        pred,
        [
            {
                "logged_at": "2026-06-30T10:00:00+00:00",
                "home": "A",
                "away": "B",
                "market": "Vitória Casa",
                "mode": "prematch",
                "tip_source": "ia_bot",
                "outcome": "loss",
                "signature": "pred|bot|x|prematch|A|B|Vitória Casa|k|0.7",
            }
        ],
    )

    rows = load_ia_tip_rows(
        predictions_path=pred,
        bot_signals_path=bots,
        ia_live_path=live,
    )
    assert len(rows) == 2
    modes = {r["mode"] for r in rows}
    assert modes == {"prematch", "live"}
    wins = sum(1 for r in rows if r["outcome"] == "win")
    losses = sum(1 for r in rows if r["outcome"] == "loss")
    assert wins == 1
    assert losses == 1


def test_trackable_includes_predictions_and_unmirrored_ia(tmp_path):
    pred = tmp_path / "predictions.jsonl"
    live = tmp_path / "ia_live_signals.jsonl"
    bots = tmp_path / "bot_signals.jsonl"

    _write(
        pred,
        [
            {
                "logged_at": "2026-06-30T12:00:00+00:00",
                "mode": "prematch",
                "home": "X",
                "away": "Y",
                "market": "Over 2.5",
                "outcome": "pending",
            }
        ],
    )
    _write(
        live,
        [
            {
                "id": "z1",
                "logged_at": "2026-06-30T21:00:00+00:00",
                "home": "P",
                "away": "Q",
                "market": "Under 2.5",
                "minute": 70,
                "espn_event_id": "1",
                "outcome": "pending",
                "signature": "ia_live|1|P|Q|Under 2.5|70|2026-06-30T21:00:00+00:00",
            }
        ],
    )
    _write(bots, [])

    rows = load_trackable_tip_rows(
        predictions_path=pred,
        bot_signals_path=bots,
        ia_live_path=live,
    )
    assert len(rows) == 2
    assert sum(1 for r in rows if r.get("mode") == "live") == 1
    assert sum(1 for r in rows if r.get("mode") == "prematch") == 1