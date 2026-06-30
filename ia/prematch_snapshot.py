"""Snapshot pré-jogo por jogo — base para IA live (ESPN gameId)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.data_paths import IA_PREMATCH_SNAPSHOTS, ensure_data_dir
from discovery.fixture_types import UpcomingFixture

SNAPSHOT_VERSION = 1


def _match_key(fixture: UpcomingFixture | object) -> str:
    eid = getattr(fixture, "espn_event_id", "") or ""
    if eid:
        return f"espn:{eid}"
    home = getattr(fixture, "home", "")
    away = getattr(fixture, "away", "")
    kick = (getattr(fixture, "kickoff", "") or "").strip()
    return f"{home}|{away}|{kick}".lower()


def _infer_favorite(odds_hint: dict | None) -> str | None:
    oh = odds_hint or {}
    home = oh.get("home_win") or oh.get("home_odd") or oh.get("home")
    away = oh.get("away_win") or oh.get("away_odd") or oh.get("away")
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


def _favorite_names(
    home: str,
    away: str,
    favorite_side: str | None,
) -> tuple[str | None, str | None]:
    if favorite_side == "home":
        return home, away
    if favorite_side == "away":
        return away, home
    return None, None


def _build_assumptions(
    *,
    home: str,
    away: str,
    odds_hint: dict | None,
    best_market: str | None,
    best_ev: float | None,
    motivation: dict | None,
) -> dict:
    fav_side = _infer_favorite(odds_hint)
    fav_name, underdog = _favorite_names(home, away, fav_side)
    ev_pct = round(float(best_ev) * 100, 2) if best_ev is not None else None
    return {
        "favorite_side": fav_side,
        "favorite_name": fav_name,
        "underdog_name": underdog,
        "expected_market": best_market,
        "expected_ev_pct": ev_pct,
        "motivation_ok": bool((motivation or {}).get("should_bet", True)),
    }


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

    assumptions = _build_assumptions(
        home=fixture.home,
        away=fixture.away,
        odds_hint=fixture.odds_hint,
        best_market=ranked_match.best_market,
        best_ev=ranked_match.best_ev,
        motivation=ranked_match.motivation,
    )

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
        "prematch_assumptions": assumptions,
    }


def build_snapshot_from_live_fixture(fixture: object) -> dict | None:
    """Snapshot mínimo quando o jogo entrou live sem scan prévio."""
    eid = str(getattr(fixture, "espn_event_id", "") or "").strip()
    if not eid:
        return None
    home = str(getattr(fixture, "home", "") or "")
    away = str(getattr(fixture, "away", "") or "")
    odds_hint = dict(getattr(fixture, "odds_hint", None) or {})
    assumptions = _build_assumptions(
        home=home,
        away=away,
        odds_hint=odds_hint,
        best_market=None,
        best_ev=None,
        motivation=None,
    )
    return {
        "version": SNAPSHOT_VERSION,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scanned_at": None,
        "match_key": f"espn:{eid}",
        "espn_event_id": eid,
        "espn_league_code": getattr(fixture, "espn_league_code", "") or None,
        "home": home,
        "away": away,
        "league": getattr(fixture, "league", "") or "",
        "stage": getattr(fixture, "stage", "") or "",
        "kickoff": getattr(fixture, "kickoff", "") or "",
        "source": "live_fallback",
        "odds_hint": odds_hint,
        "rank": None,
        "should_bet": None,
        "block_reason": None,
        "best_ev": None,
        "best_market": None,
        "best_score": None,
        "effective_min_score": None,
        "top_markets": [],
        "stake_plan": None,
        "transfermarkt": None,
        "motivation": None,
        "competition_progress": None,
        "prematch_assumptions": assumptions,
    }


def prematch_public_summary(snapshot: dict | None) -> dict | None:
    if not snapshot:
        return None
    pa = snapshot.get("prematch_assumptions") or {}
    return {
        "favorite_name": pa.get("favorite_name"),
        "underdog_name": pa.get("underdog_name"),
        "favorite_side": pa.get("favorite_side"),
        "expected_market": pa.get("expected_market") or snapshot.get("best_market"),
        "expected_ev_pct": pa.get("expected_ev_pct"),
        "best_score": snapshot.get("best_score"),
        "should_bet": snapshot.get("should_bet"),
        "source": snapshot.get("source"),
        "saved_at": snapshot.get("saved_at"),
        "top_markets": (snapshot.get("top_markets") or [])[:3],
    }


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


def upsert_snapshot(snapshot: dict) -> None:
    path = IA_PREMATCH_SNAPSHOTS
    key = str(snapshot.get("match_key") or "")
    if not key:
        return
    by_key: dict[str, dict] = {}
    for row in _read_all(path):
        mk = str(row.get("match_key") or "")
        if mk:
            by_key[mk] = row
    existing = by_key.get(key)
    if existing and existing.get("source") != "live_fallback":
        snap = dict(existing)
        snap.update({k: v for k, v in snapshot.items() if v is not None})
        if snapshot.get("source") == "live_fallback":
            snap["source"] = existing.get("source") or snapshot.get("source")
        by_key[key] = snap
    else:
        by_key[key] = snapshot
    ordered = sorted(
        by_key.values(),
        key=lambda r: str(r.get("saved_at") or ""),
        reverse=True,
    )
    _write_all(path, ordered[:500])


def save_snapshots_from_scan(result: Any) -> int:
    """Grava/atualiza snapshots para jogos com espn_event_id no resultado do scan."""
    saved = 0
    scanned_at = getattr(result, "scanned_at", None)
    for ranked in getattr(result, "ranked", []) or []:
        fixture = ranked.fixture
        if not fixture.espn_event_id:
            continue
        snap = build_snapshot_from_ranked(ranked, scanned_at=scanned_at)
        upsert_snapshot(snap)
        saved += 1
    return saved


def ensure_snapshot_for_live(fixture: object) -> dict | None:
    """Garante snapshot para análise live — carrega ou cria fallback."""
    eid = str(getattr(fixture, "espn_event_id", "") or "").strip()
    if not eid:
        return None
    existing = load_snapshot_by_espn_event(eid)
    if existing:
        return existing
    snap = build_snapshot_from_live_fixture(fixture)
    if snap:
        upsert_snapshot(snap)
    return snap


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