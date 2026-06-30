"""Testes — resolução de resultados (ESPN Mundial, aliases, event id)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from history.result_fetcher import (
    ResultFetcher,
    _espn_date_keys,
    _espn_league_codes_for_resolve,
    _espn_teams_match,
    _names_match,
)


def _finished_comp(home: str, away: str, hg: int, ag: int) -> dict:
    return {
        "status": {"type": {"completed": True, "state": "post", "name": "STATUS_FULL_TIME"}},
        "competitors": [
            {"homeAway": "home", "team": {"displayName": home}, "score": str(hg)},
            {"homeAway": "away", "team": {"displayName": away}, "score": str(ag)},
        ],
    }


def test_names_match_ivory_coast_alias():
    assert _names_match("Ivory Coast", "Côte d'Ivoire")
    assert _names_match("Cote d Ivoire", "Ivory Coast")


def test_espn_teams_match_with_alias():
    comp = _finished_comp("Côte d'Ivoire", "Norway", 1, 2)
    assert _espn_teams_match("Ivory Coast", "Norway", comp)


def test_espn_league_codes_prioritize_world_cup():
    codes = _espn_league_codes_for_resolve(league="FIFA World Cup")
    assert codes[0] == "fifa.world"


def test_espn_league_codes_prioritize_stored_code():
    codes = _espn_league_codes_for_resolve(
        league="FIFA World Cup",
        espn_league_code="fifa.world",
    )
    assert codes[0] == "fifa.world"


def test_espn_date_keys_includes_previous_day_for_late_kickoff():
    keys = _espn_date_keys("2026-07-01T01:00:00Z")
    assert "20260630" in keys
    assert "20260701" in keys


class _FakeBrowser:
    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self.urls: list[str] = []

    def fetch_json(self, url: str, *, cache_ns: str = "", cache_ttl: int = 0):
        self.urls.append(url)
        for key, payload in self.responses.items():
            if key in url:
                return payload
        return None


def test_by_espn_event_id_resolves_from_summary():
    summary = {
        "header": {
            "id": "760490",
            "competitions": [
                _finished_comp("Côte d'Ivoire", "Norway", 1, 2),
            ],
        }
    }
    browser = _FakeBrowser({"summary?event=760490": summary})
    rf = ResultFetcher(browser=browser)
    final = rf.by_espn_event_id(
        "760490",
        league_code="fifa.world",
        league="FIFA World Cup",
    )
    assert final is not None
    assert final.score_label == "1-2"
    assert final.home_goals == 1
    assert final.away_goals == 2


def test_resolve_prefers_espn_event_id_over_name_scan():
    summary = {
        "header": {
            "id": "999001",
            "competitions": [
                _finished_comp("Netherlands", "Morocco", 2, 1),
            ],
        }
    }
    browser = _FakeBrowser({"summary?event=999001": summary})
    rf = ResultFetcher(browser=browser)
    final = rf.resolve(
        "Netherlands",
        "Morocco",
        "2026-06-30T19:00:00Z",
        espn_event_id="999001",
        espn_league_code="fifa.world",
        league="FIFA World Cup",
    )
    assert final is not None
    assert final.score_label == "2-1"
    assert any("summary?event=999001" in u for u in browser.urls)


def test_by_espn_searches_adjacent_date_for_world_cup():
    scoreboard = {
        "events": [
            {
                "competitions": [
                    _finished_comp("Mexico", "Ecuador", 0, 0),
                ]
            }
        ]
    }
    browser = _FakeBrowser({"scoreboard?dates=20260630": scoreboard})
    rf = ResultFetcher(browser=browser)
    final = rf.by_espn(
        "Mexico",
        "Ecuador",
        "2026-07-01T01:00:00Z",
        league="FIFA World Cup",
    )
    assert final is not None
    assert final.score_label == "0-0"
    assert any("dates=20260630" in u for u in browser.urls)