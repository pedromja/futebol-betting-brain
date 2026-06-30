from dataclasses import dataclass

from models.poisson import PoissonModel, ScoreMatrix
from models.team_stats import MatchInput, MatchOdds

from .markets import MARKET_LABELS, Market, MarketType, ScoreBreakdown


PROB_DERIVATION = {
    MarketType.HOME_WIN: "Soma P(h>a) em todos os resultados da matriz Poisson",
    MarketType.DRAW: "Soma P(h=a) em todos os resultados da matriz Poisson",
    MarketType.AWAY_WIN: "Soma P(h<a) em todos os resultados da matriz Poisson",
    MarketType.OVER_25: "Soma P(h+a > 2.5) — total de golos superior a 2.5",
    MarketType.UNDER_25: "Soma P(h+a ≤ 2.5) — total de golos igual ou inferior a 2.5",
    MarketType.BTTS_YES: "Soma P(h>0 e a>0) — ambas as equipas marcam",
    MarketType.BTTS_NO: "Soma P(h=0 ou a=0) — pelo menos uma equipa não marca",
    MarketType.DOUBLE_CHANCE_1X: "P(vitória casa) + P(empate)",
    MarketType.DOUBLE_CHANCE_X2: "P(empate) + P(vitória fora)",
    MarketType.DOUBLE_CHANCE_12: "P(vitória casa) + P(vitória fora)",
}


@dataclass
class LambdaBreakdown:
    home_attack: float
    away_defense_factor: float
    home_advantage: float
    away_attack: float
    home_defense_factor: float
    league_avg: float
    home_formula: str
    away_formula: str


@dataclass
class MarketRecommendation:
    best: Market | None
    all_markets: list[Market]
    should_bet: bool
    matrix: ScoreMatrix
    home_lambda: float
    away_lambda: float
    lambda_breakdown: LambdaBreakdown
    min_score: float


class MarketEvaluator:
    MIN_ODD = 1.05
    EV_WEIGHT = 0.40
    CONF_WEIGHT = 0.35
    FORM_WEIGHT = 0.25

    def __init__(self, min_score: float = 0.55):
        self.min_score = min_score
        self.model = PoissonModel()

    @staticmethod
    def _implied_prob(odd: float) -> float:
        if odd <= 0:
            return 0.0
        return 1.0 / odd

    @staticmethod
    def _expected_value(model_prob: float, odd: float) -> float:
        return model_prob * odd - 1.0

    @staticmethod
    def _blend_model_prob(
        model_prob: float,
        implied_prob: float,
        match: MatchInput,
    ) -> tuple[float, float, int]:
        """
        Com poucos jogos, puxa a probabilidade do modelo para a odd do mercado.
        Evita EV absurdos (ex.: 94%) quando a amostra é de 3 jogos do Mundial.
        """
        min_games = min(match.home.games_played, match.away.games_played)
        trust = min(min_games / 10.0, 1.0)
        gap = abs(model_prob - implied_prob)
        if min_games < 8 and gap > 0.12:
            trust = min(trust, 0.20 + min_games * 0.05)
        blended = trust * model_prob + (1.0 - trust) * implied_prob
        return blended, trust, min_games

    def _model_confidence(self, match: MatchInput, model_prob: float) -> float:
        sample_factor = min(
            match.home.games_played, match.away.games_played
        ) / 10.0
        sample_factor = min(sample_factor, 1.0)
        certainty = abs(model_prob - 0.5) * 2
        return min(0.95, 0.35 + certainty * 0.35 + sample_factor * 0.25)

    def _form_score(self, match: MatchInput, market_type: MarketType) -> float:
        home = match.home
        away = match.away
        combined_attack = (home.scoring_consistency + away.scoring_consistency) / 2
        combined_defense = (
            home.conceding_consistency + away.conceding_consistency
        ) / 2

        if market_type in (MarketType.OVER_25, MarketType.BTTS_YES):
            return combined_attack * 0.6 + combined_defense * 0.4
        if market_type in (MarketType.UNDER_25, MarketType.BTTS_NO):
            return (1 - combined_attack) * 0.5 + (1 - combined_defense) * 0.5
        if market_type == MarketType.HOME_WIN:
            return home.scoring_consistency * 0.6 + (1 - away.scoring_consistency) * 0.4
        if market_type == MarketType.AWAY_WIN:
            return away.scoring_consistency * 0.6 + (1 - home.scoring_consistency) * 0.4
        if market_type == MarketType.DRAW:
            balance = 1 - abs(home.attack_rating - away.attack_rating) / 2.5
            return max(0.0, min(1.0, balance))
        if market_type == MarketType.DOUBLE_CHANCE_1X:
            return home.scoring_consistency * 0.5 + 0.3
        if market_type == MarketType.DOUBLE_CHANCE_X2:
            return away.scoring_consistency * 0.5 + 0.3
        return 0.5

    def _normalize_ev(self, ev: float) -> float:
        # Saturação em ~25% EV — 94% não deve pesar igual a 25%
        return max(0.0, min(1.0, (ev + 0.05) / 0.30))

    def _total_score(self, ev: float, confidence: float, form_score: float) -> float:
        return (
            self._normalize_ev(ev) * self.EV_WEIGHT
            + confidence * self.CONF_WEIGHT
            + form_score * self.FORM_WEIGHT
        )

    def _score_breakdown(
        self, ev: float, confidence: float, form_score: float, market_type: MarketType,
        model_prob: float, implied_prob: float,
    ) -> ScoreBreakdown:
        norm_ev = self._normalize_ev(ev)
        return ScoreBreakdown(
            normalized_ev=norm_ev,
            ev_contribution=norm_ev * self.EV_WEIGHT,
            conf_contribution=confidence * self.CONF_WEIGHT,
            form_contribution=form_score * self.FORM_WEIGHT,
            edge=model_prob - implied_prob,
            prob_derivation=PROB_DERIVATION[market_type],
        )

    def _lambda_breakdown(self, match: MatchInput) -> LambdaBreakdown:
        home = match.home
        away = match.away
        league = match.league_avg_goals
        adv = match.home_advantage

        home_attack = home.goals_scored_avg
        away_def_factor = away.goals_conceded_avg / league
        away_attack = away.goals_scored_avg
        home_def_factor = home.goals_conceded_avg / league

        home_lambda = home_attack * away_def_factor * adv
        away_lambda = away_attack * home_def_factor

        home_formula = (
            f"{home_attack:.2f} × ({away.goals_conceded_avg:.2f}/{league:.2f}) "
            f"× {adv:.2f} = {home_lambda:.3f}"
        )
        away_formula = (
            f"{away_attack:.2f} × ({home.goals_conceded_avg:.2f}/{league:.2f}) "
            f"= {away_lambda:.3f}"
        )

        return LambdaBreakdown(
            home_attack=home_attack,
            away_defense_factor=away_def_factor,
            home_advantage=adv,
            away_attack=away_attack,
            home_defense_factor=home_def_factor,
            league_avg=league,
            home_formula=home_formula,
            away_formula=away_formula,
        )

    def _reasoning(
        self,
        market_type: MarketType,
        model_prob: float,
        implied_prob: float,
        ev: float,
        match: MatchInput,
        home_lambda: float,
        away_lambda: float,
        *,
        blended_prob: float | None = None,
        trust: float = 1.0,
        min_games: int = 10,
    ) -> list[str]:
        reasons = []
        label = MARKET_LABELS[market_type]
        used_prob = blended_prob if blended_prob is not None else model_prob
        edge = (used_prob - implied_prob) * 100

        reasons.append(
            f"Modelo Poisson: {model_prob * 100:.1f}% vs odd implícita {implied_prob * 100:.1f}%"
        )
        if blended_prob is not None and trust < 0.95:
            reasons.append(
                f"Poucos jogos ({min_games}) — prob. usada no EV: {blended_prob * 100:.1f}% "
                f"(mercado pesa mais quando a amostra é curta)"
            )
        if ev > 0:
            reasons.append(f"Valor esperado positivo ({ev * 100:+.1f}%)")
        else:
            reasons.append(f"Sem valor estatístico ({ev * 100:+.1f}%)")

        if market_type in (MarketType.OVER_25, MarketType.UNDER_25):
            reasons.append(
                f"Golos esperados: {home_lambda:.2f} (casa) + {away_lambda:.2f} (fora) = {home_lambda + away_lambda:.2f}"
            )
        if market_type in (MarketType.BTTS_YES, MarketType.BTTS_NO):
            reasons.append(
                f"{match.home.name} marcou em {match.home.scored_in_last_n}/{match.home.last_n} jogos"
            )
            reasons.append(
                f"{match.away.name} marcou em {match.away.scored_in_last_n}/{match.away.last_n} jogos"
            )
        if market_type == MarketType.HOME_WIN:
            reasons.append(f"Vantagem casa aplicada no modelo Poisson")
        if edge > 5:
            reasons.append(f"Edge significativo de {edge:+.1f} pontos percentuais")

        return reasons

    def _evaluate_single(
        self,
        market_type: MarketType,
        odd: float,
        model_prob: float,
        match: MatchInput,
        home_lambda: float,
        away_lambda: float,
    ) -> Market | None:
        if odd < self.MIN_ODD:
            return None

        implied = self._implied_prob(odd)
        blended_prob, trust, min_games = self._blend_model_prob(
            model_prob, implied, match
        )
        ev = self._expected_value(blended_prob, odd)
        confidence = self._model_confidence(match, blended_prob)
        form_score = self._form_score(match, market_type)
        score = self._total_score(ev, confidence, form_score)
        breakdown = self._score_breakdown(
            ev, confidence, form_score, market_type, blended_prob, implied
        )
        reasoning = self._reasoning(
            market_type,
            model_prob,
            implied,
            ev,
            match,
            home_lambda,
            away_lambda,
            blended_prob=blended_prob,
            trust=trust,
            min_games=min_games,
        )

        return Market(
            market_type=market_type,
            odd=odd,
            model_prob=blended_prob,
            implied_prob=implied,
            expected_value=ev,
            confidence=confidence,
            form_score=form_score,
            total_score=score,
            reasoning=reasoning,
            breakdown=breakdown,
        )

    def evaluate(self, match: MatchInput) -> MarketRecommendation:
        lambda_bd = self._lambda_breakdown(match)
        matrix = self.model.build_matrix(match)
        home_lambda, away_lambda = matrix.home_lambda, matrix.away_lambda
        odds = match.odds

        candidates = [
            (MarketType.HOME_WIN, odds.home_win, matrix.prob_home_win()),
            (MarketType.DRAW, odds.draw, matrix.prob_draw()),
            (MarketType.AWAY_WIN, odds.away_win, matrix.prob_away_win()),
            (MarketType.OVER_25, odds.over_25, matrix.prob_over(2.5)),
            (MarketType.UNDER_25, odds.under_25, matrix.prob_under(2.5)),
            (MarketType.BTTS_YES, odds.btts_yes, matrix.prob_btts_yes()),
            (MarketType.BTTS_NO, odds.btts_no, matrix.prob_btts_no()),
        ]

        if odds.double_chance_1x >= self.MIN_ODD:
            candidates.append(
                (MarketType.DOUBLE_CHANCE_1X, odds.double_chance_1x, matrix.prob_double_chance_1x())
            )
        if odds.double_chance_x2 >= self.MIN_ODD:
            candidates.append(
                (MarketType.DOUBLE_CHANCE_X2, odds.double_chance_x2, matrix.prob_double_chance_x2())
            )
        if odds.double_chance_12 >= self.MIN_ODD:
            candidates.append(
                (MarketType.DOUBLE_CHANCE_12, odds.double_chance_12, matrix.prob_double_chance_12())
            )

        markets: list[Market] = []
        for mtype, odd, prob in candidates:
            result = self._evaluate_single(
                mtype, odd, prob, match, home_lambda, away_lambda
            )
            if result:
                markets.append(result)

        markets.sort(key=lambda m: m.total_score, reverse=True)
        best = markets[0] if markets else None
        should_bet = best is not None and best.total_score >= self.min_score

        return MarketRecommendation(
            best=best,
            all_markets=markets,
            should_bet=should_bet,
            matrix=matrix,
            home_lambda=home_lambda,
            away_lambda=away_lambda,
            lambda_breakdown=lambda_bd,
            min_score=self.min_score,
        )