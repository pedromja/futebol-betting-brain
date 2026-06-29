"""Dimensionamento de aposta — Kelly fraccional."""

from dataclasses import dataclass


@dataclass
class StakeSizing:
    kelly_full: float
    kelly_fraction: float
    stake_amount: float
    stake_percent: float
    edge: float


def fractional_kelly(
    model_prob: float,
    odd: float,
    bankroll: float,
    fraction: float = 0.25,
    max_stake_pct: float = 0.05,
) -> StakeSizing | None:
    """
    Kelly fraccional com tecto de risco.

    fraction=0.25 → quarter-Kelly (conservador).
    max_stake_pct → nunca mais de X% da banca numa aposta.
    """
    if bankroll <= 0 or odd <= 1.0 or model_prob <= 0:
        return None

    b = odd - 1.0
    q = 1.0 - model_prob
    kelly_full = (model_prob * b - q) / b
    if kelly_full <= 0:
        return None

    kelly_frac = kelly_full * max(0.0, min(1.0, fraction))
    kelly_frac = min(kelly_frac, max_stake_pct)
    stake = round(bankroll * kelly_frac, 2)
    if stake <= 0:
        return None

    implied = 1.0 / odd
    return StakeSizing(
        kelly_full=round(kelly_full, 4),
        kelly_fraction=round(kelly_frac, 4),
        stake_amount=stake,
        stake_percent=round(kelly_frac * 100, 2),
        edge=round(model_prob - implied, 4),
    )