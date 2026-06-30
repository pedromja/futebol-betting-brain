"""Determina win/loss/void de um mercado face ao resultado final."""

from markets.markets import MARKET_LABELS, MarketType

_LABEL_TO_TYPE = {label: mtype for mtype, label in MARKET_LABELS.items()}


def is_dnb_market(market: str) -> bool:
    lower = (market or "").lower()
    if _LABEL_TO_TYPE.get(market) in (MarketType.DNB_HOME, MarketType.DNB_AWAY):
        return True
    if "dnb" in lower or "draw no bet" in lower or "empate anula" in lower:
        return True
    if "handicap 0" in lower or "ah 0" in lower:
        return True
    return False


def dnb_side(market: str) -> str | None:
    """'home' | 'away' | None — lado protegido no Draw No Bet."""
    mtype = _LABEL_TO_TYPE.get(market or "")
    if mtype == MarketType.DNB_HOME:
        return "home"
    if mtype == MarketType.DNB_AWAY:
        return "away"
    lower = (market or "").lower()
    if "fora" in lower or "away" in lower or lower.endswith(" 2"):
        return "away"
    if "casa" in lower or "home" in lower or lower.endswith(" 1"):
        return "home"
    return None


def is_1x2_market(market: str) -> bool:
    mtype = _LABEL_TO_TYPE.get(market or "")
    return mtype in (MarketType.HOME_WIN, MarketType.DRAW, MarketType.AWAY_WIN)


def settle_market(market: str, home_goals: int, away_goals: int) -> str:
    """
    Devolve: win | loss | void
    void = empate anula (DNB) ou push — stake devolvido, PnL 0.
    Mercados desconhecidos → loss (conservador para análise).
    """
    if home_goals == away_goals:
        if is_dnb_market(market):
            side = dnb_side(market)
            if side == "home" or side == "away":
                return "void"
        mtype = _LABEL_TO_TYPE.get(market)
        if mtype == MarketType.DNB_HOME or mtype == MarketType.DNB_AWAY:
            return "void"

    total = home_goals + away_goals
    mtype = _LABEL_TO_TYPE.get(market)

    if mtype == MarketType.DNB_HOME:
        if home_goals > away_goals:
            return "win"
        if home_goals < away_goals:
            return "loss"
        return "void"
    if mtype == MarketType.DNB_AWAY:
        if away_goals > home_goals:
            return "win"
        if away_goals < home_goals:
            return "loss"
        return "void"

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
    if is_dnb_market(market) and home_goals == away_goals:
        return "void"
    if "over" in lower and "2.5" in lower:
        return "win" if total > 2 else "loss"
    if "under" in lower and "2.5" in lower:
        return "win" if total <= 2 else "loss"
    if "btts" in lower and "sim" in lower:
        return "win" if home_goals > 0 and away_goals > 0 else "loss"
    if "btts" in lower and ("não" in lower or "nao" in lower):
        return "win" if home_goals == 0 or away_goals == 0 else "loss"

    return "loss"


def settlement_note(market: str, home_goals: int, away_goals: int, outcome: str) -> str:
    """Nota legível para pós-jogo / correcção manual."""
    if home_goals == away_goals:
        if outcome == "void" and is_dnb_market(market):
            return "Empate — DNB void (stake devolvido)"
        if is_1x2_market(market) and _LABEL_TO_TYPE.get(market) != MarketType.DRAW:
            return "Empate — mercado 1X2 perde (não é DNB)"
        if _LABEL_TO_TYPE.get(market) == MarketType.DRAW:
            return "Empate — aposta ao empate ganha"
    if outcome == "void":
        return "Aposta void — stake devolvido"
    return ""


def pnl_for_outcome(
    outcome: str,
    odd: float,
    stake_amount: float | None,
) -> float | None:
    if stake_amount is None or stake_amount <= 0:
        return None
    normalized = str(outcome or "").lower()
    if normalized == "win":
        return round(stake_amount * (odd - 1.0), 2)
    if normalized == "loss":
        return round(-stake_amount, 2)
    if normalized in ("void", "push"):
        return 0.0
    return 0.0