"""URLs football-data.co.uk por liga."""

from __future__ import annotations

import re

BASE = "https://www.football-data.co.uk/mmz4281"

# Época actual (2526 = 2025/26)
DEFAULT_SEASON = "2526"

LEAGUE_FILES: dict[str, str] = {
    "PPL": "P1.csv",
    "PL": "E0.csv",
    "PD": "SP1.csv",
    "SA": "I1.csv",
    "BL1": "D1.csv",
    "FL1": "F1.csv",
    "DED": "N1.csv",
}

_LEAGUE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pat, re.IGNORECASE), code)
    for pat, code in (
        (r"primeira\s*liga|liga\s*portugal|portugal", "PPL"),
        (r"premier\s*league|england", "PL"),
        (r"la\s*liga|spain|laliga", "PD"),
        (r"serie\s*a|italy", "SA"),
        (r"bundesliga|germany", "BL1"),
        (r"ligue\s*1|france", "FL1"),
        (r"eredivisie|netherlands|holland", "DED"),
    )
)


def league_to_code(league: str) -> str | None:
    blob = (league or "").strip()
    if not blob:
        return None
    for pattern, code in _LEAGUE_PATTERNS:
        if pattern.search(blob):
            return code
    return None


def csv_url(league_code: str, season: str = DEFAULT_SEASON) -> str | None:
    fname = LEAGUE_FILES.get(league_code.upper())
    if not fname:
        return None
    return f"{BASE}/{season}/{fname}"