"""Determina win/loss de um mercado face ao resultado final."""

from markets.markets import MARKET_LABELS, MarketType

_LABEL_TO_TYPE = {label: mtype for mtype, label in MARKET_LABELS.items()}


def settle_market(market: str, home_goals: int, away_goals: int) -> str:
    """
    Devolve: win | loss | push
    Mercados desconhecidos → loss (conservador para análise).
    """
    total = home_goals + away_goals
    mtype = _LABEL_TO_TYPE.get(market)

    if mtype == MarketType.HOME_WIN:
        return "win" if home_goals > away_goals else "loss"
    if mtype == MarketType.DRAW:
        return "win" if home_goals == away_goals else "loss"
    if mtype == MarketType.AWAY_WIN:
        return "win" if away_goals > home_goals else "loss"
    if mtype == MarketType.OVER_25:
        return "win" if total > 2 else "loss"
    if mtype == MarketType.UNDER_25:
        return "win" if total <= 2 else "loss"
    if mtype == MarketType.BTTS_YES:
        return "win" if home_goals > 0 and away_goals > 0 else "loss"
    if mtype == MarketType.BTTS_NO:
        return "win" if home_goals == 0 or away_goals == 0 else "loss"
    if mtype == MarketType.DOUBLE_CHANCE_1X:
        return "win" if home_goals >= away_goals else "loss"
    if mtype == MarketType.DOUBLE_CHANCE_X2:
        return "win" if away_goals >= home_goals else "loss"
    if mtype == MarketType.DOUBLE_CHANCE_12:
        return "win" if home_goals != away_goals else "loss"

    lower = market.lower()
    if "over" in lower and "2.5" in lower:
        return "win" if total > 2 else "loss"
    if "under" in lower and "2.5" in lower:
        return "win" if total <= 2 else "loss"
    if "btts" in lower and "sim" in lower:
        return "win" if home_goals > 0 and away_goals > 0 else "loss"
    if "btts" in lower and ("não" in lower or "nao" in lower):
        return "win" if home_goals == 0 or away_goals == 0 else "loss"

    return "loss"


def pnl_for_outcome(
    outcome: str,
    odd: float,
    stake_amount: float | None,
) -> float | None:
    if stake_amount is None or stake_amount <= 0:
        return None
    if outcome == "win":
        return round(stake_amount * (odd - 1.0), 2)
    if outcome == "loss":
        return round(-stake_amount, 2)
    return 0.0