from dataclasses import dataclass
from enum import Enum


class MarketType(Enum):
    HOME_WIN = "home_win"
    DRAW = "draw"
    AWAY_WIN = "away_win"
    OVER_25 = "over_25"
    UNDER_25 = "under_25"
    BTTS_YES = "btts_yes"
    BTTS_NO = "btts_no"
    DOUBLE_CHANCE_1X = "double_chance_1x"
    DOUBLE_CHANCE_X2 = "double_chance_x2"
    DOUBLE_CHANCE_12 = "double_chance_12"
    DNB_HOME = "dnb_home"
    DNB_AWAY = "dnb_away"


MARKET_LABELS = {
    MarketType.HOME_WIN: "Vitória Casa",
    MarketType.DRAW: "Empate",
    MarketType.AWAY_WIN: "Vitória Fora",
    MarketType.OVER_25: "Over 2.5",
    MarketType.UNDER_25: "Under 2.5",
    MarketType.BTTS_YES: "BTTS Sim",
    MarketType.BTTS_NO: "BTTS Não",
    MarketType.DOUBLE_CHANCE_1X: "Dupla Hipótese 1X",
    MarketType.DOUBLE_CHANCE_X2: "Dupla Hipótese X2",
    MarketType.DOUBLE_CHANCE_12: "Dupla Hipótese 12",
    MarketType.DNB_HOME: "DNB Casa",
    MarketType.DNB_AWAY: "DNB Fora",
}


@dataclass
class ScoreBreakdown:
    normalized_ev: float
    ev_contribution: float
    conf_contribution: float
    form_contribution: float
    edge: float
    prob_derivation: str


@dataclass
class Market:
    market_type: MarketType
    odd: float
    model_prob: float
    implied_prob: float
    expected_value: float
    confidence: float
    form_score: float
    total_score: float
    reasoning: list[str]
    breakdown: ScoreBreakdown

    @property
    def label(self) -> str:
        return MARKET_LABELS[self.market_type]

    @property
    def ev_percent(self) -> float:
        return self.expected_value * 100