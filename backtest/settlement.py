"""Settlement estendido para mercados IA no backtest."""

from __future__ import annotations

from history.market_settlement import settle_market

DEFAULT_CORNERS_LINE = 9.5


def _norm(market: str) -> str:
    return str(market or "").strip().lower()


def settle_ia_market(
    market: str,
    *,
    home_goals: int,
    away_goals: int,
    home_corners: int,
    away_corners: int,
    favorite_side: str = "none",
) -> str:
    m = _norm(market)
    total_goals = home_goals + away_goals
    total_corners = home_corners + away_corners

    if "cantos over" in m:
        line = DEFAULT_CORNERS_LINE
        for token in m.replace(",", ".").split():
            try:
                val = float(token)
                if 4.0 <= val <= 14.0:
                    line = val
                    break
            except ValueError:
                continue
        return "win" if total_corners > line else "loss"

    if "cantos under" in m:
        line = DEFAULT_CORNERS_LINE
        return "win" if total_corners < line else "loss"

    if "over 1.5" in m and "golos" not in m:
        return "win" if total_goals > 1 else "loss"
    if "over 2.5" in m:
        return "win" if total_goals > 2 else "loss"
    if "under 2.5" in m:
        return "win" if total_goals <= 2 else "loss"

    if "vitória favorito" in m or "vitoria favorito" in m:
        if favorite_side == "home":
            return settle_market("Vitória Casa", home_goals, away_goals)
        if favorite_side == "away":
            return settle_market("Vitória Fora", home_goals, away_goals)
        return "loss"

    if "dnb casa" in m:
        return settle_market("DNB Casa", home_goals, away_goals)
    if "dnb fora" in m:
        return settle_market("DNB Fora", home_goals, away_goals)

    if "dupla hipótese 1x" in m or "dupla hipotese 1x" in m:
        return settle_market("Dupla Hipótese 1X", home_goals, away_goals)
    if "dupla hipótese x2" in m:
        return settle_market("Dupla Hipótese X2", home_goals, away_goals)

    return settle_market(market, home_goals, away_goals)