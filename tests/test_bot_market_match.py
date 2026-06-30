"""Testes — filtros de mercado nos bots (favorito, Over 1.5, HT)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.catalog import MARKET_OPTIONS, catalog_payload
from bots.evaluator import evaluate_bot
from bots.live_context import attach_favorite_fields
from bots.market_match import market_matches_filter
from bots.types import BotConfig


def test_catalog_includes_requested_markets():
    required = [
        "Over 1.5",
        "Vitória Favorito",
        "Dupla Hipótese Favorito",
        "Over 0.5 HT",
        "Over 1 HT",
        "Over 1.5 HT",
    ]
    for label in required:
        assert label in MARKET_OPTIONS
    cats = {c["id"]: c for c in catalog_payload()["categories"]}
    live_fields = {f["id"] for f in cats["live"]["fields"]}
    fav_fields = {f["id"] for f in cats["favorito"]["fields"]}
    assert "ht_total_goals" in live_fields
    assert "first_half_goals" in live_fields
    assert "favorite_winning" in fav_fields
    assert "away_is_favorite" in fav_fields


def test_favorite_win_market_filter():
    m = attach_favorite_fields(
        {
            "best_market": "Vitória Casa",
            "odds_hint": {"home_win": 1.6, "away_win": 5.0},
            "home_score": 1,
            "away_score": 0,
        }
    )
    assert market_matches_filter(m, "Vitória Favorito")
    assert not market_matches_filter(m, "Vitória Fora")


def test_favorite_dc_market_filter():
    m = attach_favorite_fields(
        {
            "best_market": "Dupla Hipótese X2",
            "odds_hint": {"home_win": 2.8, "away_win": 2.1},
        }
    )
    assert market_matches_filter(m, "Dupla Hipótese Favorito")


def test_over15_matches_over25_pick():
    m = {"best_market": "Over 2.5", "top_markets": []}
    assert market_matches_filter(m, "Over 1.5")
    assert not market_matches_filter(m, "Under 1.5")


def test_ht_over_market_label_in_top_markets():
    m = {
        "best_market": "Over 2.5",
        "top_markets": ["Over 0.5 HT (0.61)"],
        "favorite_side": "home",
    }
    assert market_matches_filter(m, "Over 0.5 HT")


def test_bot_favorite_winning_condition():
    m = attach_favorite_fields(
        {
            "minute": 30,
            "home_score": 2,
            "away_score": 0,
            "odds_hint": {"home_win": 1.5, "away_win": 6.0},
            "best_market": "Vitória Casa",
            "best_ev_pct": 5,
        }
    )
    bot = BotConfig(
        name="Fav ganha",
        mode="live",
        conditions=[
            {"field": "favorite_winning", "operator": "eq", "value": True},
        ],
    )
    assert evaluate_bot(bot, m, mode="live")


def test_first_half_goals_condition():
    m = attach_favorite_fields(
        {
            "minute": 28,
            "status": "1H",
            "home_score": 0,
            "away_score": 0,
            "score": "0-0",
            "best_ev_pct": 6,
        }
    )
    bot = BotConfig(
        name="HT 0-0",
        mode="live",
        conditions=[
            {"field": "first_half_goals", "operator": "lte", "value": 0},
            {"field": "is_first_half", "operator": "eq", "value": True},
        ],
    )
    assert evaluate_bot(bot, m, mode="live")