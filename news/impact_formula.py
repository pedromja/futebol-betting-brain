"""
Fórmula de distorção de valor por notícias validadas no X.

Cada notícia i aplicada à equipa t:

    I_i = W_c × S × V × R × P

    W_c = peso base da categoria (tabela CATEGORY_WEIGHTS)
    S   = severidade da notícia [0, 1]
    V   = credibilidade/validação no X [0, 1]
    R   = decaimento temporal: e^(-dias/τ), τ = 7 dias
    P   = importância do jogador afetado [0, 1]

Impacto por eixo:
    Δataque_i   = W_c.attack × I_i
    Δdefesa_i   = W_c.defense × I_i   (positivo = pior defesa, mais golos sofridos)

Agregação com retornos decrescentes (evita stacking excessivo):
    Δataque_total   = tanh(Σ Δataque_i × 2) / 2
    Δdefesa_total   = tanh(Σ Δdefesa_i × 2) / 2

Multiplicadores finais:
    M_ataque  = clamp(1 + Δataque_total,   0.65, 1.15)
    M_defesa  = clamp(1 + Δdefesa_total,   0.90, 1.40)

Distorção total da equipa:
    D_t = |M_ataque - 1| + |M_defesa - 1|
"""

from dataclasses import dataclass
from math import exp, tanh

from models.resilience import dampen_news_impact
from models.team_stats import MatchInput, TeamForm

from .types import (
    CATEGORY_LABELS,
    MatchNewsReport,
    NewsCategory,
    NewsImpactDetail,
    NewsItem,
    TeamNewsReport,
)


@dataclass
class TeamDistortion:
    team_name: str
    attack_multiplier: float
    defense_multiplier: float
    total_distortion: float
    attack_delta_total: float
    defense_delta_total: float
    details: list[NewsImpactDetail]
    original_attack: float
    original_defense: float
    adjusted_attack: float
    adjusted_defense: float


CATEGORY_WEIGHTS: dict[NewsCategory, dict[str, float]] = {
    NewsCategory.KEY_PLAYER_INJURY: {
        "base": 1.00, "attack": -0.28, "defense": 0.06, "default_player": 0.95,
    },
    NewsCategory.KEY_PLAYER_SUSPENSION: {
        "base": 0.95, "attack": -0.22, "defense": 0.04, "default_player": 0.90,
    },
    NewsCategory.SQUAD_PLAYER_INJURY: {
        "base": 0.60, "attack": -0.10, "defense": 0.03, "default_player": 0.40,
    },
    NewsCategory.UNPAID_SALARIES: {
        "base": 0.85, "attack": -0.14, "defense": 0.10, "default_player": 0.0,
    },
    NewsCategory.FAN_UNREST: {
        "base": 0.70, "attack": -0.10, "defense": 0.05, "default_player": 0.0,
    },
    NewsCategory.DRESSING_ROOM_CRISIS: {
        "base": 0.90, "attack": -0.16, "defense": 0.12, "default_player": 0.0,
    },
    NewsCategory.MANAGER_CHANGE: {
        "base": 0.75, "attack": -0.10, "defense": 0.08, "default_player": 0.0,
    },
    NewsCategory.POSITIVE_RETURN: {
        "base": 0.80, "attack": 0.12, "defense": -0.05, "default_player": 0.85,
    },
    NewsCategory.GENERAL_NEGATIVE: {
        "base": 0.50, "attack": -0.08, "defense": 0.05, "default_player": 0.0,
    },
    NewsCategory.GENERAL_POSITIVE: {
        "base": 0.50, "attack": 0.06, "defense": -0.03, "default_player": 0.0,
    },
}

RECENCY_TAU = 7.0


class ImpactFormula:
    def recency_factor(self, days_ago: float) -> float:
        return exp(-days_ago / RECENCY_TAU)

    def _player_factor(self, item: NewsItem, weights: dict) -> float:
        if weights["default_player"] > 0:
            p = item.player_importance if item.player_importance > 0 else weights["default_player"]
            return 0.4 + 0.6 * p
        return 1.0

    def compute_item_impact(self, item: NewsItem) -> NewsImpactDetail:
        weights = CATEGORY_WEIGHTS[item.category]
        r = self.recency_factor(item.days_ago)
        p = self._player_factor(item, weights)

        raw = weights["base"] * item.severity * item.credibility * r * p
        res = dampen_news_impact(raw, item.team, item.category)
        effective = res.effective_impact
        attack_delta = weights["attack"] * effective
        defense_delta = weights["defense"] * effective

        label = CATEGORY_LABELS[item.category]
        prof = res.profile
        steps = [
            f"Categoria: {label} (W_c base={weights['base']:.2f})",
            f"S={item.severity:.2f} × V={item.credibility:.2f} × R={r:.3f} × P={p:.2f}",
            f"I_bruto = {weights['base']:.2f} × {item.severity:.2f} × {item.credibility:.2f} "
            f"× {r:.3f} × {p:.2f} = {raw:.4f}",
        ]
        if prof:
            steps += [
                f"Resiliência [{prof.name}]: D={prof.squad_depth:.2f} I={prof.institutional:.2f} "
                f"F={prof.financial:.2f} → S_c={res.axis_score:.2f}",
                f"R_c={res.resilience:.2f} | α_c={res.damping_alpha:.2f} | "
                f"fator={res.dampen_factor:.2f}",
                f"I_efetivo = {raw:.4f} × {res.dampen_factor:.2f} = {effective:.4f}",
            ]
        steps += [
            f"Δataque = {weights['attack']:+.2f} × {effective:.4f} = {attack_delta:+.4f}",
            f"Δdefesa = {weights['defense']:+.2f} × {effective:.4f} = {defense_delta:+.4f}",
        ]

        return NewsImpactDetail(
            item=item,
            recency_factor=r,
            raw_impact=raw,
            attack_delta=attack_delta,
            defense_delta=defense_delta,
            formula_steps=steps,
            resilience_score=res.resilience,
            resilience_damping=res.damping_alpha,
            effective_impact=effective,
        )

    def compute_team_distortion(
        self, team: TeamForm, report: TeamNewsReport
    ) -> TeamDistortion:
        details = [
            self.compute_item_impact(
                NewsItem(
                    team=team.name,
                    category=item.category,
                    headline=item.headline,
                    summary=item.summary,
                    severity=item.severity,
                    credibility=item.credibility,
                    player_importance=item.player_importance,
                    days_ago=item.days_ago,
                    source_url=item.source_url,
                    source_handle=item.source_handle,
                    validated=item.validated,
                )
            )
            for item in report.items
        ]

        raw_attack = sum(d.attack_delta for d in details)
        raw_defense = sum(d.defense_delta for d in details)

        attack_delta_total = tanh(raw_attack * 2) / 2
        defense_delta_total = tanh(raw_defense * 2) / 2

        attack_mult = max(0.65, min(1.15, 1 + attack_delta_total))
        defense_mult = max(0.90, min(1.40, 1 + defense_delta_total))

        adjusted_attack = team.goals_scored_avg * attack_mult
        adjusted_defense = team.goals_conceded_avg * defense_mult
        distortion = abs(attack_mult - 1) + abs(defense_mult - 1)

        return TeamDistortion(
            team_name=team.name,
            attack_multiplier=attack_mult,
            defense_multiplier=defense_mult,
            total_distortion=distortion,
            attack_delta_total=attack_delta_total,
            defense_delta_total=defense_delta_total,
            details=details,
            original_attack=team.goals_scored_avg,
            original_defense=team.goals_conceded_avg,
            adjusted_attack=adjusted_attack,
            adjusted_defense=adjusted_defense,
        )

    def adjust_match(
        self, match: MatchInput, news: MatchNewsReport | None
    ) -> tuple[MatchInput, TeamDistortion | None, TeamDistortion | None]:
        if not news or (not news.home.items and not news.away.items):
            return match, None, None

        home_dist = self.compute_team_distortion(match.home, news.home)
        away_dist = self.compute_team_distortion(match.away, news.away)

        adjusted_home = TeamForm(
            name=match.home.name,
            goals_scored_avg=home_dist.adjusted_attack,
            goals_conceded_avg=home_dist.adjusted_defense,
            games_played=match.home.games_played,
            scored_in_last_n=match.home.scored_in_last_n,
            conceded_in_last_n=match.home.conceded_in_last_n,
            last_n=match.home.last_n,
        )
        adjusted_away = TeamForm(
            name=match.away.name,
            goals_scored_avg=away_dist.adjusted_attack,
            goals_conceded_avg=away_dist.adjusted_defense,
            games_played=match.away.games_played,
            scored_in_last_n=match.away.scored_in_last_n,
            conceded_in_last_n=match.away.conceded_in_last_n,
            last_n=match.away.last_n,
        )

        adjusted_match = MatchInput(
            home=adjusted_home,
            away=adjusted_away,
            odds=match.odds,
            league=match.league,
            date=match.date,
            home_advantage=match.home_advantage,
            league_avg_goals=match.league_avg_goals,
        )

        return adjusted_match, home_dist, away_dist