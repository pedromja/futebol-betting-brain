"""Cache em memória de scans — evita repetir análise pesada em polls da PWA."""

from __future__ import annotations

import time
from typing import Any

_PREMATCH_TTL = 300.0
_LIVE_TTL = 55.0
_store: dict[str, tuple[float, dict[str, Any]]] = {}


def _get(key: str, ttl: float) -> dict[str, Any] | None:
    entry = _store.get(key)
    if not entry:
        return None
    ts, payload = entry
    if (time.time() - ts) > ttl:
        _store.pop(key, None)
        return None
    out = dict(payload)
    out["cache_hit"] = True
    out["cache_age_sec"] = round(time.time() - ts, 1)
    return out


def _set(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out["cache_hit"] = False
    _store[key] = (time.time(), out)
    return out


def prematch_key(*, hours: int, min_score: float, bankroll: float | None) -> str:
    br = round(float(bankroll), 2) if bankroll is not None else "none"
    return f"prematch|{hours}|{round(min_score, 3)}|{br}"


def live_key(
    *,
    min_score: float,
    bankroll: float | None,
    max_games: int,
    league: str | None,
    prematch_odds: bool,
) -> str:
    br = round(float(bankroll), 2) if bankroll is not None else "none"
    lg = (league or "").strip().lower()
    return f"live|{round(min_score, 3)}|{br}|{max_games}|{lg}|{int(prematch_odds)}"


def get_prematch(key: str, *, ttl: float | None = None) -> dict[str, Any] | None:
    return _get(key, ttl if ttl is not None else _PREMATCH_TTL)


def set_prematch(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _set(key, payload)


def get_live(key: str, *, ttl: float = _LIVE_TTL) -> dict[str, Any] | None:
    return _get(key, ttl)


def set_live(key: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _set(key, payload)


def clear() -> None:
    _store.clear()