"""Estatísticas ao vivo por fixture — normalizadas a partir da API-Football."""

from dataclasses import dataclass, field


@dataclass
class TeamLiveStats:
    team: str = ""
    possession_pct: int | None = None
    shots_total: int | None = None
    shots_on: int | None = None
    shots_off: int | None = None
    shots_blocked: int | None = None
    corners: int | None = None
    fouls: int | None = None
    offsides: int | None = None
    yellow_cards: int | None = None
    red_cards: int | None = None
    saves: int | None = None
    passes_total: int | None = None
    passes_accurate: int | None = None
    passes_pct: int | None = None
    xg: float | None = None
    xg_source: str = "none"  # api | estimated | none

    def to_dict(self) -> dict:
        return {
            "team": self.team,
            "possession_pct": self.possession_pct,
            "shots_total": self.shots_total,
            "shots_on": self.shots_on,
            "shots_off": self.shots_off,
            "shots_blocked": self.shots_blocked,
            "corners": self.corners,
            "fouls": self.fouls,
            "offsides": self.offsides,
            "yellow_cards": self.yellow_cards,
            "red_cards": self.red_cards,
            "saves": self.saves,
            "passes_total": self.passes_total,
            "passes_accurate": self.passes_accurate,
            "passes_pct": self.passes_pct,
            "xg": self.xg,
            "xg_source": self.xg_source,
        }


@dataclass
class MatchEvent:
    minute: int
    extra: int | None
    team: str
    player: str
    assist: str
    type: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "minute": self.minute,
            "extra": self.extra,
            "team": self.team,
            "player": self.player,
            "assist": self.assist,
            "type": self.type,
            "detail": self.detail,
        }


@dataclass
class MatchLiveStatsBundle:
    fixture_id: int
    home: TeamLiveStats
    away: TeamLiveStats
    events: list[MatchEvent] = field(default_factory=list)
    fetched_at: str = ""
    xg_source: str = "none"  # api | estimated | mixed | none

    def to_dict(self) -> dict:
        return {
            "fixture_id": self.fixture_id,
            "home_stats": self.home.to_dict(),
            "away_stats": self.away.to_dict(),
            "events": [e.to_dict() for e in self.events],
            "fetched_at": self.fetched_at,
            "xg_source": self.xg_source,
        }