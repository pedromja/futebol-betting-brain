"""Deteta quotas esgotadas e activa fallback até ao dia seguinte (UTC)."""

from __future__ import annotations

from datetime import datetime, timezone

PROVIDER_API_FOOTBALL = "api-football"
PROVIDER_THE_ODDS = "the-odds-api"
PROVIDER_FOOTBALL_DATA = "football-data"

_EXHAUSTED_DAY: dict[str, str] = {}


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def is_quota_error(message: str | None) -> bool:
    if not message:
        return False
    m = message.lower()
    needles = (
        "request limit",
        "rate limit",
        "quota",
        "too many requests",
        "out of calls",
        "exceeded",
        "limit for the day",
        "no requests left",
    )
    return any(n in m for n in needles)


def mark_exhausted(provider: str, reason: str = "") -> None:
    _EXHAUSTED_DAY[provider] = _today()


def clear_exhausted(provider: str) -> None:
    _EXHAUSTED_DAY.pop(provider, None)


def is_exhausted(provider: str) -> bool:
    return _EXHAUSTED_DAY.get(provider) == _today()


def active_fallbacks() -> list[str]:
    fallbacks: list[str] = []
    if is_exhausted(PROVIDER_API_FOOTBALL):
        fallbacks.extend(["espn", "thesportsdb", "football-data"])
    if is_exhausted(PROVIDER_THE_ODDS):
        fallbacks.extend(["espn", "fixture-odds"])
    return list(dict.fromkeys(fallbacks))