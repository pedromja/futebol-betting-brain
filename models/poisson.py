from dataclasses import dataclass
from math import exp, factorial
from typing import Dict, Tuple

from .team_stats import MatchInput


@dataclass
class ScoreMatrix:
    matrix: Dict[Tuple[int, int], float]
    home_lambda: float
    away_lambda: float
    max_goals: int

    def prob(self, home: int, away: int) -> float:
        return self.matrix.get((home, away), 0.0)

    def prob_home_win(self) -> float:
        return sum(p for (h, a), p in self.matrix.items() if h > a)

    def prob_draw(self) -> float:
        return sum(p for (h, a), p in self.matrix.items() if h == a)

    def prob_away_win(self) -> float:
        return sum(p for (h, a), p in self.matrix.items() if h < a)

    def prob_over(self, line: float = 2.5) -> float:
        threshold = int(line)
        if line == int(line):
            return sum(p for (h, a), p in self.matrix.items() if h + a > line)
        return sum(p for (h, a), p in self.matrix.items() if h + a > threshold)

    def prob_under(self, line: float = 2.5) -> float:
        return 1.0 - self.prob_over(line)

    def prob_btts_yes(self) -> float:
        return sum(p for (h, a), p in self.matrix.items() if h > 0 and a > 0)

    def prob_btts_no(self) -> float:
        return 1.0 - self.prob_btts_yes()

    def prob_double_chance_1x(self) -> float:
        return self.prob_home_win() + self.prob_draw()

    def prob_double_chance_x2(self) -> float:
        return self.prob_draw() + self.prob_away_win()

    def prob_double_chance_12(self) -> float:
        return self.prob_home_win() + self.prob_away_win()

    def top_scorelines(self, n: int = 8) -> list[tuple[int, int, float]]:
        ranked = sorted(self.matrix.items(), key=lambda x: x[1], reverse=True)
        return [(h, a, p) for (h, a), p in ranked[:n]]


class PoissonModel:
    def __init__(self, max_goals: int = 8):
        self.max_goals = max_goals

    @staticmethod
    def _poisson(k: int, lam: float) -> float:
        if lam <= 0:
            return 1.0 if k == 0 else 0.0
        return exp(-lam) * (lam**k) / factorial(k)

    def expected_goals(self, match: MatchInput) -> Tuple[float, float]:
        league_avg = match.league_avg_goals
        home = match.home
        away = match.away

        home_lambda = (
            home.goals_scored_avg
            * (away.goals_conceded_avg / league_avg)
            * match.home_advantage
        )
        away_lambda = (
            away.goals_scored_avg
            * (home.goals_conceded_avg / league_avg)
        )

        return round(home_lambda, 3), round(away_lambda, 3)

    def build_matrix(self, match: MatchInput) -> ScoreMatrix:
        home_lambda, away_lambda = self.expected_goals(match)
        matrix: Dict[Tuple[int, int], float] = {}

        for h in range(self.max_goals + 1):
            for a in range(self.max_goals + 1):
                matrix[(h, a)] = self._poisson(h, home_lambda) * self._poisson(
                    a, away_lambda
                )

        total = sum(matrix.values())
        if total > 0:
            matrix = {k: v / total for k, v in matrix.items()}

        return ScoreMatrix(
            matrix=matrix,
            home_lambda=home_lambda,
            away_lambda=away_lambda,
            max_goals=self.max_goals,
        )