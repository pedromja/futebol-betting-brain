"""Testes — cache de scans e optimizações de fluxo."""

import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.evaluator import evaluate_bots_for_scan
from bots.types import BotConfig
from scanner import scan_cache


def test_prematch_cache_hit():
    scan_cache.clear()
    key = scan_cache.prematch_key(hours=12, min_score=0.55, bankroll=100.0)
    payload = {"ranked": [{"home": "A", "away": "B"}], "scanned_at": "t1"}
    scan_cache.set_prematch(key, payload)

    hit = scan_cache.get_prematch(key, ttl=60.0)
    assert hit is not None
    assert hit["cache_hit"] is True
    assert hit["ranked"][0]["home"] == "A"


def test_prematch_cache_expires():
    scan_cache.clear()
    key = scan_cache.prematch_key(hours=12, min_score=0.55, bankroll=None)
    scan_cache.set_prematch(key, {"ranked": []})
    entry = scan_cache._store[key]
    scan_cache._store[key] = (time.time() - 200, entry[1])
    assert scan_cache.get_prematch(key, ttl=150.0) is None


def test_evaluate_bots_filters_by_mode():
    ranked = [{"best_ev_pct": 5, "best_market": "Over 2.5", "odd": 1.9, "minute": 30}]
    live_bot = BotConfig(
        name="Live",
        mode="live",
        active=True,
        conditions=[{"field": "minute", "operator": "gte", "value": 20}],
    )
    pre_bot = BotConfig(
        name="Pre",
        mode="prematch",
        active=True,
        conditions=[{"field": "best_ev_pct", "operator": "gte", "value": 3}],
    )

    with patch("bots.live_enrich.enrich_live_ranked_for_bots", side_effect=lambda r, **_: r) as live_enrich:
        live_hits = evaluate_bots_for_scan(ranked, mode="live", bots=[live_bot, pre_bot])
        live_enrich.assert_called_once()

    assert len(live_hits) == 1
    assert live_hits[0]["mode"] == "live"

    with patch("bots.live_enrich.enrich_prematch_ranked_for_bots", side_effect=lambda r, **_: r) as pre_enrich:
        pre_hits = evaluate_bots_for_scan(ranked, mode="prematch", bots=[live_bot, pre_bot])
        pre_enrich.assert_called_once()

    assert len(pre_hits) == 1
    assert pre_hits[0]["mode"] == "prematch"


def test_underdog_warm_fetches_standings_once():
    from bots.underdog_table import clear_underdog_session_cache, warm_underdog_league

    clear_underdog_session_cache()
    table = [{"position": 1, "team": {"name": "A"}}]

    with patch("bots.underdog_table.fetch_standings", return_value=table) as fetch:
        with patch("bots.underdog_table._ensure_league_profiles"):
            with patch("bots.underdog_table._progress_window", return_value=(True, 50.0)):
                warm_underdog_league("Primeira Liga", football_data_key="k")
                warm_underdog_league("Primeira Liga", football_data_key="k")

    fetch.assert_called_once()
    clear_underdog_session_cache()