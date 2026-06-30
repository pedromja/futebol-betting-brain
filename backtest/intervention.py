"""Política de intervenção — rank mais ou menos agressivo conforme spread de odds."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OddSpreadInfo:
    home_odd: float
    away_odd: float
    spread_abs: float
    spread_ratio: float
    tier: str
    label: str


@dataclass(frozen=True)
class InterventionThresholds:
    """Limites efectivos para emitir dica — derivados do tier de spread."""

    tier: str
    min_score: float
    min_ev_pct: float
    min_pattern_score: float
    min_reaction_score: float
    interventive: bool


TIER_LABELS = {
    "tight": "Equilibrado (spread baixo)",
    "moderate": "Moderado",
    "clear_fav": "Favorito claro (mais interventivo)",
}

# Spread relativo = |home-away| / min(home, away)
TIER_BOUNDS = (
    ("tight", 0.0, 0.22),
    ("moderate", 0.22, 0.55),
    ("clear_fav", 0.55, 99.0),
)

BASE_MIN_SCORE = 0.55
BASE_MIN_EV_PCT = 3.0
BASE_PATTERN_SCORE = 50.0
BASE_REACTION_SCORE = 55.0


def classify_odd_spread(home_odd: float | None, away_odd: float | None) -> OddSpreadInfo | None:
    try:
        h = float(home_odd or 0)
        a = float(away_odd or 0)
    except (TypeError, ValueError):
        return None
    if h <= 1.01 or a <= 1.01:
        return None
    spread_abs = abs(h - a)
    spread_ratio = spread_abs / min(h, a)
    tier = "moderate"
    for name, lo, hi in TIER_BOUNDS:
        if lo <= spread_ratio < hi:
            tier = name
            break
    return OddSpreadInfo(
        home_odd=h,
        away_odd=a,
        spread_abs=round(spread_abs, 3),
        spread_ratio=round(spread_ratio, 3),
        tier=tier,
        label=TIER_LABELS.get(tier, tier),
    )


def intervention_thresholds(
    spread: OddSpreadInfo | None,
    *,
    base_min_score: float = BASE_MIN_SCORE,
) -> InterventionThresholds:
    tier = spread.tier if spread else "moderate"
    if tier == "tight":
        return InterventionThresholds(
            tier=tier,
            min_score=base_min_score + 0.08,
            min_ev_pct=BASE_MIN_EV_PCT + 2.0,
            min_pattern_score=BASE_PATTERN_SCORE + 12.0,
            min_reaction_score=BASE_REACTION_SCORE + 8.0,
            interventive=False,
        )
    if tier == "clear_fav":
        return InterventionThresholds(
            tier=tier,
            min_score=max(0.48, base_min_score - 0.06),
            min_ev_pct=max(1.5, BASE_MIN_EV_PCT - 1.5),
            min_pattern_score=max(38.0, BASE_PATTERN_SCORE - 12.0),
            min_reaction_score=max(45.0, BASE_REACTION_SCORE - 10.0),
            interventive=True,
        )
    return InterventionThresholds(
        tier="moderate",
        min_score=base_min_score,
        min_ev_pct=BASE_MIN_EV_PCT,
        min_pattern_score=BASE_PATTERN_SCORE,
        min_reaction_score=BASE_REACTION_SCORE,
        interventive=True,
    )


def passes_intervention_gate(
    *,
    score: float | None,
    ev_pct: float | None,
    pattern_score: float | None = None,
    reaction_score: float | None = None,
    thresholds: InterventionThresholds,
    require_pattern: bool = False,
) -> bool:
    if score is None:
        return False
    if score < thresholds.min_score:
        return False
    if ev_pct is not None and ev_pct < thresholds.min_ev_pct:
        return False
    if require_pattern:
        if pattern_score is not None and pattern_score < thresholds.min_pattern_score:
            return False
        if reaction_score is not None and reaction_score < thresholds.min_reaction_score:
            return False
    return True