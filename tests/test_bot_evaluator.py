"""Testes — avaliador de bots."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.evaluator import evaluate_bot
from bots.types import BotConfig


def _match(**kwargs):
    base = {
        "home": "Benfica",
        "away": "Sporting",
        "league": "Primeira Liga",
        "kickoff": "2099-01-01T20:00:00+00:00",
        "best_market": "Over 2.5",
        "best_ev_pct": 8.0,
        "best_score": 0.62,
        "should_bet": True,
        "stake_level": 5,
        "motivation": {"motivation_score": 3, "alignment": "strong"},
    }
    base.update(kwargs)
    return base


def test_bot_market_and_ev_filter():
    bot = BotConfig(
        name="Over",
        mode="prematch",
        markets=["Over 2.5"],
        min_ev_pct=5,
        min_score=0.6,
    )
    assert evaluate_bot(bot, _match(), mode="prematch")
    assert not evaluate_bot(bot, _match(best_market="BTTS Sim"), mode="prematch")


def test_bot_condition_motivation():
    bot = BotConfig(
        name="MG",
        mode="prematch",
        conditions=[
            {
                "category": "motivacao",
                "field": "motivation_score",
                "operator": "gte",
                "value": 2,
            }
        ],
    )
    assert evaluate_bot(bot, _match(), mode="prematch")
    assert not evaluate_bot(
        bot, _match(motivation={"motivation_score": 1}), mode="prematch"
    )


def test_bot_mode_mismatch():
    bot = BotConfig(name="Live", mode="live")
    assert not evaluate_bot(bot, _match(), mode="prematch")