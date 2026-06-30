"""Testes — snapshots de estatísticas ao vivo."""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_record_and_load_stats_history(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    import config.data_paths as dp
    import discovery.stats_snapshots as snaps

    dp.DATA_DIR = tmp_path
    dp.LIVE_STATS_SNAPSHOTS = tmp_path / "live_stats_snapshots.jsonl"
    snaps.LIVE_STATS_SNAPSHOTS = dp.LIVE_STATS_SNAPSHOTS

    from discovery.match_stats_types import MatchLiveStatsBundle, TeamLiveStats

    bundle = MatchLiveStatsBundle(
        fixture_id=99,
        home=TeamLiveStats(team="A", xg=1.1, possession_pct=55),
        away=TeamLiveStats(team="B", xg=0.4, possession_pct=45),
        xg_source="estimated",
    )
    snaps.record_stats_snapshot(bundle, minute=30, home_score=1, away_score=0)
    snaps.record_stats_snapshot(bundle, minute=45, home_score=1, away_score=0)

    history = snaps.load_stats_history(99)
    assert len(history) == 2
    assert history[0]["minute"] == 30
    assert history[1]["home_xg"] == 1.1

    lines = dp.LIVE_STATS_SNAPSHOTS.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["fixture_id"] == 99