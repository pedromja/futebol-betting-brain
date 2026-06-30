"""Correspondência de mercados nos filtros dos bots — inclui favorito e variantes HT."""

from __future__ import annotations

import re

_FAVORITE_WIN = frozenset(
    {
        "vitória favorito",
        "vence favorito",
        "vitoria favorito",
    }
)
_FAVORITE_DC = frozenset(
    {
        "dupla hipótese favorito",
        "vence ou empata favorito",
        "empate ou vence favorito",
        "favorito 1x",
        "favorito x2",
    }
)
_HT_MARKERS = (" ht", " intervalo", " 1.º tempo", " 1o tempo", " primeiro tempo")
_OVER_IMPLIES: dict[str, tuple[str, ...]] = {
    "over 2.5": ("over 1.5",),
    "over 3.5": ("over 2.5", "over 1.5"),
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _labels(match: dict) -> list[str]:
    labels = [_norm(match.get("best_market"))]
    for row in match.get("top_markets") or []:
        raw = str(row)
        labels.append(_norm(raw.split(" (")[0]))
    for row in match.get("extended_markets") or []:
        if isinstance(row, dict):
            labels.append(_norm(row.get("label") or row.get("market")))
        else:
            labels.append(_norm(row))
    return [l for l in labels if l]


def _direct_match(label: str, filt: str) -> bool:
    if not label or not filt:
        return False
    if filt in label or label in filt:
        return True
    for marker in _HT_MARKERS:
        if marker in filt:
            if marker in label and filt.replace(marker, "").strip() in label:
                return True
    return False


def _favorite_win_match(match: dict, labels: list[str]) -> bool:
    side = match.get("favorite_side")
    if side == "home":
        target = "vitória casa"
    elif side == "away":
        target = "vitória fora"
    else:
        return False
    return any(target in l for l in labels)


def _favorite_dc_match(match: dict, labels: list[str]) -> bool:
    side = match.get("favorite_side")
    if side == "home":
        target = "dupla hipótese 1x"
    elif side == "away":
        target = "dupla hipótese x2"
    else:
        return False
    return any(target in l for l in labels)


def _over_implied_match(labels: list[str], filt: str) -> bool:
    for label in labels:
        for stronger, implied in _OVER_IMPLIES.items():
            if stronger in label and filt in implied:
                return True
    return False


def market_matches_filter(match: dict, filter_market: str) -> bool:
    filt = _norm(filter_market)
    if not filt:
        return True

    labels = _labels(match)
    if any(_direct_match(l, filt) for l in labels):
        return True

    if filt in _FAVORITE_WIN:
        return _favorite_win_match(match, labels)
    if filt in _FAVORITE_DC:
        return _favorite_dc_match(match, labels)

    if filt.startswith("over ") and " ht" not in filt:
        return _over_implied_match(labels, filt)

    return False