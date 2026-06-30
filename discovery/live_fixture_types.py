"""Jogo em direto — resultado e minuto vindos da API."""

from dataclasses import dataclass, field

from discovery.fixture_types import UpcomingFixture
from live.types import LiveMatchState, MatchPeriod


@dataclass
class LiveFixture:
    home: str
    away: str
    league: str
    home_score: int
    away_score: int
    minute: int
    status_short: str
    stage: str = ""
    kickoff: str = ""
    injury_time: int = 0
    ht_home_score: int | None = None
    ht_away_score: int | None = None
    fixture_id: int | None = None
    source: str = "api-football"
    odds_hint: dict = field(default_factory=dict)
    odds_source: str = ""
    espn_event_id: str = ""
    espn_league_code: str = ""

    @property
    def label(self) -> str:
        return f"{self.home} vs {self.away}"

    @property
    def score_label(self) -> str:
        return f"{self.home_score}-{self.away_score}"

    def to_live_state(self) -> LiveMatchState:
        short = self.status_short.upper()
        period_map = {
            "1H": MatchPeriod.FIRST_HALF,
            "HT": MatchPeriod.FIRST_HALF,
            "2H": MatchPeriod.SECOND_HALF,
            "BT": MatchPeriod.SECOND_HALF,
            "ET": MatchPeriod.EXTRA_TIME,
            "P": MatchPeriod.PENALTIES,
            "LIVE": MatchPeriod.SECOND_HALF,
        }
        period = period_map.get(short, MatchPeriod.SECOND_HALF)
        minute = self.minute
        if short == "HT" and minute < 45:
            minute = 45
        return LiveMatchState(
            home_score=self.home_score,
            away_score=self.away_score,
            minute=minute,
            injury_time=self.injury_time,
            period=period,
        )

    def to_upcoming(self) -> UpcomingFixture:
        return UpcomingFixture(
            home=self.home,
            away=self.away,
            league=self.league,
            kickoff=self.kickoff,
            source=self.source,
            stage=self.stage,
            odds_hint=self.odds_hint,
            stats_hint={"api_football_fixture_id": self.fixture_id},
        )