"""Testes — histórico de tips e resolução win/loss."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from history.market_settlement import pnl_for_outcome, settle_market
from history.outcome_resolver import resolve_predictions
from history.result_fetcher import FinalScore, ResultFetcher
from history.tips_history import build_history_payload, get_last_tip


class _MockFetcher:
    def __init__(self, results: dict[str, FinalScore | None]):
        self.results = results

    def resolve(
        self,
        home: str,
        away: str,
        kickoff: str,
        fixture_id: int | None = None,
    ) -> FinalScore | None:
        key = f"{home}|{away}|{kickoff}"
        if key in self.results:
            return self.results[key]
        fid_key = f"id:{fixture_id}"
        return self.results.get(fid_key)


def _write_log(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )


def test_resolve_win_updates_outcome_and_pnl(tmp_path):
    log = tmp_path / "tips.jsonl"
    kickoff = "2026-06-28T20:00:00Z"
    _write_log(
        log,
        [
            {
                "logged_at": "2026-06-28T19:00:00+00:00",
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
    assert rows[0]["final_score"] == "2-1"
    assert rows[0]["pnl"] == 10.0

    saved = json.loads(log.read_text(encoding="utf-8").strip())
    assert saved["outcome"] == "win"


def test_resolve_loss_for_under_market(tmp_path):
    log = tmp_path / "tips.jsonl"
    kickoff = "2026-06-27T15:00:00Z"
    _write_log(
        log,
        [
            {
                "logged_at": "2026-06-27T14:00:00+00:00",
                "mode": "prematch",
                "home": "Benfica",
                "away": "Sporting",
                "kickoff": kickoff,
                "market": "Under 2.5",
                "odd": 1.9,
                "outcome": "pending",
                "kelly_stake": 5.0,
            }
        ],
    )
    fetcher = _MockFetcher(
        {
            f"Benfica|Sporting|{kickoff}": FinalScore(
                home="Benfica",
                away="Sporting",
                home_goals=2,
                away_goals=1,
                score_label="2-1",
                status="FT",
            )
        }
    )
    _, stats = resolve_predictions(log, dry_run=False, fetcher=fetcher)
    assert stats.resolved == 1
    assert stats.losses == 1
    row = json.loads(log.read_text(encoding="utf-8").strip())
    assert row["outcome"] == "loss"
    assert row["pnl"] == -5.0


def test_future_kickoff_stays_pending(tmp_path):
    log = tmp_path / "tips.jsonl"
    _write_log(
        log,
        [
            {
                "logged_at": "2026-06-30T10:00:00+00:00",
                "home": "A",
                "away": "B",
                "kickoff": "2099-01-01T20:00:00Z",
                "market": "Over 2.5",
                "odd": 2.0,
                "outcome": "pending",
            }
        ],
    )
    _, stats = resolve_predictions(log, dry_run=False, fetcher=_MockFetcher({}))
    assert stats.resolved == 0
    assert stats.not_finished == 1
    assert stats.still_pending == 1


def test_history_payload_performance(tmp_path):
    log = tmp_path / "tips.jsonl"
    _write_log(
        log,
        [
            {
                "logged_at": "2026-06-30T12:00:00+00:00",
                "mode": "live",
                "home": "A",
                "away": "B",
                "market": "BTTS Sim",
                "odd": 1.8,
                "ev_pct": 5.0,
                "outcome": "win",
                "pnl": 4.0,
                "stake_amount": 5.0,
            },
            {
                "logged_at": "2026-06-30T10:00:00+00:00",
                "mode": "prematch",
                "home": "C",
                "away": "D",
                "market": "Over 2.5",
                "odd": 2.1,
                "ev_pct": 7.0,
                "outcome": "loss",
                "pnl": -5.0,
                "stake_amount": 5.0,
            },
        ],
    )
    payload = build_history_payload(log, limit=10)
    assert payload["last_tip"]["home"] == "C"
    perf = payload["performance"]
    assert perf["wins"] == 1
    assert perf["losses"] == 1
    assert perf["hit_rate_pct"] == 50.0
    assert perf["total_pnl"] == -1.0
    assert len(payload["tips"]) == 2


def test_settle_and_pnl_helpers():
    assert settle_market("Vitória Casa", 2, 0) == "win"
    assert pnl_for_outcome("win", 2.0, 10.0) == 10.0
    assert pnl_for_outcome("loss", 2.0, 10.0) == -10.0


def test_espn_teams_match_helper():
    from history.result_fetcher import _espn_teams_match

    comp = {
        "competitors": [
            {"homeAway": "home", "team": {"displayName": "Netherlands"}},
            {"homeAway": "away", "team": {"displayName": "Morocco"}},
        ]
    }
    assert _espn_teams_match("Netherlands", "Morocco", comp) is True
    assert _espn_teams_match("Morocco", "Netherlands", comp) is True


def test_get_last_tip_filters_mode(tmp_path):
    log = tmp_path / "tips.jsonl"
    _write_log(
        log,
        [
            {"mode": "live", "home": "A", "away": "B", "market": "Over 2.5", "logged_at": "t1"},
            {"mode": "prematch", "home": "C", "away": "D", "market": "BTTS Sim", "logged_at": "t2"},
        ],
    )
    assert get_last_tip(log)["home"] == "C"
    assert get_last_tip(log, mode="live")["home"] == "A"