"""
Mercados além de 1X2 / golos — handicap asiático, cantos, equipa.

Odds inseridas manualmente ou via fetcher; modelo simplificado ao vivo.
"""

from dataclasses import dataclass, field
from enum import Enum


class ExtendedMarketType(str, Enum):
    HANDICAP_HOME = "handicap_home"
    HANDICAP_AWAY = "handicap_away"
    CORNERS_OVER = "corners_over"
    CORNERS_UNDER = "corners_under"
    TEAM_GOALS_HOME_OVER = "team_goals_home_over"
    TEAM_GOALS_HOME_UNDER = "team_goals_home_under"
    SECOND_HALF_HOME = "second_half_home"
    SECOND_HALF_DRAW = "second_half_draw"
    SECOND_HALF_AWAY = "second_half_away"


EXTENDED_LABELS = {
    ExtendedMarketType.HANDICAP_HOME: "Handicap Casa",
    ExtendedMarketType.HANDICAP_AWAY: "Handicap Fora",
    ExtendedMarketType.CORNERS_OVER: "Cantos Over",
    ExtendedMarketType.CORNERS_UNDER: "Cantos Under",
    ExtendedMarketType.TEAM_GOALS_HOME_OVER: "Golos Casa Over",
    ExtendedMarketType.TEAM_GOALS_HOME_UNDER: "Golos Casa Under",
    ExtendedMarketType.SECOND_HALF_HOME: "2.ª Parte — Casa",
    ExtendedMarketType.SECOND_HALF_DRAW: "2.ª Parte — Empate",
    ExtendedMarketType.SECOND_HALF_AWAY: "2.ª Parte — Fora",
}


@dataclass
class ExtendedOdds:
    """Odds decimais de mercados extra (fonte: casas de apostas)."""

    handicap_home_line: float = -0.5
    handicap_home: float = 0.0
    handicap_away_line: float = 0.5
    handicap_away: float = 0.0
    corners_line: float = 6.5
    corners_over: float = 0.0
    corners_under: float = 0.0
    corners_current: int | None = None
    home_team_goals_line: float = 1.5
    home_team_goals_over: float = 0.0
    home_team_goals_under: float = 0.0
    second_half_home: float = 0.0
    second_half_draw: float = 0.0
    second_half_away: float = 0.0
    source: str = "manual"


@dataclass
class ExtendedMarketPick:
    market_type: ExtendedMarketType
    label: str
    odd: float
    model_prob: float
    implied_prob: float
    expected_value: float
    reasoning: list[str] = field(default_factory=list)
    status: str = "available"

    @property
    def ev_percent(self) -> float:
        return self.expected_value * 100


@dataclass
class LiveContext:
    home_score: int
    away_score: int
    minute: int
    home_xg: float = 0.0
    away_xg: float = 0.0
    home_possession: float = 0.5
    home_shots: int = 0
    away_shots: int = 0
    home_pressure: str = "medium"
    remaining_minutes: float = 10.0


class ExtendedMarketAnalyzer:
    """Heurísticas ao vivo para mercados não-Poisson."""

    def analyze(
        self,
        ctx: LiveContext,
        odds: ExtendedOdds,
        home_name: str = "Casa",
        away_name: str = "Fora",
    ) -> list[ExtendedMarketPick]:
        picks: list[ExtendedMarketPick] = []

        if odds.handicap_away >= 1.05:
            picks.append(self._handicap_away(ctx, odds, away_name))
        if odds.handicap_home >= 1.05:
            picks.append(self._handicap_home(ctx, odds, home_name))
        if odds.corners_over >= 1.05 and odds.corners_current is not None:
            picks.append(self._corners_over(ctx, odds))
            picks.append(self._corners_under(ctx, odds))
        elif odds.corners_over >= 1.05:
            picks.append(self._corners_over_estimated(ctx, odds))
        if odds.home_team_goals_over >= 1.05:
            picks.append(self._home_team_goals_over(ctx, odds, home_name))
        if odds.second_half_home >= 1.05:
            picks.extend(self._second_half(ctx, odds, home_name, away_name))

        picks = [p for p in picks if p.status == "available"]
        picks.sort(key=lambda p: p.expected_value, reverse=True)
        return picks

    def _ev(self, prob: float, odd: float) -> float:
        return prob * odd - 1.0

    def _handicap_away(self, ctx: LiveContext, odds: ExtendedOdds, away: str) -> ExtendedMarketPick:
        line = odds.handicap_away_line
        diff = ctx.home_score - ctx.away_score
        rem = ctx.remaining_minutes

        if line == 0.5:
            prob_win = self._prob_away_covers_plus_half(ctx)
        else:
            prob_win = max(0.05, min(0.95, 0.55 + (diff * -0.12) + rem * 0.01))

        imp = 1 / odds.handicap_away
        reasons = [
            f"{away} +{line} cobre empate e vitória fora",
            f"Marcador {ctx.home_score}-{ctx.away_score}, faltam ~{rem:.0f} min",
            f"Modelo: {prob_win*100:.0f}% vs mercado {imp*100:.0f}%",
        ]
        if ctx.home_xg > ctx.away_xg * 3:
            reasons.append("Brasil domina xG mas precisa de golo vencedor — +0.5 protege empate")

        return ExtendedMarketPick(
            market_type=ExtendedMarketType.HANDICAP_AWAY,
            label=f"{away} +{line} (AH)",
            odd=odds.handicap_away,
            model_prob=prob_win,
            implied_prob=imp,
            expected_value=self._ev(prob_win, odds.handicap_away),
            reasoning=reasons,
        )

    def _handicap_home(self, ctx: LiveContext, odds: ExtendedOdds, home: str) -> ExtendedMarketPick:
        line = odds.handicap_home_line
        rem = ctx.remaining_minutes
        prob = max(0.05, min(0.28, 0.06 + (ctx.home_xg - ctx.away_xg) * 0.08 + rem * 0.008))
        if ctx.home_score < ctx.away_score:
            prob *= 0.5

        imp = 1 / odds.handicap_home
        return ExtendedMarketPick(
            market_type=ExtendedMarketType.HANDICAP_HOME,
            label=f"{home} {line} (AH)",
            odd=odds.handicap_home,
            model_prob=prob,
            implied_prob=imp,
            expected_value=self._ev(prob, odds.handicap_home),
            reasoning=[
                f"Casa precisa vencer por {abs(line)+1} golos a partir de {ctx.home_score}-{ctx.away_score}",
                f"Prob. modelo {prob*100:.0f}% — aposta de alto risco",
            ],
        )

    def _prob_away_covers_plus_half(self, ctx: LiveContext) -> float:
        diff = ctx.home_score - ctx.away_score
        rem = min(ctx.remaining_minutes, 20)
        if diff < 0:
            base = 0.90
        elif diff == 0:
            base = 0.80 - rem * 0.012
        else:
            base = 0.40
        if diff == 0 and ctx.home_xg > ctx.away_xg * 2:
            base -= 0.06
        return max(0.50, min(0.90, base))

    def _corners_over(self, ctx: LiveContext, odds: ExtendedOdds) -> ExtendedMarketPick:
        current = odds.corners_current or 0
        need = int(odds.corners_line) + 1 - current
        rem = ctx.remaining_minutes
        rate = 0.35 if ctx.home_possession > 0.6 else 0.25
        prob = max(0.05, min(0.85, 1 - (0.55 ** max(need, 1)) * (1 + rem * rate * 0.02)))

        return ExtendedMarketPick(
            market_type=ExtendedMarketType.CORNERS_OVER,
            label=f"Cantos Over {odds.corners_line}",
            odd=odds.corners_over,
            model_prob=prob,
            implied_prob=1 / odds.corners_over,
            expected_value=self._ev(prob, odds.corners_over),
            reasoning=[
                f"Cantos actuais: {current}, precisa de +{max(need,0)}",
                f"Brasil a atacar ({ctx.home_possession*100:.0f}% posse) favorece cantos",
            ],
        )

    def _corners_under(self, ctx: LiveContext, odds: ExtendedOdds) -> ExtendedMarketPick:
        over = self._corners_over(ctx, odds)
        prob = 1 - over.model_prob
        return ExtendedMarketPick(
            market_type=ExtendedMarketType.CORNERS_UNDER,
            label=f"Cantos Under {odds.corners_line}",
            odd=odds.corners_under,
            model_prob=prob,
            implied_prob=1 / odds.corners_under,
            expected_value=self._ev(prob, odds.corners_under),
            reasoning=["Complemento do mercado de cantos"],
        )

    def _corners_over_estimated(self, ctx: LiveContext, odds: ExtendedOdds) -> ExtendedMarketPick:
        prob = 0.52 if ctx.home_possession > 0.65 and ctx.remaining_minutes > 5 else 0.42
        return ExtendedMarketPick(
            market_type=ExtendedMarketType.CORNERS_OVER,
            label=f"Cantos Over {odds.corners_line} (est.)",
            odd=odds.corners_over,
            model_prob=prob,
            implied_prob=1 / odds.corners_over,
            expected_value=self._ev(prob, odds.corners_over),
            reasoning=[
                "Sem contagem live de cantos — estimativa por posse/pressão",
                "Confirmar no relatório do jogo antes de apostar",
            ],
        )

    def _home_team_goals_over(self, ctx: LiveContext, odds: ExtendedOdds, home: str) -> ExtendedMarketPick:
        line = odds.home_team_goals_line
        current = ctx.home_score
        need = int(line + 0.5) - current
        rem = ctx.remaining_minutes
        lam = ctx.home_xg * (rem / 90) * 1.2
        prob = 1 - (2.718 ** (-lam)) if need <= 1 else max(0.05, lam * 0.4)

        return ExtendedMarketPick(
            market_type=ExtendedMarketType.TEAM_GOALS_HOME_OVER,
            label=f"{home} Over {line} golos",
            odd=odds.home_team_goals_over,
            model_prob=prob,
            implied_prob=1 / odds.home_team_goals_over,
            expected_value=self._ev(prob, odds.home_team_goals_over),
            reasoning=[
                f"{home} tem {current} golos, precisa de +{max(need,0)}",
                f"xG acumulado {ctx.home_xg:.2f}, λ restante ~{lam:.2f}",
            ],
        )

    def _second_half(
        self, ctx: LiveContext, odds: ExtendedOdds, home: str, away: str
    ) -> list[ExtendedMarketPick]:
        picks = []
        h2_home = max(0, ctx.home_score)
        h2_away = max(0, ctx.away_score)
        if ctx.minute > 45:
            pass
        return picks