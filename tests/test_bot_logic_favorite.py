"""Testes — lógica OR/AND, favorito e cantos nos bots."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.evaluator import evaluate_bot
from bots.live_context import attach_favorite_fields
from bots.types import BotConfig
from discovery.espn_live_stats import parse_espn_summary


def _match(**kwargs):
    base = {
        "home": "Benfica",
        "away": "Porto",
        "minute": 30,
        "home_score": 0,
        "away_score": 1,
        "score": "0-1",
        "odds_hint": {"home_win": 1.75, "draw": 3.40, "away_win": 4.50},
        "best_ev_pct": 6,
    }
    base.update(kwargs)
    return attach_favorite_fields(base)


def test_favorite_losing_when_home_fav_behind():
    m = _match()
    assert m["favorite_side"] == "home"
    assert m["favorite_status"] == "losing"
    assert m["favorite_losing_or_drawing"] is True


def test_favorite_drawing():
    m = _match(home_score=1, away_score=1, score="1-1")
    assert m["favorite_status"] == "drawing"
    assert m["favorite_losing_or_drawing"] is True


def test_conditions_logic_or():
    bot = BotConfig(
        name="OR",
        mode="live",
        conditions_logic="or",
        conditions=[
            {"field": "favorite_status", "operator": "eq", "value": "winning"},
            {"field": "favorite_status", "operator": "eq", "value": "losing"},
        ],
    )
    assert evaluate_bot(bot, _match(), mode="live")
    assert not evaluate_bot(
        bot, _match(home_score=1, away_score=1, score="1-1"), mode="live"
    )


def test_condition_groups_and_or():
    bot = BotConfig(
        name="Grupos",
        mode="live",
        groups_logic="and",
        condition_groups=[
            {
                "logic": "or",
                "conditions": [
                    {"field": "favorite_status", "operator": "eq", "value": "losing"},
                    {"field": "favorite_status", "operator": "eq", "value": "drawing"},
                ],
            },
            {
                "logic": "and",
                "conditions": [
                    {"field": "total_corners", "operator": "gte", "value": 4},
                ],
            },
        ],
    )
    m = _match(total_corners=5)
    assert evaluate_bot(bot, m, mode="live")
    m2 = _match(total_corners=2)
    assert not evaluate_bot(bot, m2, mode="live")


def test_parse_espn_summary_corners_label():
    payload = {
        "header": {"id": "401"},
        "boxscore": {
            "teams": [
                {
                    "homeAway": "home",
                    "team": {"id": "1", "displayName": "Benfica"},
                    "statistics": [{"name": "Corner Kicks", "displayValue": "6"}],
                },
                {
                    "homeAway": "away",
                    "team": {"id": "2", "displayName": "Porto"},
                    "statistics": [{"name": "Corner Kicks", "displayValue": "3"}],
                },
            ]
        },
    }
    bundle = parse_espn_summary(payload, home_name="Benfica", away_name="Porto")
    assert bundle is not None
    assert bundle.home.corners == 6
    assert bundle.away.corners == 3


def test_parse_espn_summary_won_corners_and_stats():
    payload = {
        "header": {"id": "760488"},
        "boxscore": {
            "teams": [
                {
                    "homeAway": "home",
                    "team": {"id": "449", "displayName": "Netherlands"},
                    "statistics": [
                        {"name": "wonCorners", "displayValue": "5"},
                        {"name": "possessionPct", "displayValue": "29.9"},
                        {"name": "totalShots", "displayValue": "6"},
                        {"name": "shotsOnTarget", "displayValue": "2"},
                        {"name": "foulsCommitted", "displayValue": "18"},
                        {"name": "yellowCards", "displayValue": "0"},
                        {"name": "saves", "displayValue": "5"},
                        {"name": "passPct", "displayValue": "0.8"},
                    ],
                },
                {
                    "homeAway": "away",
                    "team": {"id": "2869", "displayName": "Morocco"},
                    "statistics": [
                        {"name": "wonCorners", "displayValue": "8"},
                        {"name": "possessionPct", "displayValue": "70.1"},
                        {"name": "totalShots", "displayValue": "11"},
                        {"name": "shotsOnTarget", "displayValue": "5"},
                        {"name": "foulsCommitted", "displayValue": "15"},
                        {"name": "yellowCards", "displayValue": "1"},
                        {"name": "saves", "displayValue": "1"},
                        {"name": "passPct", "displayValue": "0.9"},
                    ],
                },
            ]
        },
        "leaders": [
            {
                "team": {"id": "449"},
                "leaders": [
                    {
                        "name": "saves",
                        "leaders": [
                            {
                                "statistics": [
                                    {"name": "expectedGoalsConceded", "value": 1.381, "displayValue": "1.38"},
                                ]
                            }
                        ],
                    }
                ],
            },
            {
                "team": {"id": "2869"},
                "leaders": [
                    {
                        "name": "saves",
                        "leaders": [
                            {
                                "statistics": [
                                    {"name": "expectedGoalsConceded", "value": 0.239, "displayValue": "0.24"},
                                ]
                            }
                        ],
                    }
                ],
            },
        ],
    }
    bundle = parse_espn_summary(payload, home_name="Netherlands", away_name="Morocco")
    assert bundle is not None
    assert bundle.home.corners == 5
    assert bundle.away.corners == 8
    assert bundle.home.possession_pct == 30
    assert bundle.away.possession_pct == 70
    assert bundle.home.shots_on == 2
    assert bundle.away.shots_total == 11
    assert bundle.home.fouls == 18
    assert bundle.away.yellow_cards == 1
    assert bundle.home.passes_pct == 80
    assert bundle.away.passes_pct == 90
    assert bundle.home.xg == 0.24
    assert bundle.away.xg == 1.38
    assert bundle.xg_source == "espn"