"""Testes — enrich live (xG, cartões) para bots."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.evaluator import evaluate_bot, evaluate_bots_for_scan
from bots.live_enrich import (
    any_bot_needs_live_stats,
    attach_live_stats_fields,
    bot_conditions_need_live_stats,
    enrich_live_ranked_for_bots,
)
from bots.types import BotConfig
from discovery.match_stats_types import MatchLiveStatsBundle, TeamLiveStats


def _bundle(**kwargs) -> MatchLiveStatsBundle:
    home = TeamLiveStats(
        team="Casa",
        xg=1.2,
        possession_pct=58,
        corners=5,
        yellow_cards=2,
        red_cards=0,
    )
    away = TeamLiveStats(
        team="Fora",
        xg=0.5,
        possession_pct=42,
        corners=3,
        yellow_cards=1,
        red_cards=1,
    )
    defaults = {"fixture_id": 99, "home": home, "away": away, "xg_source": "api"}
    defaults.update(kwargs)
    return MatchLiveStatsBundle(**defaults)


def test_bot_conditions_need_live_stats():
    assert bot_conditions_need_live_stats([{"field": "xg_diff"}])
    assert bot_conditions_need_live_stats([{"field": "total_yellow_cards"}])
    assert not bot_conditions_need_live_stats([{"field": "minute"}])
    assert not bot_conditions_need_live_stats([])


def test_any_bot_needs_live_stats():
    live_bot = BotConfig(
        name="xG",
        mode="live",
        active=True,
        conditions=[{"field": "xg_diff", "operator": "gte", "value": 0.3}],
    )
    prematch_bot = BotConfig(
        name="Pre",
        mode="prematch",
        active=True,
        conditions=[{"field": "xg_diff", "operator": "gte", "value": 0.3}],
    )
    inactive = BotConfig(
        name="Off",
        mode="live",
        active=False,
        conditions=[{"field": "total_cards", "operator": "gte", "value": 2}],
    )
    assert any_bot_needs_live_stats([live_bot])
    assert not any_bot_needs_live_stats([prematch_bot])
    assert not any_bot_needs_live_stats([inactive])


def test_attach_live_stats_fields():
    match = {"home": "Benfica", "away": "Sporting", "fixture_id": 99}
    out = attach_live_stats_fields(match, _bundle())

    assert out["home_xg"] == 1.2
    assert out["away_xg"] == 0.5
    assert out["total_xg"] == 1.7
    assert out["xg_diff"] == 0.7
    assert out["home_possession_pct"] == 58
    assert out["total_corners"] == 8
    assert out["total_yellow_cards"] == 3
    assert out["total_red_cards"] == 1
    assert out["total_cards"] == 4
    assert out["live_stats"]["fixture_id"] == 99


def test_enrich_skips_without_live_stats_conditions():
    ranked = [{"fixture_id": 1, "minute": 30}]
    bot = BotConfig(name="Min", mode="live", conditions=[{"field": "minute", "operator": "gte", "value": 20}])

    with patch("discovery.api_football_client.ApiFootballClient") as mock_client:
        out = enrich_live_ranked_for_bots(ranked, bots=[bot])
        mock_client.assert_not_called()

    assert out == ranked


def test_enrich_fetches_when_needed():
    ranked = [{"fixture_id": 42, "minute": 35, "best_ev_pct": 6}]
    bot = BotConfig(
        name="Cards",
        mode="live",
        active=True,
        conditions=[{"field": "total_yellow_cards", "operator": "gte", "value": 2}],
    )
    bundle = _bundle()

    mock_client = MagicMock()
    mock_client.is_configured = True

    with (
        patch("discovery.api_football_client.ApiFootballClient", return_value=mock_client),
        patch("discovery.match_stats.fetch_match_live_stats", return_value=bundle) as fetch,
    ):
        out = enrich_live_ranked_for_bots(ranked, bots=[bot])

    fetch.assert_called_once_with(mock_client, 42)
    assert out[0]["total_yellow_cards"] == 3
    assert out[0]["xg_diff"] == 0.7


def test_evaluate_bot_xg_and_cards_conditions():
    match = {
        "minute": 30,
        "best_ev_pct": 6,
        "xg_diff": 0.7,
        "home_possession_pct": 58,
        "total_yellow_cards": 3,
    }
    xg_bot = BotConfig(
        name="Pressão",
        mode="live",
        conditions=[
            {"field": "xg_diff", "operator": "gte", "value": 0.4},
            {"field": "home_possession_pct", "operator": "gte", "value": 52},
        ],
    )
    cards_bot = BotConfig(
        name="Intenso",
        mode="live",
        conditions=[{"field": "total_yellow_cards", "operator": "gte", "value": 3}],
    )

    assert evaluate_bot(xg_bot, match, mode="live")
    assert evaluate_bot(cards_bot, match, mode="live")
    assert not evaluate_bot(cards_bot, {**match, "total_yellow_cards": 2}, mode="live")


def test_evaluate_bots_for_scan_live_enriches_pool():
    ranked = [{"fixture_id": 7, "minute": 40, "best_ev_pct": 8}]
    bot = BotConfig(
        name="xG live",
        mode="live",
        active=True,
        conditions=[{"field": "total_xg", "operator": "gte", "value": 1.5}],
    )
    bundle = _bundle()

    mock_client = MagicMock()
    mock_client.is_configured = True

    with (
        patch("discovery.api_football_client.ApiFootballClient", return_value=mock_client),
        patch("discovery.match_stats.fetch_match_live_stats", return_value=bundle),
    ):
        hits = evaluate_bots_for_scan(ranked, mode="live", bots=[bot])

    assert len(hits) == 1
    assert hits[0]["bot_id"] == bot.id
    assert hits[0]["matches"][0]["total_xg"] == 1.7