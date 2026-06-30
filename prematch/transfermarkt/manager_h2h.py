"""Pilar 2 — contexto tático treinador + H2H."""

from __future__ import annotations

from prematch.transfermarkt.types import ManagerH2H, ManagerProfile, TacticalInsight

FORMATION_OPENNESS: dict[str, float] = {
    "3-4-3": 0.72,
    "3-4-2-1": 0.68,
    "4-3-3": 0.65,
    "4-2-3-1": 0.55,
    "4-4-2": 0.52,
    "4-1-4-1": 0.48,
    "5-4-1": 0.35,
    "5-3-2": 0.38,
}


def _formation_openness(formation: str) -> float:
    fmt = (formation or "4-2-3-1").strip()
    if fmt in FORMATION_OPENNESS:
        return FORMATION_OPENNESS[fmt]
    for key, val in FORMATION_OPENNESS.items():
        if key in fmt:
            return val
    return 0.55


def compute_tactical(
    home_mgr: ManagerProfile | None,
    away_mgr: ManagerProfile | None,
    h2h: ManagerH2H | None,
) -> TacticalInsight | None:
    if not home_mgr and not away_mgr:
        return None
    home_name = home_mgr.manager if home_mgr else "—"
    away_name = away_mgr.manager if away_mgr else "—"
    home_fmt = home_mgr.formation if home_mgr else "4-2-3-1"
    away_fmt = away_mgr.formation if away_mgr else "4-2-3-1"
    openness = (_formation_openness(home_fmt) + _formation_openness(away_fmt)) / 2

    h2h_games = h2h.games if h2h else 0
    h2h_goals = h2h.avg_goals if h2h else None

    if h2h_goals is not None and h2h_games >= 3:
        if h2h_goals < 2.1:
            tendency = "under"
            label = f"H2H treinadores: média {h2h_goals:.1f} golos — jogo tende a fechar"
        elif h2h_goals > 2.8:
            tendency = "over"
            label = f"H2H treinadores: média {h2h_goals:.1f} golos — confronto aberto"
        else:
            tendency = "neutral"
            label = f"H2H treinadores: média {h2h_goals:.1f} golos"
    elif openness >= 0.62:
        tendency = "over"
        label = f"Formações ofensivas ({home_fmt} vs {away_fmt}) — favorece Over/BTTS"
    elif openness <= 0.42:
        tendency = "under"
        label = f"Blocos compactos ({home_fmt} vs {away_fmt}) — favorece Under"
    else:
        tendency = "neutral"
        label = f"Perfil tático equilibrado ({home_fmt} vs {away_fmt})"

    if h2h and h2h_games >= 4:
        win_rate = h2h.wins_a / h2h_games
        if win_rate >= 0.65:
            label += f" · {home_name} domina o H2H ({h2h.wins_a}V)"

    return TacticalInsight(
        home_manager=home_name,
        away_manager=away_name,
        home_formation=home_fmt,
        away_formation=away_fmt,
        openness_score=openness,
        h2h_games=h2h_games,
        h2h_avg_goals=h2h_goals,
        goals_tendency=tendency,
        label=label,
    )