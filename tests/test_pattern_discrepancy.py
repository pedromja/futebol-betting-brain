"""Testes — motor IA de discrepância histórica vs live."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.evaluator import evaluate_bot
from bots.pattern_discrepancy import (
    attach_pattern_fields,
    compute_pattern_analysis,
    detect_situation,
)
from bots.types import BotConfig
from prematch.historical.types import TeamHistoricalProfile, VenueSlice


def _profile(**kwargs) -> TeamHistoricalProfile:
    home = VenueSlice(
        matches=12,
        corners_avg=6.0,
        goals_scored_avg=1.8,
        fouls_avg=11.0,
    )
    away = VenueSlice(
        matches=10,
        corners_avg=4.5,
        goals_scored_avg=1.2,
        fouls_avg=13.0,
    )
    defaults = {
        "team": "Benfica",
        "league": "P1",
        "season": "2526",
        "matches": 22,
        "home": home,
        "away": away,
    }
    defaults.update(kwargs)
    return TeamHistoricalProfile(**defaults)


def test_detect_situation_fav_losing_post_ht():
    match = {
        "favorite_side": "home",
        "favorite_status": "losing",
        "minute": 58,
        "match_status": "2H",
        "is_second_half": True,
        "ht_home_score": 0,
        "ht_away_score": 1,
        "home_score": 0,
        "away_score": 1,
    }
    assert detect_situation(match) == "fav_losing_post_ht"


def test_compute_pattern_analysis_underperforming():
    match = {
        "home": "Benfica",
        "away": "Sporting",
        "league": "Primeira Liga",
        "favorite_side": "home",
        "favorite_status": "losing",
        "minute": 58,
        "match_status": "2H",
        "is_second_half": True,
        "ht_home_score": 0,
        "ht_away_score": 1,
        "home_score": 0,
        "away_score": 1,
        "home_corners": 0,
        "away_corners": 2,
        "home_yellow_cards": 0,
        "home_red_cards": 0,
        "odds_hint": {"home_win": 1.65, "away_win": 4.5},
    }
    mock_store = MagicMock()
    mock_store.profile.return_value = _profile()

    with patch("bots.pattern_discrepancy.get_store", return_value=mock_store), patch(
        "bots.pattern_discrepancy._record_track", return_value=1
    ):
        out = compute_pattern_analysis(match)

    assert out["pattern_has_profile"] is True
    assert out["pattern_situation"] == "fav_losing_post_ht"
    assert out["pattern_corners_gap_pct"] >= 40
    assert out["pattern_discrepancy_score"] >= 40
    assert out["pattern_discrepancy_trend"] == 1
    assert "Benfica" in out["pattern_summary"]
    assert out["pattern_alert"] is True


def test_attach_pattern_fields_no_profile():
    match = {
        "home": "Unknown FC",
        "away": "Other FC",
        "minute": 40,
        "favorite_side": "home",
        "favorite_status": "losing",
    }
    mock_store = MagicMock()
    mock_store.profile.return_value = None

    with patch("bots.pattern_discrepancy.get_store", return_value=mock_store):
        out = attach_pattern_fields(match)

    assert out["pattern_has_profile"] is False


def test_evaluate_bot_pattern_conditions():
    match = {
        "minute": 55,
        "pattern_has_profile": True,
        "pattern_discrepancy_score": 62,
        "pattern_discrepancy_trend": 1,
        "favorite_losing_or_drawing": True,
        "favorite_status": "losing",
    }
    bot = BotConfig(
        name="IA Padrão",
        mode="live",
        conditions=[
            {"field": "pattern_has_profile", "operator": "eq", "value": True},
            {"field": "pattern_discrepancy_score", "operator": "gte", "value": 50},
            {"field": "pattern_discrepancy_trend", "operator": "gte", "value": 0},
        ],
    )
    assert evaluate_bot(bot, match, mode="live")
    assert not evaluate_bot(bot, {**match, "pattern_discrepancy_score": 30}, mode="live")