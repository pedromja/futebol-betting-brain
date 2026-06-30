"""Tipos — painel de auditores e Motivation Gate."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AuditorVote:
    """Voto de um auditor independente."""

    auditor_id: str
    category: str  # strength | table | availability | form | historical_market
    side: str  # home | away | neutral
    label: str
    supports_market: bool = True
    market_side: str | None = None  # over | under | draw — alinha mercados não-1X2

    def to_dict(self) -> dict:
        return {
            "auditor_id": self.auditor_id,
            "category": self.category,
            "side": self.side,
            "label": self.label,
            "supports_market": self.supports_market,
            "market_side": self.market_side,
        }


@dataclass
class TableStakesInsight:
    team: str
    position: int
    total_teams: int
    points: int
    motivation: str  # title | europe | relegation | midtable
    label: str

    def to_dict(self) -> dict:
        return {
            "team": self.team,
            "position": self.position,
            "total_teams": self.total_teams,
            "points": self.points,
            "motivation": self.motivation,
            "label": self.label,
        }


@dataclass
class ClubEloInsight:
    team: str
    elo: float
    rank: int | None = None

    def to_dict(self) -> dict:
        return {
            "team": self.team,
            "elo": round(self.elo, 1),
            "rank": self.rank,
        }


@dataclass
class MotivationReport:
    home: str
    away: str
    bet_market: str
    bet_side: str  # home | away | draw | over | under | other
    bet_ev: float
    votes: list[AuditorVote] = field(default_factory=list)
    motivation_score: int = 0
    independent_categories: int = 0
    labels: list[str] = field(default_factory=list)
    stake_multiplier: float = 1.0
    veto: bool = False
    should_bet: bool = True
    alignment: str = "neutral"  # strong | neutral | weak | veto
    summary: str = ""
    clubelo: dict | None = None
    table_stakes: dict | None = None
    historical: dict | None = None

    def to_dict(self) -> dict:
        return {
            "home": self.home,
            "away": self.away,
            "bet_market": self.bet_market,
            "bet_side": self.bet_side,
            "bet_ev_pct": round(self.bet_ev * 100, 1),
            "votes": [v.to_dict() for v in self.votes],
            "motivation_score": self.motivation_score,
            "independent_categories": self.independent_categories,
            "labels": self.labels,
            "stake_multiplier": self.stake_multiplier,
            "veto": self.veto,
            "should_bet": self.should_bet,
            "alignment": self.alignment,
            "summary": self.summary,
            "clubelo": self.clubelo,
            "table_stakes": self.table_stakes,
            "historical": self.historical,
        }