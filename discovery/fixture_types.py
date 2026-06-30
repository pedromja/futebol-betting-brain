from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class UpcomingFixture:
    home: str
    away: str
    league: str
    kickoff: str
    country: str = "PT"
    source: str = "unknown"
    stage: str = ""
    espn_event_id: str = ""
    espn_league_code: str = ""
    odds_hint: dict = field(default_factory=dict)
    stats_hint: dict = field(default_factory=dict)

    @property
    def kickoff_dt(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.kickoff.replace("Z", "+00:00"))
        except ValueError:
            return None

    @property
    def label(self) -> str:
        return f"{self.home} vs {self.away}"