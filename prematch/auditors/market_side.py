"""Mapeia mercado recomendado → lado / família para o Motivation Gate."""

from __future__ import annotations


def bet_side_from_market(market_label: str) -> str:
    text = (market_label or "").lower()
    if "vitória casa" in text or "dupla hipótese 1x" in text:
        return "home"
    if "vitória fora" in text or "dupla hipótese x2" in text:
        return "away"
    if "empate" in text:
        return "draw"
    if "over" in text or "btts sim" in text:
        return "over"
    if "under" in text or "btts não" in text or "btts nao" in text:
        return "under"
    if "dupla hipótese 12" in text:
        return "other"
    return "other"


def vote_aligns_with_market(
    vote_side: str,
    bet_side: str,
    *,
    market_side: str | None = None,
) -> bool:
    if market_side is not None:
        return market_side == bet_side
    if vote_side == "neutral":
        return False
    if bet_side == "home":
        return vote_side == "home"
    if bet_side == "away":
        return vote_side == "away"
    if bet_side == "draw":
        return vote_side == "neutral"
    if bet_side in ("over", "under"):
        return vote_side in ("home", "away")
    return vote_side in ("home", "away")