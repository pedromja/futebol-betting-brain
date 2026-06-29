"""Odds in-play — API-Football live + fallback ESPN (grátis)."""

from discovery.api_football_client import ApiFootballClient
from discovery.espn_odds import extract_match_odds
from discovery.live_fixture_types import LiveFixture
from discovery.web_browser import WebBrowser
from discovery.web_fixture_scanner import ESPN_EXTRA, ESPN_PRIORITY

_LIVE_ODDS_TTL = 30
_SCOREBOARD_TTL = 45

_LEAGUE_ESPN: dict[str, str] = {
    "world cup": "fifa.world",
    "fifa": "fifa.world",
    "premier league": "eng.1",
    "la liga": "esp.1",
    "laliga": "esp.1",
    "serie a": "ita.1",
    "bundesliga": "ger.1",
    "ligue 1": "fra.1",
    "primeira liga": "por.1",
    "liga portugal": "por.1",
    "champions": "uefa.champions",
    "europa league": "uefa.europa",
}


class LiveOddsFetcher:
    def __init__(
        self,
        api_football: ApiFootballClient | None = None,
        browser: WebBrowser | None = None,
    ):
        self.api_football = api_football or ApiFootballClient()
        self.browser = browser or WebBrowser()

    def _espn_codes_for_league(self, league: str) -> list[str]:
        key = league.lower()
        codes: list[str] = []
        for pattern, code in _LEAGUE_ESPN.items():
            if pattern in key and code not in codes:
                codes.append(code)
        if not codes:
            codes = ["fifa.world", "eng.1", "esp.1", "ita.1"]
        return codes

    @staticmethod
    def _normalize_name(name: str) -> str:
        return "".join(c for c in name.lower() if c.isalnum() or c.isspace()).strip()

    def _teams_match(self, home: str, away: str, event: dict) -> bool:
        comp = event.get("competitions", [{}])[0]
        eh = ea = ""
        for c in comp.get("competitors", []):
            team = c.get("team", {}).get("displayName", "")
            if c.get("homeAway") == "home":
                eh = team
            elif c.get("homeAway") == "away":
                ea = team
        if not eh or not ea:
            return False
        nh, na, eh_n, ea_n = map(
            self._normalize_name, (home, away, eh, ea)
        )
        return (
            (nh in eh_n or eh_n in nh)
            and (na in ea_n or ea_n in na)
        ) or (
            (nh in ea_n or ea_n in nh)
            and (na in eh_n or eh_n in na)
        )

    def _espn_live_odds(self, fx: LiveFixture) -> dict | None:
        for code in self._espn_codes_for_league(fx.league):
            url = (
                "https://site.api.espn.com/apis/site/v2/sports/soccer/"
                f"{code}/scoreboard"
            )
            data = self.browser.fetch_json(
                url, cache_ns="espn_live_scoreboard", cache_ttl=_SCOREBOARD_TTL
            )
            if not isinstance(data, dict):
                continue
            for event in data.get("events", []):
                comp = event.get("competitions", [{}])[0]
                state = (comp.get("status", {}).get("type", {}) or {}).get(
                    "state", ""
                )
                if state != "in":
                    continue
                if not self._teams_match(fx.home, fx.away, event):
                    continue
                odds = extract_match_odds(comp)
                if odds:
                    return odds
        return None

    def enrich(
        self,
        fixtures: list[LiveFixture],
        *,
        prefer_live: bool = True,
    ) -> None:
        for fx in fixtures:
            if fx.odds_hint and fx.odds_source:
                continue
            if not fx.fixture_id and not prefer_live:
                continue

            if prefer_live and fx.fixture_id:
                live = self.api_football.fetch_live_odds(int(fx.fixture_id))
                if live:
                    fx.odds_hint = live
                    fx.odds_source = "api-football-live"
                    continue

            if prefer_live:
                espn = self._espn_live_odds(fx)
                if espn:
                    fx.odds_hint = espn
                    fx.odds_source = "espn-live"
                    continue

            if fx.fixture_id:
                prematch = self.api_football.fetch_fixture_odds(int(fx.fixture_id))
                if prematch:
                    fx.odds_hint = prematch
                    fx.odds_source = "api-football-prematch"
                    continue

            if not prefer_live:
                continue

            espn = self._espn_live_odds(fx)
            if espn:
                fx.odds_hint = espn
                fx.odds_source = "espn-live"