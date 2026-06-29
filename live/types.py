"""Estado do jogo ao vivo."""

from dataclasses import dataclass, field
from enum import Enum


class MatchPeriod(str, Enum):
    FIRST_HALF = "1H"
    SECOND_HALF = "2H"
    EXTRA_TIME = "ET"
    PENALTIES = "PEN"


@dataclass
class LiveMatchState:
    home_score: int
    away_score: int
    minute: int
    injury_time: int = 0
    period: MatchPeriod = MatchPeriod.SECOND_HALF
    regulation_minutes: int = 90

    @classmethod
    def from_score_string(
        cls,
        score: str,
        minute: int,
        injury_time: int = 0,
        period: str = "2H",
    ) -> "LiveMatchState":
        parts = score.replace(" ", "").split("-")
        if len(parts) != 2:
            raise ValueError(f"Score inválido: {score!r} (usa formato '1-1')")
        h, a = int(parts[0]), int(parts[1])
        try:
            p = MatchPeriod(period.upper())
        except ValueError:
            p = MatchPeriod.SECOND_HALF
        return cls(
            home_score=h,
            away_score=a,
            minute=minute,
            injury_time=injury_time,
            period=p,
        )

    @property
    def total_goals(self) -> int:
        return self.home_score + self.away_score

    @property
    def score_diff_home(self) -> int:
        return self.home_score - self.away_score

    @property
    def remaining_minutes(self) -> float:
        if self.period == MatchPeriod.FIRST_HALF:
            base = 45 - self.minute
        elif self.period == MatchPeriod.SECOND_HALF:
            base = self.regulation_minutes - self.minute
        elif self.period == MatchPeriod.EXTRA_TIME:
            base = 120 - self.minute
        else:
            base = 0
        return max(1.0, base + self.injury_time)

    @property
    def remaining_fraction(self) -> float:
        """Fracção do tempo regulamentar restante (0–1)."""
        total = float(self.regulation_minutes)
        return max(0.03, min(1.0, self.remaining_minutes / total))

    @property
    def btts_settled_yes(self) -> bool:
        return self.home_score > 0 and self.away_score > 0

    @property
    def over_25_settled(self) -> bool | None:
        if self.total_goals > 2:
            return True
        if self.remaining_minutes <= 0:
            return self.total_goals > 2
        return None

    @property
    def under_25_settled(self) -> bool | None:
        o = self.over_25_settled
        if o is True:
            return False
        if self.remaining_minutes <= 0:
            return self.total_goals <= 2
        return None


class LiveMarketStatus(str, Enum):
    AVAILABLE = "available"
    SETTLED_WON = "settled_won"
    SETTLED_LOST = "settled_lost"
    UNAVAILABLE = "unavailable"


@dataclass
class LiveMarketNote:
    market_type: str
    status: LiveMarketStatus
    reason: str = ""


@dataclass
class LiveAnalysisMeta:
    state: LiveMatchState
    home_lambda_remaining: float
    away_lambda_remaining: float
    home_lambda_full: float
    away_lambda_full: float
    market_notes: list[LiveMarketNote] = field(default_factory=list)