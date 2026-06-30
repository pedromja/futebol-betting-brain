"""Pilar 1 — Market Value Gap vs odds implícitas."""

from __future__ import annotations

import math

from prematch.transfermarkt.types import ValueGapInsight


def _implied_probs(odds: dict) -> tuple[float, float, float]:
    hw = float(odds.get("home_win") or 0)
    dr = float(odds.get("draw") or 0)
    aw = float(odds.get("away_win") or 0)
    if hw <= 1 or dr <= 1 or aw <= 1:
        return 0.33, 0.34, 0.33
    inv = [1 / hw, 1 / dr, 1 / aw]
    total = sum(inv)
    return inv[0] / total, inv[1] / total, inv[2] / total


def _expected_home_from_ratio(ratio: float) -> float:
    if ratio <= 0:
        return 0.33
    log_r = math.log10(max(ratio, 0.05))
    prob = 0.50 + 0.14 * log_r
    return max(0.12, min(0.88, prob))


def compute_value_gap(
    home_value_m: float,
    away_value_m: float,
    odds_hint: dict | None,
) -> ValueGapInsight | None:
    if home_value_m <= 0 and away_value_m <= 0:
        return None
    home_v = max(home_value_m, 0.1)
    away_v = max(away_value_m, 0.1)
    ratio = home_v / away_v
    expected_home = _expected_home_from_ratio(ratio)
    implied_home, _, implied_away = _implied_probs(odds_hint or {})
    gap = (expected_home - implied_home) * 100

    if ratio >= 3 and gap >= 8:
        signal = "home_undervalued"
        label = f"Plantel casa ~{ratio:.0f}× mais valioso — odd casa pode estar alta (valor)"
    elif ratio <= 0.35 and (implied_away - (1 - expected_home)) * 100 >= 8:
        signal = "away_undervalued"
        label = f"Plantel fora superior em valor — mercado pode subestimar a fora"
    elif abs(gap) < 5:
        signal = "fair"
        label = "Valor de plantel alinhado com as odds"
    elif gap <= -8:
        signal = "home_overpriced"
        label = "Odd casa baixa face ao valor relativo dos plantéis"
    else:
        signal = "away_overpriced"
        label = "Mercado precifica fora acima do fosso de valor"

    return ValueGapInsight(
        home_value_m=home_v,
        away_value_m=away_v,
        ratio=ratio,
        expected_home_prob=expected_home,
        implied_home_prob=implied_home,
        gap_pct=gap,
        signal=signal,
        label=label,
    )