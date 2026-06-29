"""
Ajuste por necessidade competitiva.

Pré-jogo e ao vivo usam a mesma base; ao vivo aplica urgência extra
consoante o resultado actual (ver live/urgency.py).

Multiplicadores base (ataque, defesa/sofridos):
  MUST_WIN        → ataca mais, abre um pouco (1.10, 1.04)
  MUST_NOT_LOSE   → mais cauteloso (0.94, 0.92)
  DRAW_OK         → protege resultado possível (0.90, 0.90)
  QUALIFIED       → poupa energia (0.86, 0.97)
  DEPENDS_OTHERS  → incerteza, ligeiro conservador (0.98, 0.98)
  ELIMINATED      → honra/prazer, irregular (1.03, 1.05)
  KNOCKOUT        → intensidade alta (1.08, 1.02)
  NEUTRAL         → (1.00, 1.00)
"""

from models.team_stats import MatchInput, TeamForm

from .types import (
    STAKE_LABELS,
    MatchStakesReport,
    StakeAdjustment,
    StakeSituation,
    TeamStake,
)

BASE_MULTIPLIERS: dict[StakeSituation, tuple[float, float, float]] = {
    # (attack_mult, defense_mult, urgency_base)
    StakeSituation.NEUTRAL: (1.00, 1.00, 1.00),
    StakeSituation.MUST_WIN: (1.10, 1.04, 1.12),
    StakeSituation.MUST_NOT_LOSE: (0.94, 0.92, 0.95),
    StakeSituation.DRAW_OK: (0.90, 0.90, 0.88),
    StakeSituation.QUALIFIED: (0.86, 0.97, 0.82),
    StakeSituation.DEPENDS_OTHERS: (0.98, 0.98, 1.00),
    StakeSituation.ELIMINATED: (1.03, 1.05, 0.90),
    StakeSituation.KNOCKOUT: (1.08, 1.02, 1.10),
}


def _default_stake() -> TeamStake:
    return TeamStake(situation=StakeSituation.NEUTRAL)


def compute_stake_adjustment(
    team: TeamForm,
    stake: TeamStake | None,
    *,
    score_diff: int | None = None,
    is_home: bool = True,
    minute: int | None = None,
) -> StakeAdjustment:
    """score_diff = golos da equipa − adversário (só relevante ao vivo)."""
    st = stake or _default_stake()
    atk, dfn, urg = BASE_MULTIPLIERS.get(st.situation, (1.0, 1.0, 1.0))
    steps = [
        f"Situação: {STAKE_LABELS[st.situation]}",
        f"Base: M_ataque={atk:.2f}, M_defesa={dfn:.2f}, urgência={urg:.2f}",
    ]

    if score_diff is not None and minute is not None:
        late = minute >= 70
        if st.situation == StakeSituation.MUST_WIN:
            if score_diff < 0:
                boost = 1.18 if late else 1.12
                atk *= boost
                dfn *= 1.06
                steps.append(f"Ao vivo a perder: ataque ×{boost:.2f} (precisa virar)")
            elif score_diff > 0:
                atk *= 0.93
                dfn *= 0.94
                steps.append("Ao vivo a ganhar: protege resultado (ataque −7%)")
        elif st.situation in (StakeSituation.MUST_NOT_LOSE, StakeSituation.DRAW_OK):
            if score_diff >= 0:
                atk *= 0.88
                dfn *= 0.92
                steps.append("Objetivo cumprido: fecha o jogo (ataque −12%)")
            elif late:
                atk *= 1.05
                steps.append("A perder tarde: risco calculado para evitar derrota")
        elif st.situation == StakeSituation.QUALIFIED:
            atk *= 0.92 if score_diff >= 0 else 1.0
            steps.append("Já apurada: intensidade reduzida")
        elif st.situation == StakeSituation.KNOCKOUT:
            if score_diff == 0 and late:
                atk *= 1.14
                dfn *= 1.03
                steps.append("Eliminatória empatada tarde: busca vitória antes do prolongamento")
            elif score_diff < 0 and late:
                atk *= 1.20
                dfn *= 1.05
                steps.append("Eliminatória a perder: tudo ou nada")

    return StakeAdjustment(
        team_name=team.name,
        situation=st.situation,
        attack_mult=round(atk, 3),
        defense_mult=round(dfn, 3),
        urgency=round(urg, 3),
        label=STAKE_LABELS[st.situation],
        formula_steps=steps,
    )


def apply_stakes_to_match(
    match: MatchInput,
    home_stake: TeamStake | None = None,
    away_stake: TeamStake | None = None,
    *,
    score_diff_home: int | None = None,
    minute: int | None = None,
) -> tuple[MatchInput, MatchStakesReport]:
    hs = home_stake or getattr(match, "home_stake", None)
    as_ = away_stake or getattr(match, "away_stake", None)

    home_adj = compute_stake_adjustment(
        match.home, hs, score_diff=score_diff_home, is_home=True, minute=minute
    )
    away_adj = compute_stake_adjustment(
        match.away,
        as_,
        score_diff=-score_diff_home if score_diff_home is not None else None,
        is_home=False,
        minute=minute,
    )

    new_home = TeamForm(
        name=match.home.name,
        goals_scored_avg=match.home.goals_scored_avg * home_adj.attack_mult,
        goals_conceded_avg=match.home.goals_conceded_avg * home_adj.defense_mult,
        games_played=match.home.games_played,
        scored_in_last_n=match.home.scored_in_last_n,
        conceded_in_last_n=match.home.conceded_in_last_n,
        last_n=match.home.last_n,
    )
    new_away = TeamForm(
        name=match.away.name,
        goals_scored_avg=match.away.goals_scored_avg * away_adj.attack_mult,
        goals_conceded_avg=match.away.goals_conceded_avg * away_adj.defense_mult,
        games_played=match.away.games_played,
        scored_in_last_n=match.away.scored_in_last_n,
        conceded_in_last_n=match.away.conceded_in_last_n,
        last_n=match.away.last_n,
    )

    adjusted = MatchInput(
        home=new_home,
        away=new_away,
        odds=match.odds,
        league=match.league,
        date=match.date,
        home_advantage=match.home_advantage,
        league_avg_goals=match.league_avg_goals,
        venue_stadium=match.venue_stadium,
        venue_city=match.venue_city,
        venue_country=match.venue_country,
        home_stake=hs,
        away_stake=as_,
    )

    note_parts = []
    if home_adj.situation != StakeSituation.NEUTRAL:
        note_parts.append(f"{match.home.name}: {home_adj.label}")
    if away_adj.situation != StakeSituation.NEUTRAL:
        note_parts.append(f"{match.away.name}: {away_adj.label}")

    report = MatchStakesReport(
        home=home_adj,
        away=away_adj,
        combined_note=" | ".join(note_parts) if note_parts else "Sem ajuste de necessidade",
    )
    return adjusted, report