"""Testes — reavaliação pós-jogo e prompts de verificação."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.match_stats_types import MatchLiveStatsBundle, TeamLiveStats
from history.post_match_review import (
    build_review,
    build_verify_queue,
    enrich_resolved_log,
)
from history.result_fetcher import FinalScore
from tests.test_history_resolve import _MockFetcher, _write_log


def _bundle() -> MatchLiveStatsBundle:
    return MatchLiveStatsBundle(
        fixture_id=42,
        home=TeamLiveStats(team="Brasil", xg=1.8, shots_on=6, yellow_cards=2, red_cards=0),
        away=TeamLiveStats(team="Japão", xg=0.9, shots_on=3, yellow_cards=1, red_cards=1),
        xg_source="api",
    )


def test_build_review_enriched():
    row = {
        "home": "Brasil",
        "away": "Japão",
        "market": "Over 2.5",
        "outcome": "win",
        "mode": "live",
        "minute": 30,
        "score_at_tip": "1-0",
    }
    final = FinalScore(
        home="Brasil",
        away="Japão",
        home_goals=2,
        away_goals=1,
        score_label="2-1",
        status="FT",
        fixture_id=42,
    )
    review = build_review(
        row,
        final=final,
        bundle=_bundle(),
        sources_tried=["api-football-stats"],
    )
    assert review["status"] == "enriched"
    assert review["outcome_confirmed"] is True
    assert "xG total" in review["context_note"]
    assert review["ft_stats"]["cards"]["yellow"] == 3


def test_build_review_initial_only_prompt():
    row = {
        "home": "Benfica",
        "away": "Porto",
        "league": "Primeira Liga",
        "market": "BTTS Sim",
        "odd": 1.85,
        "outcome": "loss",
        "final_score": "1-0",
        "pnl": -5.0,
        "bot_name": "BTTS bot",
    }
    review = build_review(
        row,
        final=None,
        bundle=None,
        sources_tried=["api-football", "espn"],
        reason="fixture_id em falta",
    )
    assert review["status"] == "initial_only"
    assert review["needs_verification"] is True
    assert "SofaScore" in review["verify_prompt"]
    assert "BTTS bot" in review["verify_prompt"]


def test_enrich_resolved_log_with_mock_stats(tmp_path):
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
                "outcome": "win",
                "final_score": "2-1",
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
    mock_client = MagicMock()
    mock_client.is_configured = True
    mock_client.quota_exhausted = False

    with patch(
        "history.post_match_review.fetch_match_ft_stats",
        return_value=_bundle(),
    ):
        reviewed, enriched, needs = enrich_resolved_log(
            log,
            dry_run=False,
            fetcher=fetcher,
            client=mock_client,
        )

    assert reviewed == 1
    assert enriched == 1
    assert needs == 0
    row = json.loads(log.read_text(encoding="utf-8").strip())
    assert row["review"]["status"] == "enriched"


def test_build_verify_queue(tmp_path):
    log = tmp_path / "bots.jsonl"
    _write_log(
        log,
        [
            {
                "logged_at": "2026-06-28T19:00:00+00:00",
                "bot_id": "b1",
                "bot_name": "Test",
                "home": "A",
                "away": "B",
                "market": "Over 2.5",
                "outcome": "win",
                "review": {
                    "status": "initial_only",
                    "needs_verification": True,
                    "verify_prompt": "Verifica manualmente",
                },
            }
        ],
    )
    with patch("history.post_match_review.BOT_SIGNALS_LOG", log), patch(
        "history.post_match_review.PREDICTIONS_LOG",
        tmp_path / "empty.jsonl",
    ):
        items = build_verify_queue(limit=5)
    assert len(items) == 1
    assert items[0]["kind"] == "bot"
    assert items[0]["prompt"] == "Verifica manualmente"