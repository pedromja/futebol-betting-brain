"""Perfis agregados — football-data.co.uk (fecho + estilo)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VenueSlice:
    matches: int = 0
    shots_avg: float = 0.0
    sot_avg: float = 0.0
    corners_avg: float = 0.0
    fouls_avg: float = 0.0
    goals_scored_avg: float = 0.0
    goals_conceded_avg: float = 0.0
    closing_win_odd_avg: float | None = None
    closing_ou_over_avg: float | None = None

    def to_dict(self) -> dict:
        return {
            "matches": self.matches,
            "shots_avg": round(self.shots_avg, 2),
            "sot_avg": round(self.sot_avg, 2),
            "corners_avg": round(self.corners_avg, 2),
            "fouls_avg": round(self.fouls_avg, 2),
            "goals_scored_avg": round(self.goals_scored_avg, 2),
            "goals_conceded_avg": round(self.goals_conceded_avg, 2),
            "closing_win_odd_avg": (
                round(self.closing_win_odd_avg, 2)
                if self.closing_win_odd_avg
                else None
            ),
            "closing_ou_over_avg": (
                round(self.closing_ou_over_avg, 2)
                if self.closing_ou_over_avg
                else None
            ),
        }


@dataclass
class TeamHistoricalProfile:
    team: str
    league: str
    season: str
    matches: int = 0
    home: VenueSlice = field(default_factory=VenueSlice)
    away: VenueSlice = field(default_factory=VenueSlice)
    goals_total_avg: float = 0.0
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "team": self.team,
            "league": self.league,
            "season": self.season,
            "matches": self.matches,
            "home": self.home.to_dict(),
            "away": self.away.to_dict(),
            "goals_total_avg": round(self.goals_total_avg, 2),
            "updated_at": self.updated_at,
        }

    @classmethod
    def _slice_from_dict(cls, data: dict) -> VenueSlice:
        def f(key: str, default: float = 0.0) -> float:
            val = data.get(key)
            return float(val) if val is not None else default

        odd = data.get("closing_win_odd_avg")
        ou = data.get("closing_ou_over_avg")
        return VenueSlice(
            matches=int(data.get("matches") or 0),
            shots_avg=f("shots_avg"),
            sot_avg=f("sot_avg"),
            corners_avg=f("corners_avg"),
            fouls_avg=f("fouls_avg"),
            goals_scored_avg=f("goals_scored_avg"),
            goals_conceded_avg=f("goals_conceded_avg"),
            closing_win_odd_avg=float(odd) if odd else None,
            closing_ou_over_avg=float(ou) if ou else None,
        )

    @classmethod
    def from_dict(cls, data: dict) -> TeamHistoricalProfile:
        home = cls._slice_from_dict(data.get("home") or {})
        away = cls._slice_from_dict(data.get("away") or {})
        return cls(
            team=str(data.get("team") or ""),
            league=str(data.get("league") or ""),
            season=str(data.get("season") or ""),
            matches=int(data.get("matches") or 0),
            home=home,
            away=away,
            goals_total_avg=float(data.get("goals_total_avg") or 0),
            updated_at=str(data.get("updated_at") or ""),
        )