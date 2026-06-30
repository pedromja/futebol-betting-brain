"""Testes — verificação de estádio via web multi-fonte."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.venue_verifier import (
    VenueWebVerifier,
    extract_venue_from_text,
    is_neutral_tournament,
    venues_differ,
)
from discovery.web_browser import WebSearchHit
from models.team_stats import MatchInput, MatchOdds, TeamForm


def _match(home: str = "Brazil", away: str = "Japan", league: str = "FIFA World Cup") -> MatchInput:
    return MatchInput(
        home=TeamForm(name=home, goals_scored_avg=1.5, goals_conceded_avg=1.0),
        away=TeamForm(name=away, goals_scored_avg=1.2, goals_conceded_avg=1.0),
        odds=MatchOdds(2.0, 3.2, 3.5, 1.9, 1.9, 1.8, 1.9, 1.3, 1.6, 1.25),
        league=league,
        date="2026-06-28",
    )


def test_is_neutral_tournament():
    assert is_neutral_tournament("FIFA World Cup 2026")
    assert not is_neutral_tournament("Primeira Liga")


def test_extract_venue_from_text():
    parsed = extract_venue_from_text(
        "Brazil vs Japan at NRG Stadium, Houston, TX — World Cup Round of 16"
    )
    assert parsed is not None
    assert "NRG" in parsed.stadium
    assert parsed.country == "US"


def test_venues_differ_detects_neutral_site():
    assert venues_differ("Maracanã", "Rio de Janeiro", "NRG Stadium", "Houston")
    assert not venues_differ("Maracanã", "Rio", "Maracanã", "Rio de Janeiro")


class _FakeBrowser:
    def search(self, query: str, max_results: int = 8):
        return [
            WebSearchHit(
                title="Brazil vs Japan at NRG Stadium, Houston",
                url="https://espn.com/1",
                snippet="Match at NRG Stadium in Houston, United States",
            )
        ]

    def search_duckduckgo(self, query: str, max_results: int = 8):
        return [
            WebSearchHit(
                title="Brazil Japan NRG Stadium Houston World Cup",
                url="https://fifa.com/2",
                snippet="Venue: NRG Stadium, Houston TX",
            )
        ]


def test_verify_corrects_when_two_engines_agree():
    verifier = VenueWebVerifier(browser=_FakeBrowser())
    result = verifier.verify(
        _match(),
        usual_stadium="Maracanã",
        usual_city="Rio de Janeiro",
        usual_country="BR",
    )
    assert result is not None
    assert "NRG" in result.stadium
    assert result.corrected_from_usual is True
    assert result.is_home_venue is False
    assert len(result.verification_sources) >= 2


def test_verify_rejects_same_as_usual_home():
    verifier = VenueWebVerifier(browser=_FakeBrowser())
    result = verifier.verify(
        _match(league="Primeira Liga"),
        usual_stadium="NRG Stadium",
        usual_city="Houston",
        usual_country="US",
        require_different_from_usual=True,
    )
    assert result is None