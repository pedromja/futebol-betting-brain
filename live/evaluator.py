"""Avaliador de mercados ao vivo."""

from dataclasses import dataclass

from markets.evaluator import MarketEvaluator, MarketRecommendation
from markets.markets import Market, MarketType
from models.poisson import PoissonModel
from models.team_stats import MatchInput
from stakes.types import MatchStakesReport

from .poisson import build_live_matrix, remaining_lambdas
from .types import LiveAnalysisMeta, LiveMarketNote, LiveMarketStatus, LiveMatchState


class LiveMarketEvaluator(MarketEvaluator):
    def _live_market_status(
        self, mtype: MarketType, state: LiveMatchState
    ) -> LiveMarketNote | None:
        total = state.total_goals

        if mtype == MarketType.BTTS_YES:
            if state.btts_settled_yes:
                return LiveMarketNote("BTTS Sim", LiveMarketStatus.SETTLED_WON, "Ambas já marcaram")
            return None
        if mtype == MarketType.BTTS_NO:
            if state.btts_settled_yes:
                return LiveMarketNote("BTTS Não", LiveMarketStatus.SETTLED_LOST, "Ambas já marcaram")
            if state.home_score == 0 and state.away_score == 0:
                return None
            return None

        if mtype == MarketType.OVER_25:
            if total > 2:
                return LiveMarketNote("Over 2.5", LiveMarketStatus.SETTLED_WON, f"Já há {total} golos")
            return None
        if mtype == MarketType.UNDER_25:
            if total > 2:
                return LiveMarketNote("Under 2.5", LiveMarketStatus.SETTLED_LOST, f"Já há {total} golos")
            need = 3 - total
            if need > 3 and state.minute >= 85:
                return LiveMarketNote(
                    "Under 2.5",
                    LiveMarketStatus.AVAILABLE,
                    f"Faltam {state.remaining_minutes:.0f}min, máx {need - 1} golos para falhar",
                )
            return None

        return None

    def evaluate_live(
        self,
        match: MatchInput,
        state: LiveMatchState,
        stakes_report: MatchStakesReport | None = None,
    ) -> tuple[MarketRecommendation, LiveAnalysisMeta]:
        poisson = PoissonModel()
        lam_h_full, lam_a_full = poisson.expected_goals(match)

        home_urg = stakes_report.home.urgency if stakes_report else 1.0
        away_urg = stakes_report.away.urgency if stakes_report else 1.0
        home_urg *= stakes_report.home.attack_mult if stakes_report else 1.0
        away_urg *= stakes_report.away.attack_mult if stakes_report else 1.0

        lam_h_rem, lam_a_rem = remaining_lambdas(
            match, state, lam_h_full, lam_a_full, home_urg, away_urg
        )
        matrix = build_live_matrix(state, lam_h_rem, lam_a_rem)
        notes: list[LiveMarketNote] = []

        lambda_bd = self._lambda_breakdown(match)
        odds = match.odds

        candidates: list[tuple[MarketType, float, float]] = [
            (MarketType.HOME_WIN, odds.home_win, matrix.prob_home_win()),
            (MarketType.DRAW, odds.draw, matrix.prob_draw()),
            (MarketType.AWAY_WIN, odds.away_win, matrix.prob_away_win()),
            (MarketType.OVER_25, odds.over_25, self._prob_over_live(matrix, state)),
            (MarketType.UNDER_25, odds.under_25, self._prob_under_live(matrix, state)),
            (MarketType.BTTS_YES, odds.btts_yes, self._prob_btts_yes_live(matrix, state)),
            (MarketType.BTTS_NO, odds.btts_no, self._prob_btts_no_live(matrix, state)),
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
            status_note = self._live_market_status(mtype, state)
            if status_note:
                notes.append(status_note)
                if status_note.status in (
                    LiveMarketStatus.SETTLED_WON,
                    LiveMarketStatus.SETTLED_LOST,
                ):
                    continue

            result = self._evaluate_single(
                mtype, odd, prob, match, lam_h_rem, lam_a_rem
            )
            if result:
                if status_note and status_note.status == LiveMarketStatus.UNAVAILABLE:
                    continue
                markets.append(result)

        markets.sort(key=lambda m: m.total_score, reverse=True)
        best = markets[0] if markets else None
        should_bet = best is not None and best.total_score >= self.min_score

        meta = LiveAnalysisMeta(
            state=state,
            home_lambda_remaining=lam_h_rem,
            away_lambda_remaining=lam_a_rem,
            home_lambda_full=lam_h_full,
            away_lambda_full=lam_a_full,
            market_notes=notes,
        )

        rec = MarketRecommendation(
            best=best,
            all_markets=markets,
            should_bet=should_bet,
            matrix=matrix,
            home_lambda=lam_h_rem,
            away_lambda=lam_a_rem,
            lambda_breakdown=lambda_bd,
            min_score=self.min_score,
        )
        return rec, meta

    @staticmethod
    def _prob_over_live(matrix, state: LiveMatchState) -> float:
        if state.total_goals > 2:
            return 1.0
        return sum(
            p for (h, a), p in matrix.matrix.items() if h + a > 2.5
        )

    @staticmethod
    def _prob_under_live(matrix, state: LiveMatchState) -> float:
        if state.total_goals > 2:
            return 0.0
        return sum(
            p for (h, a), p in matrix.matrix.items() if h + a <= 2.5
        )

    @staticmethod
    def _prob_btts_yes_live(matrix, state: LiveMatchState) -> float:
        if state.btts_settled_yes:
            return 1.0
        return sum(
            p for (h, a), p in matrix.matrix.items() if h > 0 and a > 0
        )

    @staticmethod
    def _prob_btts_no_live(matrix, state: LiveMatchState) -> float:
        if state.btts_settled_yes:
            return 0.0
        return sum(
            p for (h, a), p in matrix.matrix.items() if h == 0 or a == 0
        )