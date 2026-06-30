"""Benchmark rápido — scan cache, bots e underdog batch."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bots.evaluator import evaluate_bots_for_scan
from bots.live_enrich import enrich_prematch_ranked_for_bots
from bots.types import BotConfig
from history.bot_signals import append_bot_hits
from scanner import scan_cache


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


def bench_scan_cache(iterations: int = 5000) -> float:
    scan_cache.clear()
    key = scan_cache.prematch_key(hours=12, min_score=0.55, bankroll=100.0)
    scan_cache.set_prematch(key, {"ranked": [{"home": "A"}] * 80, "scanned_at": "t"})
    t0 = time.perf_counter()
    for _ in range(iterations):
        scan_cache.get_prematch(key)
    return _ms(t0)


def bench_underdog_enrich(matches: int = 60) -> tuple[float, float]:
    ranked = [
        {
            "home": f"Home{i}",
            "away": f"Away{i}",
            "league": "Primeira Liga" if i % 3 == 0 else "Premier League",
            "best_ev_pct": 5,
            "best_market": "Over 1.5",
            "odd": 1.85,
            "competition_progress": {"progress_pct": 50},
        }
        for i in range(matches)
    ]
    bot = BotConfig(
        name="UD",
        mode="prematch",
        active=True,
        conditions=[
            {"field": "underdog_progress_ok", "operator": "eq", "value": True},
            {"field": "underdog_scenario", "operator": "eq", "value": "raca"},
        ],
    )
    profile = {
        "scenario": "raca",
        "significant": True,
        "rate_vs_strong_pct": 42.0,
        "rate_vs_weak_pct": 18.0,
        "games_vs_strong": 10,
        "games_vs_weak": 10,
        "z_score": 2.1,
        "p_value": 0.03,
    }

    def _fake_attach(match, **kwargs):
        out = {**match}
        out.update(
            {
                "underdog_scenario": "raca",
                "underdog_significant": True,
                "underdog_progress_ok": True,
                "underdog_ia_alert": "easy_score",
                "underdog_ia_play_allowed": True,
                "underdog_ia_active": True,
            }
        )
        return out

    with (
        patch("bots.live_enrich.attach_underdog_ia_fields", side_effect=_fake_attach),
        patch("bots.underdog_table.warm_underdog_league") as warm,
    ):
        t0 = time.perf_counter()
        enrich_prematch_ranked_for_bots(ranked, bots=[bot])
        cold = _ms(t0)
        warm_calls = warm.call_count

        t0 = time.perf_counter()
        enrich_prematch_ranked_for_bots(ranked, bots=[bot])
        warm2 = _ms(t0)

    return cold, warm2, warm_calls


def bench_bot_eval(matches: int = 80, bots_n: int = 5) -> float:
    ranked = [
        {
            "home": f"H{i}",
            "away": f"A{i}",
            "league": "Liga",
            "best_ev_pct": 6,
            "best_market": "Over 2.5",
            "odd": 1.9,
            "kickoff": "2026-06-30T15:00:00",
        }
        for i in range(matches)
    ]
    bots = [
        BotConfig(
            name=f"B{i}",
            mode="prematch",
            active=True,
            conditions=[{"field": "best_ev_pct", "operator": "gte", "value": 4 + i}],
        )
        for i in range(bots_n)
    ]
    with patch("bots.live_enrich.enrich_prematch_ranked_for_bots", side_effect=lambda r, **_: r):
        t0 = time.perf_counter()
        evaluate_bots_for_scan(ranked, mode="prematch", bots=bots)
    return _ms(t0)


def main() -> None:
    print("=== Bench plataforma (sintético) ===\n")
    cache_ms = bench_scan_cache()
    print(f"Scan cache: 5000 hits em {cache_ms} ms")

    cold, hot, leagues = bench_underdog_enrich(60)
    print(f"Underdog enrich 60 jogos: 1ª={cold} ms, 2ª={hot} ms (warm ligas={leagues})")

    bot_ms = bench_bot_eval(80, 5)
    print(f"Bots eval 80×5: {bot_ms} ms")

    print("\nOK — optimizações activas (cache, batch underdog, filtro modo).")


if __name__ == "__main__":
    main()