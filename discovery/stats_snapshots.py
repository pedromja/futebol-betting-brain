"""Histórico de snapshots de estatísticas ao vivo — mini-gráficos na PWA."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from config.data_paths import LIVE_STATS_SNAPSHOTS, ensure_data_dir
from discovery.match_stats_types import MatchLiveStatsBundle

_MAX_POINTS = 40
_MAX_FILE_LINES = 5000


def _snapshot_row(
    bundle: MatchLiveStatsBundle,
    *,
    minute: int | None,
    home_score: int | None,
    away_score: int | None,
) -> dict:
    return {
        "fixture_id": bundle.fixture_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "minute": minute,
        "home_score": home_score,
        "away_score": away_score,
        "home_xg": bundle.home.xg,
        "away_xg": bundle.away.xg,
        "home_possession_pct": bundle.home.possession_pct,
        "away_possession_pct": bundle.away.possession_pct,
        "home_shots_on": bundle.home.shots_on,
        "away_shots_on": bundle.away.shots_on,
        "home_corners": bundle.home.corners,
        "away_corners": bundle.away.corners,
        "total_corners": (bundle.home.corners or 0) + (bundle.away.corners or 0)
        if bundle.home.corners is not None and bundle.away.corners is not None
        else None,
        "home_yellow_cards": bundle.home.yellow_cards,
        "away_yellow_cards": bundle.away.yellow_cards,
        "total_cards": (
            (bundle.home.yellow_cards or 0)
            + (bundle.away.yellow_cards or 0)
            + (bundle.home.red_cards or 0)
            + (bundle.away.red_cards or 0)
        ),
        "xg_source": bundle.xg_source,
    }


def record_stats_snapshot(
    bundle: MatchLiveStatsBundle,
    *,
    minute: int | None = None,
    home_score: int | None = None,
    away_score: int | None = None,
) -> dict:
    """Grava um ponto no histórico e devolve a linha escrita."""
    ensure_data_dir()
    row = _snapshot_row(
        bundle,
        minute=minute,
        home_score=home_score,
        away_score=away_score,
    )
    with LIVE_STATS_SNAPSHOTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def load_stats_history(fixture_id: int, *, limit: int = _MAX_POINTS) -> list[dict]:
    """Últimos N snapshots de um fixture (ordem cronológica)."""
    if fixture_id <= 0 or not LIVE_STATS_SNAPSHOTS.exists():
        return []

    safe_limit = max(1, min(limit, _MAX_POINTS))
    rows: list[dict] = []
    try:
        lines = LIVE_STATS_SNAPSHOTS.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    for line in lines[-_MAX_FILE_LINES:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if int(row.get("fixture_id") or 0) != fixture_id:
            continue
        rows.append(row)

    if len(rows) > safe_limit:
        rows = rows[-safe_limit:]
    return rows


def load_snapshot_hints_batch(
    fixture_ids: list[int],
    *,
    tail_lines: int = _MAX_FILE_LINES,
) -> dict[int, tuple[dict | None, dict | None]]:
    """
    Últimos dois snapshots por fixture — uma passagem no ficheiro.
    Usado para temperatura na grelha live sem pedidos API.
    """
    wanted = {int(x) for x in fixture_ids if int(x) > 0}
    if not wanted or not LIVE_STATS_SNAPSHOTS.exists():
        return {}

    acc: dict[int, list[dict]] = {fid: [] for fid in wanted}
    try:
        lines = LIVE_STATS_SNAPSHOTS.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    for line in lines[-tail_lines:]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        fid = int(row.get("fixture_id") or 0)
        if fid not in wanted:
            continue
        bucket = acc[fid]
        if bucket and int(bucket[-1].get("minute") or -1) == int(row.get("minute") or -2):
            bucket[-1] = row
        else:
            bucket.append(row)
        if len(bucket) > 2:
            acc[fid] = bucket[-2:]

    out: dict[int, tuple[dict | None, dict | None]] = {}
    for fid, rows in acc.items():
        if not rows:
            continue
        if len(rows) == 1:
            out[fid] = (None, rows[0])
        else:
            out[fid] = (rows[-2], rows[-1])
    return out