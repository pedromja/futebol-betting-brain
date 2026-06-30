"""Estratégias inspiradas em comunidades de apostas — cenários live com tese EV."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioPlay:
    """Narrativa de mercado + comportamento esperado em campo."""

    id: str
    name: str
    community_thesis: str
    situations: tuple[str, ...]
    minute_min: int
    minute_max: int
    markets: tuple[str, ...]
    min_ev_pct: float = 3.0
    # Sinais mínimos para considerar que a equipa «voltou ao jogo»
    min_reaction_corners: int = 2
    min_reaction_shots_on: int = 2
    min_reaction_xg_diff: float = 0.15
    min_reaction_possession: float = 52.0
    # Apatia: abaixo disto sem momentum recente → bloquear tese
    apathy_corners_max: int = 1
    apathy_shots_on_max: int = 1
    apathy_xg_diff_max: float = -0.1
    requires_favorite_trouble: bool = True


# Narrativas comuns em fóruns/Telegram (favorito a reagir, xG invertido, urgência final)
COMMUNITY_SCENARIOS: tuple[ScenarioPlay, ...] = (
    ScenarioPlay(
        id="fav_push_post_ht",
        name="Favorito a reagir pós-HT",
        community_thesis=(
            "Comunidade: favorito a perder ao intervalo costuma abrir o jogo nos primeiros "
            "20–30 min da 2.ª parte — cantos, remates e over de golos ganham valor."
        ),
        situations=("fav_losing_post_ht", "fav_losing_ht"),
        minute_min=46,
        minute_max=78,
        markets=("Cantos Over", "Over 1.5", "Over 2.5", "Vitória Favorito", "DNB Casa", "DNB Fora"),
        min_reaction_corners=2,
        min_reaction_shots_on=2,
        min_reaction_xg_diff=0.2,
        apathy_corners_max=1,
        apathy_shots_on_max=1,
    ),
    ScenarioPlay(
        id="fav_draw_opens",
        name="Favorito a empatar — jogo a abrir",
        community_thesis=(
            "Favorito só empata: comunidades apostam na abertura entre 55'–80' "
            "(over golos, cantos do favorito) quando há pressão visível."
        ),
        situations=("fav_drawing",),
        minute_min=55,
        minute_max=82,
        markets=("Over 1.5", "Over 2.5", "Cantos Over", "Vitória Favorito"),
        min_reaction_corners=3,
        min_reaction_shots_on=3,
        min_reaction_xg_diff=0.25,
        apathy_corners_max=2,
        apathy_shots_on_max=2,
    ),
    ScenarioPlay(
        id="xg_dominant_loser",
        name="Favorito dominante no xG mas a perder",
        community_thesis=(
            "Tese «regressão ao xG»: favorito com xG superior mas resultado negativo — "
            "valor no DNB/vitória quando a pressão se confirma em remates."
        ),
        situations=("fav_losing", "fav_losing_post_ht", "fav_drawing"),
        minute_min=35,
        minute_max=85,
        markets=("Vitória Favorito", "DNB Casa", "DNB Fora", "Over 1.5"),
        min_reaction_shots_on=3,
        min_reaction_xg_diff=0.35,
        min_reaction_corners=2,
        apathy_shots_on_max=2,
        apathy_xg_diff_max=0.1,
    ),
    ScenarioPlay(
        id="late_desperation",
        name="Urgência final (75'+)",
        community_thesis=(
            "Minutos finais com favorito a precisar de resultado: over de golos e cantos "
            "— mas só após sinais prévios de pressão (evitar «apanhar apatia»)."
        ),
        situations=("fav_losing", "fav_losing_post_ht", "fav_drawing"),
        minute_min=75,
        minute_max=90,
        markets=("Over 1.5", "Over 2.5", "Cantos Over", "Vitória Favorito"),
        min_reaction_corners=4,
        min_reaction_shots_on=4,
        min_reaction_xg_diff=0.15,
        apathy_corners_max=3,
        apathy_shots_on_max=3,
    ),
    ScenarioPlay(
        id="physical_game_cards",
        name="Jogo físico — cartões/over",
        community_thesis=(
            "Jogo truncado com muitas faltas: comunidade procura over de golos e mercados "
            "de intensidade quando o favorito precisa de resultado."
        ),
        situations=("fav_losing", "fav_drawing", "fav_losing_post_ht"),
        minute_min=30,
        minute_max=88,
        markets=("Over 2.5", "Over 1.5", "Cantos Over"),
        min_reaction_corners=2,
        min_reaction_shots_on=2,
        requires_favorite_trouble=False,
        apathy_corners_max=1,
        apathy_shots_on_max=1,
    ),
)


def scenario_by_id(scenario_id: str) -> ScenarioPlay | None:
    for s in COMMUNITY_SCENARIOS:
        if s.id == scenario_id:
            return s
    return None