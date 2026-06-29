"""Matriz Poisson condicionada ao resultado actual e tempo restante."""

from math import exp, factorial

from models.poisson import ScoreMatrix
from models.team_stats import MatchInput

from .types import LiveMatchState


def _poisson(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return exp(-lam) * (lam**k) / factorial(k)


def remaining_lambdas(
    match: MatchInput,
    state: LiveMatchState,
    home_lambda_full: float,
    away_lambda_full: float,
    home_urgency: float = 1.0,
    away_urgency: float = 1.0,
) -> tuple[float, float]:
    frac = state.remaining_fraction
    lam_h = home_lambda_full * frac * home_urgency
    lam_a = away_lambda_full * frac * away_urgency
    return round(lam_h, 4), round(lam_a, 4)


def build_live_matrix(
    state: LiveMatchState,
    home_lambda_rem: float,
    away_lambda_rem: float,
    max_add: int = 6,
) -> ScoreMatrix:
    """
    Probabilidades de resultado FINAL (90 min regulamentar).
    Soma sobre golos adicionais (dh, da) a partir do marcador actual.
    """
    h0, a0 = state.home_score, state.away_score
    matrix: dict[tuple[int, int], float] = {}

    for dh in range(max_add + 1):
        ph = _poisson(dh, home_lambda_rem)
        for da in range(max_add + 1):
            pa = _poisson(da, away_lambda_rem)
            p = ph * pa
            hf, af = h0 + dh, a0 + da
            key = (hf, af)
            matrix[key] = matrix.get(key, 0.0) + p

    total = sum(matrix.values())
    if total > 0:
        matrix = {k: v / total for k, v in matrix.items()}

    return ScoreMatrix(
        matrix=matrix,
        home_lambda=home_lambda_rem,
        away_lambda=away_lambda_rem,
        max_goals=max(h for h, _ in matrix) if matrix else h0,
    )