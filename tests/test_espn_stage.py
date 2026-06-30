"""Testes — normalização de fase ESPN (Motivation Gate / eliminatórias)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.espn_live_scanner import EspnLiveScanner
from discovery.espn_stage import resolve_espn_stage, stage_from_scoreboard
from prematch.auditors import evaluate_motivation
from prematch.transfermarkt.analyzer import analyze_prematch
from stakes.auto import is_knockout_context


_SCOREBOARD_FIXTURE = {
    "leagues": [
        {
            "season": {
                "type": {
                    "id": "2",
                    "type": 13801,
                    "name": "Round of 32",
                    "abbreviation": "Round of 32",
                },
                "slug": "round-of-32",
            }
        }
    ],
    "events": [
        {
            "id": "760488",
            "date": "2026-06-30T01:00Z",
            "season": {"year": 2026, "type": 13801, "slug": "round-of-32"},
            "competitions": [
                {
                    "status": {
                        "displayClock": "72'",
                        "type": {"state": "in", "completed": False, "name": "STATUS_IN_PROGRESS"},
                    },
                    "competitors": [
                        {
                            "homeAway": "home",
                            "score": "1",
                            "team": {"displayName": "Netherlands"},
                        },
                        {
                            "homeAway": "away",
                            "score": "1",
                            "team": {"displayName": "Morocco"},
                        },
                    ],
                }
            ],
        }
    ],
}


def test_stage_from_scoreboard_round_of_32():
    assert stage_from_scoreboard(_SCOREBOARD_FIXTURE) == "Round of 32"


def test_resolve_espn_stage_from_numeric_event_type():
    event = _SCOREBOARD_FIXTURE["events"][0]
    stage = resolve_espn_stage(event, _SCOREBOARD_FIXTURE)
    assert stage == "Round of 32"
    assert is_knockout_context("FIFA World Cup", stage) is True


def test_espn_live_scanner_uses_human_stage():
    scanner = EspnLiveScanner()
    event = _SCOREBOARD_FIXTURE["events"][0]
    fx = scanner._event_to_live(
        event,
        "FIFA World Cup",
        "fifa.world",
        scoreboard=_SCOREBOARD_FIXTURE,
    )
    assert fx is not None
    assert fx.stage == "Round of 32"


def test_motivation_knockout_not_veto_with_resolved_stage():
    tm = analyze_prematch("Netherlands", "Morocco")
    mot = evaluate_motivation(
        "Netherlands",
        "Morocco",
        best_market="Over 2.5",
        best_ev=0.15,
        league="FIFA World Cup",
        stage="Round of 32",
        tm_insights=tm,
        football_data_key="",
    )
    assert mot.motivation_score >= 2
    assert mot.veto is False