"""Limite de stake em competições com dados menos fiáveis."""

from __future__ import annotations

import re

MAX_STAKE_LOW_TRUST = 1

# Liga + fase do jogo (texto livre das APIs)
_YOUTH_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bjunior\b",
        r"\bjúnior\b",
        r"\bjuniores\b",
        r"\bjovens\b",
        r"\bjovem\b",
        r"\byouth\b",
        r"\bu-?\s?(17|18|19|20|21|23)\b",
        r"\bunder[\s-]?(17|18|19|20|21|23)\b",
        r"sub[\s-]?(15|17|19|20|21|23)",
        r"\beuro\s*u\s*21\b",
        r"\bu21\b",
    )
)

_FRIENDLY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"amig[aá]v",
        r"amistos",
        r"amig[aá]vel",
        r"\bfriendly\b",
        r"\bfriendlies\b",
        r"international\s+friendly",
    )
)

_INTERNATIONAL_SENIOR_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bfifa\b",
        r"world\s*cup",
        r"mundial",
        r"\bwc\b",
        r"nations\s+league",
        r"\beuro\s*20\d{2}\b",
        r"\beuropean\s+championship\b",
        r"qualificat",
        r"copa\s+america",
        r"gold\s+cup",
        r"afcon",
        r"africa\s+cup",
        r"asian\s+cup",
        r"concacaf",
    )
)

_UEFA_CLUB_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\buefa\b",
        r"champions\s*league",
        r"liga\s+dos\s+campe",
        r"europa\s+league",
        r"conference\s+league",
        r"\beuro\b",
    )
)

_OLYMPIC_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"olympic",
        r"olímpic",
        r"olimpic",
    )
)

_LOW_TRUST_PATTERNS: tuple[re.Pattern[str], ...] = (
    *_YOUTH_PATTERNS,
    *_FRIENDLY_PATTERNS,
    *_INTERNATIONAL_SENIOR_PATTERNS,
    *_UEFA_CLUB_PATTERNS,
    *_OLYMPIC_PATTERNS,
)


def _competition_blob(league: str, stage: str = "") -> str:
    return f"{league or ''} {stage or ''}".strip()


def _matches_any(blob: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(p.search(blob) for p in patterns)


def stake_cap_reason(league: str, stage: str = "") -> str | None:
    """Motivo legível do limite de stake — sem misturar seleções sénior com juniores."""
    blob = _competition_blob(league, stage)
    if not blob:
        return None
    if _matches_any(blob, _YOUTH_PATTERNS):
        return "juniores"
    if _matches_any(blob, _OLYMPIC_PATTERNS):
        return "seleções olímpicas"
    if _matches_any(blob, _FRIENDLY_PATTERNS):
        return "amigável internacional"
    if _matches_any(blob, _INTERNATIONAL_SENIOR_PATTERNS):
        return "seleções"
    if _matches_any(blob, _UEFA_CLUB_PATTERNS):
        return "UEFA"
    return None


def is_stake_capped_competition(league: str, stage: str = "") -> bool:
    """FIFA, UEFA, amigáveis, seleções, juniores → stake máximo 1."""
    blob = _competition_blob(league, stage)
    if not blob:
        return False
    return _matches_any(blob, _LOW_TRUST_PATTERNS)


def cap_stake_level(level: int, league: str, stage: str = "") -> int:
    if is_stake_capped_competition(league, stage):
        return min(level, MAX_STAKE_LOW_TRUST)
    return level