"""Testes — cliente transfermarkt-api."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prematch.transfermarkt import api_client


def test_pick_club_prefers_portugal_senior():
    payload = {
        "results": [
            {"id": "1", "name": "SL Benfica B", "country": "Portugal", "marketValue": 50_000_000},
            {"id": "294", "name": "SL Benfica", "country": "Portugal", "marketValue": 372_000_000},
            {"id": "9", "name": "Benfica Macau", "country": "Macao", "marketValue": 20_000},
        ]
    }
    picked = api_client.pick_club_from_search(payload, query="Benfica")
    assert picked["id"] == "294"


def test_pick_club_excludes_national_team_for_porto():
    payload = {
        "results": [
            {"id": "3300", "name": "Portugal", "country": "Portugal", "marketValue": 1_010_000_000},
            {"id": "720", "name": "FC Porto", "country": "Portugal", "marketValue": 428_600_000},
        ]
    }
    picked = api_client.pick_club_from_search(payload, query="Porto")
    assert picked["id"] == "720"


def test_pick_club_sl_benfica_not_treated_as_youth():
    payload = {
        "results": [
            {"id": "39885", "name": "Benfica de Macau", "country": "Macao", "marketValue": 20_000},
            {"id": "294", "name": "SL Benfica", "country": "Portugal", "marketValue": 372_000_000},
        ]
    }
    picked = api_client.pick_club_from_search(payload, query="Benfica", prefer_country="Portugal")
    assert picked["id"] == "294"


def test_parse_player_status():
    assert api_client.parse_player_status("Team captain") is None
    assert api_client.parse_player_status("Muscle injury") == "injured"
    assert api_client.parse_player_status("Suspension through sports court") == "suspended"


def test_euros_to_millions():
    assert api_client.euros_to_millions(372_000_000) == 372.0