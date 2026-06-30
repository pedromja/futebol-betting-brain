"""Testes — temperatura live e análise de pressão."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.stats_snapshots import load_snapshot_hints_batch
from live.match_intensity import (
    build_pressure_analysis,
    compute_temperature,
    temperature_from_fixture_dict,
)
from web.api.serializers import attach_game_temperature


def test_temperature_calm_low_scoring():
    t = compute_temperature(minute=60, home_score=0, away_score=0)
    assert t.level == "calm"
    assert t.events_per_min < 0.055


def test_temperature_hot_many_goals():
    t = compute_temperature(minute=50, home_score=3, away_score=2)
    assert t.level == "hot"
    assert t.events_per_min >= 0.13


def test_temperature_warm_with_snapshot_activity():
    prev = {"minute": 30, "home_score": 1, "away_score": 0, "total_corners": 2, "total_cards": 1, "home_shots_on": 3, "away_shots_on": 1}
    last = {"minute": 38, "home_score": 2, "away_score": 0, "total_corners": 5, "total_cards": 2, "home_shots_on": 6, "away_shots_on": 2}
    t = compute_temperature(minute=38, home_score=2, away_score=0, snapshot_prev=prev, snapshot_last=last)
    assert t.level in ("warm", "hot")
    assert t.events_per_min > 0.05


def test_pressure_analysis_series():
    history = [
        {"minute": 20, "home_xg": 0.4, "away_xg": 0.2, "home_possession_pct": 55, "home_shots_on": 2, "away_shots_on": 1, "home_score": 0, "away_score": 0, "total_corners": 2, "total_cards": 0},
        {"minute": 35, "home_xg": 1.1, "away_xg": 0.3, "home_possession_pct": 62, "home_shots_on": 5, "away_shots_on": 2, "home_score": 1, "away_score": 0, "total_corners": 4, "total_cards": 1},
    ]
    pa = build_pressure_analysis(history)
    assert pa["available"] is True
    assert len(pa["series"]) == 2
    assert pa["current"]["home_pressure"] > 50
    assert pa["series"][1]["intensity"] > 0


def test_attach_game_temperature_on_fixtures():
    fixtures = [
        {
            "home": "A",
            "away": "B",
            "fixture_id": 999001,
            "minute": 70,
            "home_score": 2,
            "away_score": 2,
            "status": "2H",
        }
    ]
    out = attach_game_temperature(fixtures)
    assert out[0]["game_temperature"]["level"] in ("calm", "warm", "hot")
    assert "events_per_min" in out[0]["game_temperature"]


def test_snapshot_hints_batch(tmp_path, monkeypatch):
    from config.data_paths import LIVE_STATS_SNAPSHOTS

    log = tmp_path / "snaps.jsonl"
    rows = [
        '{"fixture_id": 10, "minute": 10, "home_score": 0, "away_score": 0, "total_corners": 1, "total_cards": 0, "home_shots_on": 1, "away_shots_on": 0}',
        '{"fixture_id": 10, "minute": 20, "home_score": 1, "away_score": 0, "total_corners": 3, "total_cards": 1, "home_shots_on": 3, "away_shots_on": 1}',
        '{"fixture_id": 20, "minute": 15, "home_score": 0, "away_score": 1, "total_corners": 0, "total_cards": 0, "home_shots_on": 0, "away_shots_on": 2}',
    ]
    log.write_text("\n".join(rows) + "\n", encoding="utf-8")
    monkeypatch.setattr("discovery.stats_snapshots.LIVE_STATS_SNAPSHOTS", log)

    hints = load_snapshot_hints_batch([10, 20, 99])
    assert hints[10][0] is not None
    assert hints[10][1]["minute"] == 20
    assert hints[20][1]["minute"] == 15
    assert 99 not in hints