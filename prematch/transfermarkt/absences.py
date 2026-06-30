"""Pilar 4 — impacto estruturado de lesões e suspensões."""

from __future__ import annotations

from prematch.transfermarkt.types import AbsenceInsight, PlayerAbsence, SquadSnapshot


def _severity(days_out: int, games_missed: int, history: str) -> float:
    base = min(1.0, days_out / 90.0 * 0.7 + games_missed / 15.0 * 0.5)
    if history == "recurrent":
        base = min(1.0, base * 1.15)
    elif history == "crystal":
        base *= 0.75
    return max(0.05, base)


def _replacement_factor(player_mv: float, replacement_mv: float, squad_mv: float) -> float:
    if player_mv <= 0 or squad_mv <= 0:
        return 0.5
    if replacement_mv <= 0:
        replacement_mv = squad_mv * 0.08
    ratio = replacement_mv / max(player_mv, 0.01)
    return max(0.0, min(1.0, 1.0 - ratio))


def _player_impact(
    absence: PlayerAbsence,
    squad_mv: float,
) -> float:
    share = absence.market_value_m / max(squad_mv, 0.1) if absence.market_value_m else 0.08
    share = min(0.45, share)
    sev = _severity(absence.days_out, absence.games_missed, absence.injury_history)
    repl = _replacement_factor(
        absence.market_value_m,
        absence.replacement_value_m,
        squad_mv,
    )
    if absence.status == "suspended":
        sev = min(1.0, sev * 0.85)
    return share * sev * repl


def compute_absences(team: str, squad: SquadSnapshot | None, absences: list[PlayerAbsence]) -> AbsenceInsight | None:
    if not absences:
        return None
    squad_mv = squad.market_value_m if squad else 0.0
    total = sum(_player_impact(a, squad_mv) for a in absences)
    total = min(0.85, total)
    if total >= 0.35:
        label = f"Impacto alto ({len(absences)} ausência(s) relevante(s))"
    elif total >= 0.15:
        label = f"Impacto moderado ({len(absences)} ausência(s))"
    else:
        label = f"Substituições cobrem bem as ausências"
    return AbsenceInsight(
        team=team,
        absences=absences,
        total_impact=total,
        label=label,
    )