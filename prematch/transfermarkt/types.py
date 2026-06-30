"""Tipos normalizados — dados Transfermarkt em cache."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlayerAbsence:
    name: str
    status: str  # injured | suspended
    days_out: int = 0
    games_missed: int = 0
    market_value_m: float = 0.0
    replacement_value_m: float = 0.0
    injury_history: str = "unknown"  # crystal | recurrent | unknown
    expected_return: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "days_out": self.days_out,
            "games_missed": self.games_missed,
            "market_value_m": self.market_value_m,
            "replacement_value_m": self.replacement_value_m,
            "injury_history": self.injury_history,
            "expected_return": self.expected_return,
        }


@dataclass
class SquadSnapshot:
    team: str
    market_value_m: float
    players: list[dict] = field(default_factory=list)
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "team": self.team,
            "market_value_m": self.market_value_m,
            "players": self.players,
            "updated_at": self.updated_at,
        }


@dataclass
class ManagerProfile:
    team: str
    manager: str
    formation: str = "4-2-3-1"
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "team": self.team,
            "manager": self.manager,
            "formation": self.formation,
            "updated_at": self.updated_at,
        }


@dataclass
class ManagerH2H:
    manager_a: str
    manager_b: str
    wins_a: int = 0
    draws: int = 0
    losses_a: int = 0
    avg_goals: float = 2.5
    updated_at: str = ""

    @property
    def games(self) -> int:
        return self.wins_a + self.draws + self.losses_a

    def to_dict(self) -> dict:
        return {
            "manager_a": self.manager_a,
            "manager_b": self.manager_b,
            "wins_a": self.wins_a,
            "draws": self.draws,
            "losses_a": self.losses_a,
            "avg_goals": self.avg_goals,
            "games": self.games,
            "updated_at": self.updated_at,
        }


@dataclass
class RefereeProfile:
    name: str
    yellow_avg: float = 4.0
    red_avg: float = 0.12
    penalty_avg: float = 0.25
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "yellow_avg": self.yellow_avg,
            "red_avg": self.red_avg,
            "penalty_avg": self.penalty_avg,
            "updated_at": self.updated_at,
        }


@dataclass
class ValueGapInsight:
    home_value_m: float
    away_value_m: float
    ratio: float
    expected_home_prob: float
    implied_home_prob: float
    gap_pct: float
    signal: str
    label: str

    def to_dict(self) -> dict:
        return {
            "home_value_m": self.home_value_m,
            "away_value_m": self.away_value_m,
            "ratio": round(self.ratio, 2),
            "expected_home_prob_pct": round(self.expected_home_prob * 100, 1),
            "implied_home_prob_pct": round(self.implied_home_prob * 100, 1),
            "gap_pct": round(self.gap_pct, 1),
            "signal": self.signal,
            "label": self.label,
        }


@dataclass
class TacticalInsight:
    home_manager: str
    away_manager: str
    home_formation: str
    away_formation: str
    openness_score: float
    h2h_games: int
    h2h_avg_goals: float | None
    goals_tendency: str
    label: str

    def to_dict(self) -> dict:
        return {
            "home_manager": self.home_manager,
            "away_manager": self.away_manager,
            "home_formation": self.home_formation,
            "away_formation": self.away_formation,
            "openness_score": round(self.openness_score, 2),
            "h2h_games": self.h2h_games,
            "h2h_avg_goals": self.h2h_avg_goals,
            "goals_tendency": self.goals_tendency,
            "label": self.label,
        }


@dataclass
class RefereeInsight:
    referee: str
    yellow_avg: float
    red_avg: float
    penalty_avg: float
    cards_signal: str
    penalty_signal: str
    label: str

    def to_dict(self) -> dict:
        return {
            "referee": self.referee,
            "yellow_avg": self.yellow_avg,
            "red_avg": self.red_avg,
            "penalty_avg": self.penalty_avg,
            "cards_signal": self.cards_signal,
            "penalty_signal": self.penalty_signal,
            "label": self.label,
        }


@dataclass
class AbsenceInsight:
    team: str
    absences: list[PlayerAbsence]
    total_impact: float
    label: str

    def to_dict(self) -> dict:
        return {
            "team": self.team,
            "absences": [a.to_dict() for a in self.absences],
            "total_impact": round(self.total_impact, 3),
            "label": self.label,
        }


@dataclass
class PrematchInsights:
    home: str
    away: str
    data_available: bool
    value_gap: ValueGapInsight | None = None
    tactical: TacticalInsight | None = None
    referee: RefereeInsight | None = None
    home_absences: AbsenceInsight | None = None
    away_absences: AbsenceInsight | None = None
    alignment: str = "neutral"
    signals: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "home": self.home,
            "away": self.away,
            "data_available": self.data_available,
            "value_gap": self.value_gap.to_dict() if self.value_gap else None,
            "tactical": self.tactical.to_dict() if self.tactical else None,
            "referee": self.referee.to_dict() if self.referee else None,
            "home_absences": self.home_absences.to_dict() if self.home_absences else None,
            "away_absences": self.away_absences.to_dict() if self.away_absences else None,
            "alignment": self.alignment,
            "signals": self.signals,
            "summary": self.summary,
        }