"""Fonte unificada de odds — fixture/ESPN → The-Odds-API → X."""

from __future__ import annotations

from dataclasses import replace

from discovery.fixture_scanner import UpcomingFixture
from discovery.quota_guard import PROVIDER_THE_ODDS, is_exhausted
from models.team_stats import MatchInput, MatchOdds
from scanner.odds_fetcher import OddsFetcher

from .the_odds_api import TheOddsApiClient
from .types import OddsFetchResult


def _odds_from_hint(hint: dict, fixture: UpcomingFixture, source: str) -> OddsFetchResult:
    return OddsFetchResult(
        match_odds=MatchOdds(
            home_win=float(hint.get("home_win", 0)),
            draw=float(hint.get("draw", 0)),
            away_win=float(hint.get("away_win", 0)),
            over_25=float(hint.get("over_25", 1.9)),
            under_25=float(hint.get("under_25", 1.9)),
            btts_yes=float(hint.get("btts_yes", 1.8)),
            btts_no=float(hint.get("btts_no", 1.9)),
            double_chance_1x=float(hint.get("double_chance_1x", 0)),
            double_chance_x2=float(hint.get("double_chance_x2", 0)),
            double_chance_12=float(hint.get("double_chance_12", 0)),
        ),
        home_team=fixture.home,
        away_team=fixture.away,
        bookmaker=source,
        bookmaker_title=source.replace("-", " ").title(),
        source=source,
    )


class OddsProvider:
    def __init__(
        self,
        the_odds_api_key: str | None = None,
        xai_api_key: str | None = None,
        region: str = "eu",
    ):
        self.the_odds = TheOddsApiClient(api_key=the_odds_api_key, region=region)
        self.x_fetcher = OddsFetcher(xai_api_key=xai_api_key)

    def fetch_for_fixture(self, fixture: UpcomingFixture) -> OddsFetchResult | None:
        if fixture.odds_hint:
            src = fixture.source or "fixture-odds"
            if "espn" in src:
                src = "espn"
            return _odds_from_hint(fixture.odds_hint, fixture, src)

        if not is_exhausted(PROVIDER_THE_ODDS):
            result = self.the_odds.fetch_for_teams(fixture.home, fixture.away)
            if result:
                return result

        x_data = self.x_fetcher.fetch(fixture)
        if not x_data:
            return None

        return OddsFetchResult(
            match_odds=MatchOdds(
                home_win=x_data["home_win"],
                draw=x_data["draw"],
                away_win=x_data["away_win"],
                over_25=x_data["over_25"],
                under_25=x_data["under_25"],
                btts_yes=x_data["btts_yes"],
                btts_no=x_data["btts_no"],
            ),
            home_team=fixture.home,
            away_team=fixture.away,
            bookmaker="x_search",
            bookmaker_title="X Search",
            source="x_search",
        )

    def fetch_for_match(
        self,
        match: MatchInput,
        sport_key: str | None = None,
    ) -> OddsFetchResult | None:
        return self.the_odds.fetch_for_teams(
            match.home.name,
            match.away.name,
            sport_key=sport_key,
        )

    @staticmethod
    def apply_to_match(match: MatchInput, fetched: OddsFetchResult) -> MatchInput:
        return replace(match, odds=fetched.match_odds)