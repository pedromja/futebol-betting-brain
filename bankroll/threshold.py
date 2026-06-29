"""Limiar dinâmico — exige mais confiança quando os dados são fracos."""

from models.team_stats import MatchInput


def dynamic_min_score(base: float, match: MatchInput) -> float:
    """
    Sobe o score mínimo quando a amostra de forma recente é pequena.
    Evita apostas agressivas com stats de 1–2 jogos (comum no Mundial).
    """
    min_games = min(match.home.games_played, match.away.games_played)
    penalty = 0.0
    if min_games < 3:
        penalty = 0.08
    elif min_games < 5:
        penalty = 0.04
    elif min_games < 8:
        penalty = 0.02

    return round(min(0.90, base + penalty), 3)