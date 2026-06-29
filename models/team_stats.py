from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stakes.types import TeamStake


@dataclass
class TeamForm:
    name: str
    goals_scored_avg: float
    goals_conceded_avg: float
    games_played: int = 10
    scored_in_last_n: int = 7
    conceded_in_last_n: int = 6
    last_n: int = 10

    @property
    def attack_rating(self) -> float:
        return self.goals_scored_avg

    @property
    def defense_rating(self) -> float:
        return self.goals_conceded_avg

    @property
    def scoring_consistency(self) -> float:
        return self.scored_in_last_n / max(self.last_n, 1)

    @property
    def conceding_consistency(self) -> float:
        return self.conceded_in_last_n / max(self.last_n, 1)


@dataclass
class MatchOdds:
    home_win: float
    draw: float
    away_win: float
    over_25: float
    under_25: float
    btts_yes: float
    btts_no: float
    double_chance_1x: float = 0.0
    double_chance_x2: float = 0.0
    double_chance_12: float = 0.0


@dataclass
class MatchInput:
    home: TeamForm
    away: TeamForm
    odds: MatchOdds
    league: str = "Liga"
    date: str = ""
    home_advantage: float = 1.15
    league_avg_goals: float = 1.35
    venue_stadium: str = ""
    venue_city: str = ""
    venue_country: str = "PT"
    home_stake: "TeamStake | None" = None
    away_stake: "TeamStake | None" = None