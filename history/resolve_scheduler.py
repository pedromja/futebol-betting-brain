"""Evita resolver outcomes em cada pedido ao histórico — cooldown configurável."""

from __future__ import annotations

import json
import time
from pathlib import Path

from config.data_paths import DATA_DIR

_STATE = DATA_DIR / "last_resolve.json"
_ENRICH_STATE = DATA_DIR / "last_enrich.json"
_DEFAULT_COOLDOWN_SEC = 180  # 3 min — resolve mais cedo após FT
_DEFAULT_ENRICH_COOLDOWN_SEC = 1800  # 30 min


def _read_state() -> dict:
    if not _STATE.exists():
        return {}
    try:
        return json.loads(_STATE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def should_resolve(*, force: bool = False, cooldown_sec: int = _DEFAULT_COOLDOWN_SEC) -> bool:
    if force:
        return True
    state = _read_state()
    last = float(state.get("at") or 0)
    return (time.time() - last) >= cooldown_sec


def mark_resolved(*, resolved_count: int = 0) -> None:
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(
        json.dumps(
            {"at": time.time(), "resolved": resolved_count},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _read_enrich_state() -> dict:
    if not _ENRICH_STATE.exists():
        return {}
    try:
        return json.loads(_ENRICH_STATE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def should_enrich(*, force: bool = False, cooldown_sec: int = _DEFAULT_ENRICH_COOLDOWN_SEC) -> bool:
    if force:
        return True
    state = _read_enrich_state()
    last = float(state.get("at") or 0)
    return (time.time() - last) >= cooldown_sec


def mark_enriched(*, reviewed_count: int = 0) -> None:
    _ENRICH_STATE.parent.mkdir(parents=True, exist_ok=True)
    _ENRICH_STATE.write_text(
        json.dumps(
            {"at": time.time(), "reviewed": reviewed_count},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def maybe_enrich_resolved(
    *,
    force: bool = False,
    cooldown_sec: int = _DEFAULT_ENRICH_COOLDOWN_SEC,
    max_fetch: int = 10,
) -> int:
    """Reavalia entradas resolvidas com stats FT quando o cooldown expirou."""
    if not should_enrich(force=force, cooldown_sec=cooldown_sec):
        return 0
    try:
        from history.post_match_review import enrich_all_resolved_logs

        stats = enrich_all_resolved_logs(max_fetch=max_fetch, dry_run=False)
        mark_enriched(reviewed_count=stats.get("reviewed", 0))
        return int(stats.get("reviewed", 0))
    except Exception:
        return 0


def maybe_resolve_pending(*, force: bool = False, cooldown_sec: int = _DEFAULT_COOLDOWN_SEC) -> int:
    """Resolve tips pendentes se o cooldown tiver expirado. Devolve quantas foram resolvidas."""
    if not should_resolve(force=force, cooldown_sec=cooldown_sec):
        maybe_enrich_resolved()
        return 0
    try:
        from config.data_paths import BOT_SIGNALS_LOG, IA_LIVE_SIGNALS, PREDICTIONS_LOG
        from history.outcome_resolver import resolve_predictions

        total = 0
        _, stats = resolve_predictions(PREDICTIONS_LOG, dry_run=False)
        total += stats.resolved
        _, bot_stats = resolve_predictions(BOT_SIGNALS_LOG, dry_run=False)
        total += bot_stats.resolved
        if IA_LIVE_SIGNALS.exists():
            _, ia_stats = resolve_predictions(IA_LIVE_SIGNALS, dry_run=False)
            total += ia_stats.resolved
        mark_resolved(resolved_count=total)
        maybe_enrich_resolved()
        if total > 0:
            try:
                from bots.ia_audit import maybe_refresh_ia_audit

                maybe_refresh_ia_audit()
            except Exception:
                pass
        return total
    except Exception:
        return 0