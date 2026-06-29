"""Tipos partilhados de odds (sem dependências circulares)."""

from dataclasses import dataclass, field

from markets.extended import ExtendedOdds
from models.team_stats import MatchOdds


@dataclass
class OddsFetchResult:
    match_odds: MatchOdds
    extended: ExtendedOdds | None = None
    event_id: str = ""
    sport_key: str = ""
    home_team: str = ""
    away_team: str = ""
    bookmaker: str = ""
    bookmaker_title: str = ""
    fetched_at: str = ""
    credits_remaining: int | None = None
    credits_used: int | None = None
    source: str = "the-odds-api"
    region: str = "eu"
    all_bookmakers: list[str] = field(default_factory=list)