"""Testes — auto-sync Transfermarkt do calendário."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from discovery.fixture_types import UpcomingFixture
from prematch.transfermarkt import api_client
from prematch.transfermarkt.auto_sync import (
    is_international_fixture,
    prefer_country_for_fixture,
    squad_needs_sync,
    sync_calendar_teams,
)


def test_is_international_fixture():
    assert is_international_fixture("World Cup", "Group A")
    assert is_international_fixture("International Friendly")
    assert not is_international_fixture("Primeira Liga", "Jornada 12")


def test_prefer_country_national_team():
    assert prefer_country_for_fixture(national=True, team="Norway") == "Norway"
    assert (
        prefer_country_for_fixture(national=True, team="Ivory Coast")
        == "Côte d'Ivoire"
    )


def test_prefer_country_league_hint():
    assert prefer_country_for_fixture("Primeira Liga") == "Portugal"
    assert prefer_country_for_fixture("Ligue 1") == "France"


def test_squad_needs_sync_missing_and_seed():
    squads = {
        "Benfica": {
            "team": "Benfica",
            "tm_club_id": "294",
            "source": "transfermarkt-api",
            "market_value_m": 372,
        },
        "Mystery FC": {"team": "Mystery FC", "market_value_m": 10, "players": []},
    }
    assert not squad_needs_sync("Benfica", squads)
    assert squad_needs_sync("Unknown Team", squads)
    assert squad_needs_sync("Mystery FC", squads)


def test_pick_national_team_from_search():
    payload = {
        "results": [
            {"id": "720", "name": "FC Porto", "country": "Portugal", "marketValue": 428_600_000},
            {"id": "3300", "name": "Norway", "country": "Norway", "marketValue": 350_000_000},
        ]
    }
    picked = api_client.pick_national_team_from_search(payload, query="Norway")
    assert picked["id"] == "3300"


def test_sync_calendar_teams_skips_when_disabled(monkeypatch):
    monkeypatch.setenv("TRANSFERMARKT_AUTO_SYNC", "0")
    fixtures = [
        UpcomingFixture(
            home="Ivory Coast",
            away="Norway",
            league="World Cup",
            kickoff="2026-07-01T18:00:00+00:00",
        )
    ]
    assert sync_calendar_teams(fixtures) is None