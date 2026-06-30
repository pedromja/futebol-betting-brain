"""Regras de emissão — janelas J1-J4 e cooldown 15 min por mercado."""

from __future__ import annotations

from discovery.espn_commentary import phase_window_for_minute

MARKET_COOLDOWN_MINUTES = 15


def current_phase_window(minute: int) -> str | None:
    return phase_window_for_minute(minute)


def _norm_market(market: str) -> str:
    return (market or "").strip().lower()


def filter_tips(
    tips: list[dict],
    *,
    current_minute: int,
    recent_signals: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Filtra dicas propostas.
    Devolve (aceites, rejeitadas).
    """
    phase = current_phase_window(current_minute)
    accepted: list[dict] = []
    rejected: list[dict] = []

    for tip in tips:
        market = _norm_market(str(tip.get("market") or ""))
        if not market:
            rejected.append({**tip, "reject_reason": "mercado_vazio"})
            continue

        tip_phase = str(tip.get("phase_window") or "").upper() or phase
        if phase and tip_phase and tip_phase != phase:
            rejected.append({**tip, "reject_reason": f"fase_{tip_phase}_vs_{phase}"})
            continue

        blocked = False
        for prev in recent_signals:
            prev_market = _norm_market(str(prev.get("market") or ""))
            if prev_market != market:
                continue
            try:
                prev_min = int(prev.get("minute") or 0)
            except (TypeError, ValueError):
                prev_min = 0
            if current_minute - prev_min < MARKET_COOLDOWN_MINUTES:
                rejected.append(
                    {**tip, "reject_reason": f"cooldown_15m_{prev_market}"}
                )
                blocked = True
                break
        if blocked:
            continue

        out = dict(tip)
        out["phase_window"] = tip_phase or phase
        out["minute"] = current_minute
        accepted.append(out)

    return accepted, rejected