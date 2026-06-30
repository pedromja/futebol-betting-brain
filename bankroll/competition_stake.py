"""Limite de stake em competições com dados menos fiáveis."""

from __future__ import annotations

import re

MAX_STAKE_LOW_TRUST = 1

# Liga + fase do jogo (texto livre das APIs)
_LOW_TRUST_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bfifa\b",
        r"\buefa\b",
        r"world\s*cup",
        r"mundial",
        r"champions\s*league",
        r"liga\s+dos\s+campe",
        r"europa\s+league",
        r"conference\s+league",
        r"nations\s+league",
        r"\beuro\s*20\d{2}\b",
        r"\beuro\b",
        r"amigav",
        r"amistos",
        r"\bfriendly\b",
        r"\bfriendlies\b",
        r"international\s+friendly",
        r"junior",
        r"júnior",
        r"jovem",
        r"\byouth\b",
        r"\bu-?\s?(17|18|19|20|21|23)\b",
        r"\bunder[\s-]?(17|18|19|20|21|23)\b",
        r"sub[\s-]?(15|17|19|20|21|23)",
        r"olympic",
        r"olímpic",
        r"qualificat",
        r"\bwc\b",
    )
)


def _competition_blob(league: str, stage: str = "") -> str:
    return f"{league or ''} {stage or ''}".strip()


def is_stake_capped_competition(league: str, stage: str = "") -> bool:
    """FIFA, UEFA, amigáveis, juniores → stake máximo 1."""
    blob = _competition_blob(league, stage)
    if not blob:
        return False
    return any(p.search(blob) for p in _LOW_TRUST_PATTERNS)


def cap_stake_level(level: int, league: str, stage: str = "") -> int:
    if is_stake_capped_competition(league, stage):
        return min(level, MAX_STAKE_LOW_TRUST)
    return level