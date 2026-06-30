"""Regra de progresso do campeonato — sem apostas no início/fim de época."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from bankroll.competition_stake import is_stake_capped_competition
from prematch.auditors.table_stakes import fetch_standings, league_to_fd_code
from prematch.historical.sources import league_to_code as historical_league_code
from prematch.historical.store import get_store as get_historical_store

MIN_PROGRESS_PCT = 20.0
MAX_PROGRESS_PCT = 85.0

# Jornadas totais (ida+volta) por liga — fallback quando só há jornada no stage
_LEAGUE_TOTAL_ROUNDS: dict[str, int] = {
    "PPL": 34,
    "PL": 38,
    "PD": 38,
    "SA": 38,
    "BL1": 34,
    "FL1": 34,
    "DED": 34,
}

_ROUND_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"(?:regular\s*season|jornada|matchday|match\s*day|round|week|weekend)\s*[-#:]\s*(\d+)",
        r"(?:regular\s*season|jornada|matchday|round|week)\s+(\d+)",
        r"(\d+)\s*(?:ª|a|º|o)?\s*(?:jornada|round|matchday)",
        r"^(\d+)$",
    )
)


@dataclass
class CompetitionProgress:
    league: str
    progress_pct: float
    allowed: bool
    reason: str
    source: str
    matchday: int | None = None
    total_rounds: int | None = None
    teams: int | None = None

    def to_dict(self) -> dict:
        return {
            "league": self.league,
            "progress_pct": round(self.progress_pct, 1),
            "allowed": self.allowed,
            "reason": self.reason,
            "source": self.source,
            "matchday": self.matchday,
            "total_rounds": self.total_rounds,
            "teams": self.teams,
            "min_pct": MIN_PROGRESS_PCT,
            "max_pct": MAX_PROGRESS_PCT,
        }


def applies_progress_rule(league: str, stage: str = "") -> bool:
    """Só ligas domésticas; copas/seleções/juniores ficam fora desta regra."""
    return not is_stake_capped_competition(league, stage)


def parse_round_from_stage(stage: str) -> int | None:
    text = (stage or "").strip()
    if not text:
        return None
    for pattern in _ROUND_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                val = int(m.group(1))
                return val if val > 0 else None
            except (TypeError, ValueError):
                continue
    return None


def _expected_rounds(league_code: str | None, num_teams: int | None) -> int | None:
    if league_code and league_code in _LEAGUE_TOTAL_ROUNDS:
        return _LEAGUE_TOTAL_ROUNDS[league_code]
    if num_teams and num_teams >= 4:
        return 2 * (num_teams - 1)
    return None


def _progress_from_standings(table: list[dict]) -> tuple[float, int, int] | None:
    if not table or len(table) < 4:
        return None
    played = [int(row.get("playedGames") or 0) for row in table]
    if not played or max(played) <= 0:
        return None
    teams = len(table)
    total_rounds = 2 * (teams - 1)
    avg_played = sum(played) / len(played)
    pct = (avg_played / total_rounds) * 100.0
    return pct, int(round(avg_played)), total_rounds


def _progress_from_historical(league: str) -> tuple[float, int, int] | None:
    code = historical_league_code(league)
    if not code:
        return None
    store = get_historical_store()
    matches = [
        prof.matches
        for prof in store._index.values()
        if prof.league == code and prof.matches > 0
    ]
    if len(matches) < 4:
        return None
    avg_matches = sum(matches) / len(matches)
    total_rounds = _LEAGUE_TOTAL_ROUNDS.get(code)
    if not total_rounds:
        return None
    pct = (avg_matches / total_rounds) * 100.0
    return pct, int(round(avg_matches)), total_rounds


def _block_reason(progress_pct: float) -> str:
    if progress_pct < MIN_PROGRESS_PCT:
        return (
            f"Época demasiado cedo ({progress_pct:.0f}% < {MIN_PROGRESS_PCT:.0f}%) "
            "— sem posições"
        )
    return (
        f"Época demasiado avançada ({progress_pct:.0f}% > {MAX_PROGRESS_PCT:.0f}%) "
        "— sem posições"
    )


def resolve_competition_progress(
    league: str,
    *,
    stage: str = "",
    football_data_key: str | None = None,
) -> CompetitionProgress | None:
    """
    Calcula progresso da época. Devolve None se não for aplicável ou incalculável.
    """
    if not applies_progress_rule(league, stage):
        return None

    league_code = league_to_fd_code(league) or historical_league_code(league)
    fd_key = football_data_key or os.getenv("FOOTBALL_DATA_API_KEY", "")

    pct: float | None = None
    source = ""
    matchday: int | None = None
    total_rounds: int | None = None
    teams: int | None = None

    table = fetch_standings(league, api_key=fd_key) if fd_key else None
    if table:
        teams = len(table)
        standings_hit = _progress_from_standings(table)
        if standings_hit:
            pct, matchday, total_rounds = standings_hit
            source = "standings"

    if pct is None:
        hist = _progress_from_historical(league)
        if hist:
            pct, matchday, total_rounds = hist
            source = "historical_profiles"

    round_from_stage = parse_round_from_stage(stage)
    if round_from_stage:
        total = total_rounds or _expected_rounds(league_code, teams)
        if total:
            stage_pct = (round_from_stage / total) * 100.0
            if pct is None:
                pct, matchday, total_rounds = stage_pct, round_from_stage, total
                source = "stage"
            else:
                pct = (pct + stage_pct) / 2.0
                matchday = round_from_stage
                source = f"{source}+stage"

    if pct is None:
        return None

    allowed = MIN_PROGRESS_PCT <= pct <= MAX_PROGRESS_PCT
    reason = "Progresso dentro da janela útil" if allowed else _block_reason(pct)

    return CompetitionProgress(
        league=league,
        progress_pct=pct,
        allowed=allowed,
        reason=reason,
        source=source,
        matchday=matchday,
        total_rounds=total_rounds,
        teams=teams,
    )


def is_competition_bet_allowed(
    league: str,
    *,
    stage: str = "",
    football_data_key: str | None = None,
) -> tuple[bool, CompetitionProgress | None]:
    """
    (True, info) se pode apostar; (False, info) se bloqueado por progresso.
    Sem dados de progresso → (True, None) — não bloqueia à cegas.
    """
    info = resolve_competition_progress(
        league, stage=stage, football_data_key=football_data_key
    )
    if info is None:
        return True, None
    return info.allowed, info