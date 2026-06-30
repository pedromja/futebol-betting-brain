"""Evita resolver outcomes em cada pedido ao histórico — cooldown configurável."""

from __future__ import annotations

import json
import time
from pathlib import Path

from config.data_paths import DATA_DIR

_STATE = DATA_DIR / "last_resolve.json"
_DEFAULT_COOLDOWN_SEC = 900  # 15 min


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


def maybe_resolve_pending(*, force: bool = False, cooldown_sec: int = _DEFAULT_COOLDOWN_SEC) -> int:
    """Resolve tips pendentes se o cooldown tiver expirado. Devolve quantas foram resolvidas."""
    if not should_resolve(force=force, cooldown_sec=cooldown_sec):
        return 0
    try:
        from config.data_paths import BOT_SIGNALS_LOG, PREDICTIONS_LOG
        from history.outcome_resolver import resolve_predictions

        total = 0
        _, stats = resolve_predictions(PREDICTIONS_LOG, dry_run=False)
        total += stats.resolved
        _, bot_stats = resolve_predictions(BOT_SIGNALS_LOG, dry_run=False)
        total += bot_stats.resolved
        mark_resolved(resolved_count=total)
        return total
    except Exception:
        return 0