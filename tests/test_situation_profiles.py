"""Testes — perfis condicionais por situação e janela (Fase 2)."""

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.pattern_discrepancy import compute_pattern_analysis
from prematch.historical.situation_aggregate import aggregate_situation_rows
from prematch.historical.situation_store import SituationStore, cumulative_expected
from prematch.historical.types import TeamSituationProfile


def _rows():
    return [
        {
            "HomeTeam": "Benfica",
            "AwayTeam": "Sp Lisbon",
            "HTHG": "0",
            "HTAG": "1",
            "FTHG": "1",
            "FTAG": "2",
            "HS": "14",
            "AS": "9",
            "HST": "5",
            "AST": "4",
            "HC": "8",
            "AC": "3",
            "HF": "11",
            "AF": "13",
            "B365CH": "1.50",
            "B365CA": "6.00",
        },
        {
            "HomeTeam": "Benfica",
            "AwayTeam": "Porto",
            "HTHG": "0",
            "HTAG": "1",
            "FTHG": "2",
            "FTAG": "1",
            "HS": "16",
            "AS": "8",
            "HST": "7",
            "AST": "2",
            "HC": "10",
            "AC": "2",
            "HF": "10",
            "AF": "12",
            "B365CH": "1.45",
            "B365CA": "7.00",
        },
        {
            "HomeTeam": "Sp Lisbon",
            "AwayTeam": "Benfica",
            "HTHG": "1",
            "HTAG": "0",
            "FTHG": "1",
            "FTAG": "1",
            "HS": "10",
            "AS": "12",
            "HST": "3",
            "AST": "5",
            "HC": "4",
            "AC": "6",
            "HF": "12",
            "AF": "9",
            "B365CH": "2.60",
            "B365CA": "2.50",
        },
        {
            "HomeTeam": "Benfica",
            "AwayTeam": "Guimaraes",
            "HTHG": "0",
            "HTAG": "1",
            "FTHG": "1",
            "FTAG": "1",
            "HS": "13",
            "AS": "7",
            "HST": "4",
            "AST": "2",
            "HC": "9",
            "AC": "2",
            "HF": "9",
            "AF": "11",
            "B365CH": "1.40",
            "B365CA": "8.00",
        },
    ]


def test_aggregate_situation_fav_losing_at_ht():
    profiles = aggregate_situation_rows(_rows(), league_code="PPL", season="2526")
    keys = {(p.team, p.venue, p.situation, p.window) for p in profiles}
    assert ("Benfica", "home", "fav_losing_at_ht", "post_ht_0_15") in keys
    assert ("Benfica", "home", "fav_losing_at_ht", "first_half") in keys

    fav_posts = [
        p
        for p in profiles
        if p.team == "Benfica"
        and p.situation == "fav_losing_at_ht"
        and p.window == "post_ht_0_15"
    ]
    assert len(fav_posts) >= 2
    assert sum(p.metrics.matches for p in fav_posts) >= 3
    assert any(p.metrics.goals_scored_avg > 0 for p in fav_posts)


def test_cumulative_expected_post_ht_minute_58():
    profiles = aggregate_situation_rows(_rows(), league_code="PPL", season="2526")
    by_window = {
        p.window: p
        for p in profiles
        if p.team == "Benfica"
        and p.venue == "home"
        and p.situation == "fav_losing_at_ht"
    }
    metrics, window, sample = cumulative_expected(by_window, minute=58, post_ht=True)
    assert window == "post_ht_0_15"
    assert sample >= 2
    assert metrics.corners_avg > 0
    assert metrics.goals_scored_avg >= 0


def test_pattern_analysis_uses_situation_profile():
    store = SituationStore()
    store._index = {}
    for p in aggregate_situation_rows(_rows(), league_code="PPL", season="2526"):
        if p.team == "Benfica" and p.situation == "fav_losing_at_ht":
            key = f"{p.team}|{p.venue}|{p.situation}|{p.window}"
            store._index[key] = p

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
        "home_yellow_cards": 0,
        "home_red_cards": 0,
    }

    from prematch.historical.types import TeamHistoricalProfile, VenueSlice

    season_prof = TeamHistoricalProfile(
        team="Benfica",
        league="PPL",
        season="2526",
        matches=20,
        home=VenueSlice(matches=10, corners_avg=6, goals_scored_avg=1.5, fouls_avg=11),
        away=VenueSlice(matches=10, corners_avg=4, goals_scored_avg=1.0, fouls_avg=12),
    )

    with (
        patch("bots.pattern_discrepancy.get_situation_store", return_value=store),
        patch("bots.pattern_discrepancy.get_store") as mock_season,
        patch("bots.pattern_discrepancy._record_track", return_value=0),
    ):
        mock_season.return_value.profile.return_value = season_prof
        out = compute_pattern_analysis(match)

    assert out["pattern_source"] == "situation"
    assert out["pattern_window"] == "post_ht_0_15"
    assert out["pattern_hist_situation"] == "fav_losing_at_ht"
    assert out["pattern_situation_sample"] >= 3
    assert "Histórico condicional" in out["pattern_summary"]