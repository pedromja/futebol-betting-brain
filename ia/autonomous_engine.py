"""Motor IA autónomo — ESPN live + snapshot pré + LLM xAI."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from bots.catalog import MARKET_OPTIONS
from discovery.espn_commentary import fetch_espn_commentary
from discovery.espn_live_scanner import EspnLiveScanner
from discovery.espn_live_stats import fetch_espn_live_stats
from discovery.live_fixture_types import LiveFixture
from ia.llm_client import IaLlmClient, normalize_llm_output
from ia.market_ev_gate import apply_ev_gate
from ia.prematch_snapshot import (
    ensure_snapshot_for_live,
    load_snapshot_by_espn_event,
    prematch_public_summary,
)
from ia.signals import append_ia_signals, build_signal_record, recent_signals_for_game
from ia.stake_policy import apply_stake_policy, to_public_tip
from ia.tip_gate import current_phase_window, filter_tips

_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL_SEC = 90

_VALID_MARKETS = {m.lower() for m in MARKET_OPTIONS}


def _fixture_dict(fx: LiveFixture) -> dict:
    return {
        "espn_event_id": fx.espn_event_id,
        "espn_league_code": fx.espn_league_code,
        "home": fx.home,
        "away": fx.away,
        "league": fx.league,
        "stage": fx.stage,
        "minute": fx.minute,
        "injury_time": fx.injury_time,
        "status_short": fx.status_short,
        "score": f"{fx.home_score}-{fx.away_score}",
        "home_score": fx.home_score,
        "away_score": fx.away_score,
        "odds_hint": fx.odds_hint,
    }


def _live_stats_dict(fx: LiveFixture) -> dict | None:
    bundle = fetch_espn_live_stats(
        fx.espn_league_code,
        fx.espn_event_id,
        home_name=fx.home,
        away_name=fx.away,
    )
    if not bundle:
        return None
    return {
        "home": bundle.home.to_dict() if hasattr(bundle.home, "to_dict") else {},
        "away": bundle.away.to_dict() if hasattr(bundle.away, "to_dict") else {},
        "xg_source": bundle.xg_source,
    }


def _pattern_context(fx: LiveFixture, stats: dict | None) -> dict:
    match = _fixture_dict(fx)
    if stats:
        h = stats.get("home") or {}
        a = stats.get("away") or {}
        match.update(
            {
                "home_corners": h.get("corners"),
                "away_corners": a.get("corners"),
                "home_shots_on": h.get("shots_on"),
                "away_shots_on": a.get("shots_on"),
                "home_possession_pct": h.get("possession_pct"),
                "away_possession_pct": a.get("possession_pct"),
                "home_yellow_cards": h.get("yellow_cards"),
                "away_yellow_cards": a.get("yellow_cards"),
            }
        )
    try:
        from bots.pattern_discrepancy import attach_pattern_fields

        enriched = attach_pattern_fields(match)
        return {
            "pattern_discrepancy_score": enriched.get("pattern_discrepancy_score"),
            "pattern_discrepancy_trend": enriched.get("pattern_discrepancy_trend"),
            "pattern_alert": enriched.get("pattern_alert"),
            "pattern_summary": enriched.get("pattern_summary"),
            "pattern_situation": enriched.get("pattern_situation"),
        }
    except Exception:
        return {}


def _phase_windows_state(minute: int) -> list[dict]:
    windows = (
        ("J1", 15, 30),
        ("J2", 30, 45),
        ("J3", 60, 75),
        ("J4", 75, 120),
    )
    current = current_phase_window(minute)
    out: list[dict] = []
    for code, start, end in windows:
        status = "future"
        if current == code:
            status = "active"
        elif minute >= end:
            status = "past"
        out.append({"code": code, "start": start, "end": end, "status": status})
    return out


def _validate_market(label: str) -> bool:
    blob = (label or "").strip().lower()
    if blob in _VALID_MARKETS:
        return True
    return any(blob in m or m in blob for m in _VALID_MARKETS)


def build_llm_context(fx: LiveFixture) -> dict:
    commentary = fetch_espn_commentary(fx.espn_league_code, fx.espn_event_id)
    prematch = ensure_snapshot_for_live(fx) or {}
    stats = _live_stats_dict(fx)
    pattern = _pattern_context(fx, stats)

    def _comment_row(e: object) -> dict:
        return {
            "minute": e.minute,
            "minute_display": e.minute_display,
            "event_type": e.event_type,
            "team": e.team,
            "text": e.text,
        }

    recent_comments = []
    commentary_timeline = []
    if commentary:
        recent_comments = [_comment_row(e) for e in commentary.entries[-10:]]
        commentary_timeline = [_comment_row(e) for e in commentary.entries[-20:]]

    minute = fx.minute
    if commentary and commentary.minute > minute:
        minute = commentary.minute

    return {
        "fixture": _fixture_dict(fx),
        "minute": minute,
        "phase_window": current_phase_window(minute),
        "prematch_snapshot": prematch,
        "prematch_assumptions": prematch.get("prematch_assumptions") or {},
        "live_stats": stats,
        "pattern_discrepancy": pattern,
        "recent_commentary": recent_comments,
        "commentary_timeline": commentary_timeline,
        "key_events": [
            {
                "minute": e.minute,
                "event_type": e.event_type,
                "text": e.text,
                "scoring_play": e.scoring_play,
            }
            for e in (commentary.key_events[-8:] if commentary else [])
        ],
        "valid_markets": MARKET_OPTIONS[:20],
    }


def analyze_game(
    fx: LiveFixture,
    *,
    llm: IaLlmClient | None = None,
    force: bool = False,
    include_context: bool = False,
) -> dict:
    """Analisa um jogo in-play e devolve payload público."""
    cache_key = f"{fx.espn_event_id}:{fx.minute}"
    now = time.time()
    if not force and cache_key in _CACHE:
        ts, payload = _CACHE[cache_key]
        if now - ts < _CACHE_TTL_SEC:
            return payload

    context = build_llm_context(fx)
    prematch = context.get("prematch_snapshot") or {}
    minute = int(context.get("minute") or fx.minute or 0)
    client = llm or IaLlmClient()
    raw = client.analyze_live(context)
    normalized = normalize_llm_output(raw)

    recent = recent_signals_for_game(fx.espn_event_id)
    accepted, rejected = filter_tips(
        normalized["tips"],
        current_minute=minute,
        recent_signals=recent,
    )

    final_tips: list[dict] = []
    to_log: list[dict] = []
    for tip in accepted:
        if not _validate_market(tip.get("market", "")):
            rejected.append({**tip, "reject_reason": "mercado_invalido"})
            continue
        ev_tip, ev_reject = apply_ev_gate(
            tip,
            fx.odds_hint,
            home_score=fx.home_score,
            away_score=fx.away_score,
            minute=minute,
        )
        if ev_reject or not ev_tip:
            rejected.append({**tip, "reject_reason": ev_reject or "ev_gate"})
            continue
        stamped = apply_stake_policy(ev_tip, market=ev_tip.get("market"))
        final_tips.append(to_public_tip(stamped))
        to_log.append(
            build_signal_record(
                stamped,
                fixture=_fixture_dict(fx),
                commentary_meta={
                    "minute": minute,
                    "llm_status": normalized.get("llm_status"),
                },
            )
        )

    if to_log:
        append_ia_signals(to_log)

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "espn_event_id": fx.espn_event_id,
        "espn_league_code": fx.espn_league_code,
        "home": fx.home,
        "away": fx.away,
        "league": fx.league,
        "minute": minute,
        "phase_window": current_phase_window(minute),
        "score": f"{fx.home_score}-{fx.away_score}",
        "llm_status": normalized.get("llm_status"),
        "llm_model": normalized.get("llm_model"),
        "llm_model_reason": normalized.get("llm_model_reason"),
        "tips": final_tips,
        "action_forecasts": normalized.get("action_forecasts") or [],
        "rejected_tips": rejected,
        "prematch_snapshot": bool(prematch),
        "prematch_summary": prematch_public_summary(prematch),
        "pattern_discrepancy": context.get("pattern_discrepancy") or {},
        "commentary_available": bool(context.get("recent_commentary")),
        "commentary_timeline": context.get("commentary_timeline") or [],
        "key_events": context.get("key_events") or [],
        "phase_windows": _phase_windows_state(minute),
        "history": [
            {
                "market": r.get("market"),
                "minute": r.get("minute"),
                "confidence_pct": r.get("confidence_pct"),
                "reasoning_pt": r.get("reasoning_pt"),
                "prematch_alignment": r.get("prematch_alignment"),
                "quote_en": r.get("quote_en"),
                "logged_at": r.get("logged_at"),
            }
            for r in recent[:12]
        ],
    }
    if include_context:
        payload["llm_context"] = context
        payload["llm_system_prompt_excerpt"] = (
            "reasoning_pt (PT) + quote_en (ESPN EN) + action_forecasts por equipa"
        )
    _CACHE[cache_key] = (now, payload)
    return payload


def list_live_games() -> list[dict]:
    scanner = EspnLiveScanner()
    games: list[dict] = []
    for fx in scanner.scan():
        if not fx.espn_event_id:
            continue
        snap = ensure_snapshot_for_live(fx) or load_snapshot_by_espn_event(fx.espn_event_id)
        pat = _pattern_context(fx, _live_stats_dict(fx))
        games.append(
            {
                **_fixture_dict(fx),
                "has_prematch_snapshot": bool(snap),
                "prematch_summary": prematch_public_summary(snap),
                "phase_window": current_phase_window(fx.minute),
                "pattern_alert": pat.get("pattern_alert"),
                "pattern_summary": pat.get("pattern_summary"),
            }
        )
    return games


def analyze_by_game_id(
    game_id: str,
    *,
    league_code: str | None = None,
    force: bool = False,
    include_context: bool = False,
) -> dict | None:
    gid = str(game_id or "").strip()
    if not gid:
        return None

    scanner = EspnLiveScanner()
    for fx in scanner.scan():
        if fx.espn_event_id == gid:
            return analyze_game(fx, force=force, include_context=include_context)

    if league_code:
        from discovery.live_fixture_types import LiveFixture as LF

        # Jogo pode ter terminado — tentar só commentary para debug
        commentary = fetch_espn_commentary(league_code, gid)
        if commentary:
            fx = LF(
                home=commentary.home,
                away=commentary.away,
                league="",
                home_score=0,
                away_score=0,
                minute=commentary.minute,
                status_short="LIVE",
                espn_event_id=gid,
                espn_league_code=league_code,
            )
            return analyze_game(fx, force=force, include_context=include_context)
    return None


def build_live_board_payload(*, force: bool = False) -> dict:
    games = list_live_games()
    analyzed: list[dict] = []
    for g in games[:6]:
        fx = LiveFixture(
            home=g["home"],
            away=g["away"],
            league=g["league"],
            home_score=int(g.get("home_score") or 0),
            away_score=int(g.get("away_score") or 0),
            minute=int(g.get("minute") or 0),
            status_short=str(g.get("status_short") or "LIVE"),
            espn_event_id=str(g.get("espn_event_id") or ""),
            espn_league_code=str(g.get("espn_league_code") or ""),
        )
        if fx.espn_event_id:
            analyzed.append(analyze_game(fx, force=force))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "games": games,
        "analyses": analyzed,
    }