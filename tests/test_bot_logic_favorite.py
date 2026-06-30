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


def test_parse_espn_summary_corners():
    payload = {
        "header": {"id": "401"},
        "boxscore": {
            "teams": [
                {
                    "homeAway": "home",
                    "team": {"displayName": "Benfica"},
                    "statistics": [{"name": "Corner Kicks", "displayValue": "6"}],
                },
                {
                    "homeAway": "away",
                    "team": {"displayName": "Porto"},
                    "statistics": [{"name": "Corner Kicks", "displayValue": "3"}],
                },
            ]
        },
    }
    bundle = parse_espn_summary(payload, home_name="Benfica", away_name="Porto")
    assert bundle is not None
    assert bundle.home.corners == 6
    assert bundle.away.corners == 3