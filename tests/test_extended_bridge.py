"""Testes — mercados avançados (extended bridge)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.match_stats_types import MatchLiveStatsBundle, TeamLiveStats
from live.extended_bridge import analyze_extended_markets, build_live_context


def _sample_bundle() -> MatchLiveStatsBundle:
    return MatchLiveStatsBundle(
        fixture_id=12345,
        home=TeamLiveStats(
            team="Brasil",
            possession_pct=68,
            shots_total=14,
            shots_on=6,
            corners=7,
            xg=1.42,
            xg_source="estimated",
        ),
        away=TeamLiveStats(
            team="Japão",
            possession_pct=32,
            shots_total=5,
            shots_on=1,
            corners=2,
            xg=0.28,
            xg_source="estimated",
        ),
        xg_source="estimated",
    )


def test_build_live_context_remaining_minutes():
    ctx = build_live_context(_sample_bundle(), home_score=1, away_score=1, minute=86, injury_time=4)
    assert ctx.home_score == 1
    assert ctx.remaining_minutes == 8.0
    assert ctx.home_pressure == "high"


def test_analyze_extended_markets_returns_picks():
    picks = analyze_extended_markets(
        _sample_bundle(),
        home_score=1,
        away_score=1,
        minute=86,
        home_name="Brasil",
        away_name="Japão",
        injury_time=4,
    )
    assert isinstance(picks, list)
    assert picks
    first = picks[0]
    assert "label" in first
    assert "ev_pct" in first
    assert "odd" in first