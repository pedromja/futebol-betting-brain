"""Testes — cenários comunidade, apatia e gate de reação."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.evaluator import evaluate_bot
from bots.pattern_discrepancy import attach_pattern_fields
from bots.scenario_engine import compute_scenario_analysis
from bots.types import BotConfig
from prematch.historical.types import TeamHistoricalProfile, VenueSlice


def _profile():
    return TeamHistoricalProfile(
        team="Benfica",
        league="P1",
        season="2526",
        matches=22,
        home=VenueSlice(matches=12, corners_avg=6.0, goals_scored_avg=1.8, fouls_avg=11.0),
        away=VenueSlice(matches=10, corners_avg=4.5, goals_scored_avg=1.2, fouls_avg=13.0),
    )


def _apathetic_match():
    return {
        "home": "Benfica",
        "away": "Sporting",
        "league": "Primeira Liga",
        "fixture_id": 1001,
        "favorite_side": "home",
        "favorite_status": "losing",
        "favorite_losing_or_drawing": True,
        "minute": 58,
        "match_status": "2H",
        "is_second_half": True,
        "ht_home_score": 0,
        "ht_away_score": 1,
        "home_score": 0,
        "away_score": 1,
        "home_corners": 0,
        "away_corners": 3,
        "home_shots_on": 0,
        "away_shots_on": 4,
        "home_xg": 0.4,
        "away_xg": 1.1,
        "xg_diff": -0.7,
        "home_possession_pct": 48,
        "best_ev_pct": 6,
        "best_market": "Cantos Over",
        "pattern_situation": "fav_losing_post_ht",
        "pattern_team": "Benfica",
        "pattern_discrepancy_score": 72,
        "pattern_discrepancy_trend": 1,
    }


def _reacting_match():
    m = _apathetic_match()
    m.update(
        {
            "home_corners": 5,
            "home_shots_on": 5,
            "home_xg": 1.3,
            "xg_diff": 0.2,
            "away_xg": 1.1,
            "home_possession_pct": 58,
            "pattern_discrepancy_trend": -1,
            "pattern_discrepancy_score": 28,
        }
    )
    return m


def test_scenario_apathetic_blocks_play():
    with patch("bots.scenario_engine.load_stats_history", return_value=[]):
        out = compute_scenario_analysis(_apathetic_match())

    assert out["scenario_active"] is True
    assert out["scenario_apathetic"] is True
    assert out["scenario_reaction_confirmed"] is False
    assert out["scenario_play_allowed"] is False
    assert "apática" in out["scenario_summary"].lower()


def test_scenario_reaction_allows_ev_play():
    history = [
        {"minute": 48, "home_corners": 2, "home_shots_on": 2, "home_xg": 0.7},
        {"minute": 52, "home_corners": 3, "home_shots_on": 3, "home_xg": 0.9},
    ]
    with patch("bots.scenario_engine.load_stats_history", return_value=history):
        out = compute_scenario_analysis(_reacting_match())

    assert out["scenario_apathetic"] is False
    assert out["scenario_reaction_confirmed"] is True
    assert out["scenario_ev_aligned"] is True
    assert out["scenario_play_allowed"] is True


def test_evaluate_bot_ev_confirmed_template():
    bot = BotConfig(
        name="EV cenário",
        mode="live",
        conditions=[
            {"field": "scenario_play_allowed", "operator": "eq", "value": True},
            {"field": "scenario_reaction_confirmed", "operator": "eq", "value": True},
            {"field": "scenario_apathetic", "operator": "eq", "value": False},
        ],
    )
    good = {
        "minute": 60,
        "scenario_play_allowed": True,
        "scenario_reaction_confirmed": True,
        "scenario_apathetic": False,
    }
    bad = {**good, "scenario_apathetic": True, "scenario_play_allowed": False}
    assert evaluate_bot(bot, good, mode="live")
    assert not evaluate_bot(bot, bad, mode="live")


def test_attach_pattern_includes_scenario():
    match = _apathetic_match()
    mock_store = MagicMock()
    mock_store.profile.return_value = _profile()

    with (
        patch("bots.pattern_discrepancy.get_store", return_value=mock_store),
        patch("bots.pattern_discrepancy._record_track", return_value=1),
        patch("bots.scenario_engine.load_stats_history", return_value=[]),
    ):
        out = attach_pattern_fields(match)

    assert "scenario_active" in out
    assert out.get("scenario_apathetic") is True