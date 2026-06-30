"""Snapshot pré-jogo por jogo — base para IA live (ESPN gameId)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.data_paths import IA_PREMATCH_SNAPSHOTS, ensure_data_dir
from discovery.fixture_types import UpcomingFixture

SNAPSHOT_VERSION = 1


def _match_key(fixture: UpcomingFixture) -> str:
    if fixture.espn_event_id:
        return f"espn:{fixture.espn_event_id}"
    kick = (fixture.kickoff or "").strip()
    return f"{fixture.home}|{fixture.away}|{kick}".lower()


def build_snapshot_from_ranked(
    ranked_match: Any,
    *,
    scanned_at: str | None = None,
) -> dict:
    """Constrói snapshot a partir de RankedMatch do scan."""
    fixture: UpcomingFixture = ranked_match.fixture
    decision = ranked_match.decision
    rec = decision.recommendation if decision else None
    best = rec.best_market if rec else None

    top_markets = []
    if rec:
        top_markets = [
            {
                "label": m.label,
                "score": round(float(m.total_score), 4),
                "ev": round(float(m.expected_value), 4),
                "odd": float(m.odd) if m.odd else None,
            }
            for m in (rec.all_markets or [])[:5]
        ]

    stake = ranked_match.stake_plan
    stake_dict = None
    if stake is not None:
        stake_dict = {
            "level": stake.level,
            "label": stake.label,
            "bankroll_pct": stake.bankroll_pct,
            "suggested_amount": stake.suggested_amount,
        }

    return {
        "version": SNAPSHOT_VERSION,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scanned_at": scanned_at,
        "match_key": _match_key(fixture),
        "espn_event_id": fixture.espn_event_id or None,
        "espn_league_code": fixture.espn_league_code or None,
        "home": fixture.home,
        "away": fixture.away,
        "league": fixture.league,
        "stage": fixture.stage,
        "kickoff": fixture.kickoff,
        "source": fixture.source,
        "odds_hint": dict(fixture.odds_hint or {}),
        "rank": ranked_match.rank,
        "should_bet": bool(ranked_match.should_bet),
        "block_reason": ranked_match.block_reason,
        "best_ev": round(float(ranked_match.best_ev), 4),
        "best_market": ranked_match.best_market,
        "best_score": round(float(ranked_match.best_score), 4),
        "effective_min_score": round(float(ranked_match.effective_min_score), 4),
        "top_markets": top_markets,
        "stake_plan": stake_dict,
        "transfermarkt": ranked_match.transfermarkt,
        "motivation": ranked_match.motivation,
        "competition_progress": ranked_match.competition_progress,
        "prematch_assumptions": {
            "favorite_side": _infer_favorite(fixture.odds_hint),
            "expected_market": ranked_match.best_market,
            "expected_ev_pct": round(float(ranked_match.best_ev) * 100, 2),
            "motivation_ok": bool((ranked_match.motivation or {}).get("should_bet", True)),
        },
    }


def _infer_favorite(odds_hint: dict | None) -> str | None:
    oh = odds_hint or {}
    home = oh.get("home_odd") or oh.get("home")
    away = oh.get("away_odd") or oh.get("away")
    try:
        h = float(home) if home else None
        a = float(away) if away else None
    except (TypeError, ValueError):
        return None
    if h and a:
        if h < a:
            return "home"
        if a < h:
            return "away"
    return None


def _read_all(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _write_all(path: Path, rows: list[dict]) -> None:
    ensure_data_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def save_snapshots_from_scan(result: Any) -> int:
    """Grava/atualiza snapshots para jogos com espn_event_id no resultado do scan."""
    path = IA_PREMATCH_SNAPSHOTS
    existing = _read_all(path)
    by_key: dict[str, dict] = {}
    for row in existing:
        key = str(row.get("match_key") or "")
        if key:
            by_key[key] = row

    saved = 0
    scanned_at = getattr(result, "scanned_at", None)
    for ranked in getattr(result, "ranked", []) or []:
        fixture = ranked.fixture
        if not fixture.espn_event_id:
            continue
        snap = build_snapshot_from_ranked(ranked, scanned_at=scanned_at)
        by_key[snap["match_key"]] = snap
        saved += 1

    if saved:
        ordered = sorted(
            by_key.values(),
            key=lambda r: str(r.get("saved_at") or ""),
            reverse=True,
        )
        _write_all(path, ordered[:500])
    return saved


def load_snapshot_by_espn_event(event_id: str) -> dict | None:
    eid = str(event_id or "").strip()
    if not eid:
        return None
    for row in _read_all(IA_PREMATCH_SNAPSHOTS):
        if str(row.get("espn_event_id") or "") == eid:
            return row
    return None


def load_snapshot_by_match_key(match_key: str) -> dict | None:
    key = (match_key or "").strip().lower()
    if not key:
        return None
    for row in _read_all(IA_PREMATCH_SNAPSHOTS):
        if str(row.get("match_key") or "").lower() == key:
            return row
    return None


def list_snapshots(*, limit: int = 50) -> list[dict]:
    rows = _read_all(IA_PREMATCH_SNAPSHOTS)
    rows.sort(key=lambda r: str(r.get("saved_at") or ""), reverse=True)
    return rows[: max(1, limit)]