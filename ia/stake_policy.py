"""Stake interna omissa — cap inicial 5 (5% banca), madura até 10."""

from __future__ import annotations

from config.data_paths import IA_LIVE_SIGNALS
from history.tips_history import _read_all_rows

MAX_STAKE_INITIAL = 5.0
MAX_STAKE_MATURE = 10.0
MIN_SAMPLES_MATURE = 10
SATISFACTORY_HIT_RATE = 50.0


def _market_mature(market: str) -> bool:
    """Mercado com ≥10 entradas resolvidas e hit rate satisfatório."""
    rows = _read_all_rows(IA_LIVE_SIGNALS)
    market_l = (market or "").strip().lower()
    wins = losses = 0
    for row in rows:
        if (row.get("market") or "").strip().lower() != market_l:
            continue
        outcome = str(row.get("outcome") or "pending").lower()
        if outcome == "win":
            wins += 1
        elif outcome == "loss":
            losses += 1
    decided = wins + losses
    if decided < MIN_SAMPLES_MATURE:
        return False
    hit = 100.0 * wins / decided if decided else 0.0
    return hit >= SATISFACTORY_HIT_RATE


def apply_stake_policy(tip: dict, *, market: str | None = None) -> dict:
    """Aplica penalizações e cap; stake fica omissa na API pública."""
    market = market or str(tip.get("market") or "")
    try:
        conf = float(tip.get("confidence_pct") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    try:
        stake = float(tip.get("stake_raw") or 0)
    except (TypeError, ValueError):
        stake = 0.0

    align = str(tip.get("prematch_alignment") or "neutral").lower()
    if align == "divergent":
        conf = max(0.0, conf * 0.55)
        stake *= 0.45
    elif align == "neutral":
        stake *= 0.85

    mature = _market_mature(market)
    cap = MAX_STAKE_MATURE if mature else MAX_STAKE_INITIAL
    stake = max(0.0, min(stake, cap))

    return {
        **tip,
        "confidence_pct": round(conf, 1),
        "stake_raw": round(stake, 2),
        "bankroll_pct": round(stake * 1.0, 2),
        "stake_hidden": True,
        "market_mature": mature,
        "stake_cap": cap,
    }


def to_public_tip(tip: dict) -> dict:
    """Remove stake da resposta pública."""
    pub = {k: v for k, v in tip.items() if k not in ("stake_raw", "bankroll_pct", "stake_cap")}
    pub["stake_hidden"] = True
    return pub