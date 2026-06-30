"""
Descobre jogos nas próximas N horas via web (APIs públicas + pesquisa Bing).
Não depende de XAI nem de créditos X.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from discovery.espn_odds import extract_match_odds
from discovery.fixture_types import UpcomingFixture
from discovery.espn_stage import stage_from_scoreboard
from discovery.web_browser import WebBrowser, WebSearchHit

ESPN_PRIORITY: dict[str, str] = {
    "fifa.world": "FIFA World Cup",
    "por.1": "Primeira Liga",
    "eng.1": "Premier League",
    "esp.1": "La Liga",
    "ita.1": "Serie A",
    "ger.1": "Bundesliga",
    "fra.1": "Ligue 1",
}

ESPN_EXTRA: dict[str, str] = {
    "ned.1": "Eredivisie",
    "usa.1": "MLS",
    "bra.1": "Brasileirão",
    "uefa.champions": "UEFA Champions League",
    "uefa.europa": "UEFA Europa League",
}

BING_FIXTURE_QUERY = "soccer football fixtures today kick off schedule"

TRUSTED_DOMAINS = (
    "espn.com",
    "soccerway.com",
    "flashscore.",
    "livescore.com",
    "whoscored.com",
    "goal.com",
    "zerozero.pt",
    "ojogo.pt",
    "abola.pt",
    "record.pt",
)


class WebFixtureScanner:
    def __init__(self, browser: WebBrowser | None = None):
        self.browser = browser or WebBrowser()

    def _within_window(self, kickoff: datetime, hours_ahead: int) -> bool:
        now = datetime.now(timezone.utc)
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        return now <= kickoff <= now + timedelta(hours=hours_ahead)

    def _espn_url(self, league_code: str, date_key: str) -> str:
        return (
            "https://site.api.espn.com/apis/site/v2/sports/soccer/"
            f"{league_code}/scoreboard?dates={date_key}"
        )

    def _parse_espn_response(
        self,
        data: dict | None,
        league_name: str,
        hours_ahead: int,
        *,
        league_code: str = "",
    ) -> list[UpcomingFixture]:
        if not isinstance(data, dict):
            return []
        stage = stage_from_scoreboard(data)
        out: list[UpcomingFixture] = []
        for event in data.get("events", []):
            fixture = self._espn_event_to_fixture(
                event,
                league_name,
                hours_ahead,
                stage=stage,
                league_code=league_code,
            )
            if fixture:
                out.append(fixture)
        return out

    def _fetch_espn_league(
        self, league_code: str, league_name: str, date_key: str, hours_ahead: int
    ) -> list[UpcomingFixture]:
        url = self._espn_url(league_code, date_key)
        data = self.browser.fetch_json(url, cache_ns="espn_scoreboard", cache_ttl=600)
        return self._parse_espn_response(
            data, league_name, hours_ahead, league_code=league_code
        )

    def _scan_espn(self, hours_ahead: int, leagues: dict[str, str]) -> list[UpcomingFixture]:
        now = datetime.now(timezone.utc)
        dates = [now.strftime("%Y%m%d")]
        if hours_ahead > 8:
            dates.append((now + timedelta(days=1)).strftime("%Y%m%d"))

        tasks: list[tuple[str, str, str]] = []
        for code, name in leagues.items():
            for date_key in dates:
                tasks.append((code, name, date_key))

        fixtures: list[UpcomingFixture] = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                pool.submit(self._fetch_espn_league, c, n, d, hours_ahead): (c, d)
                for c, n, d in tasks
            }
            for fut in as_completed(futures):
                try:
                    fixtures.extend(fut.result())
                except Exception:
                    pass
        return fixtures

    def _espn_event_to_fixture(
        self,
        event: dict,
        league_name: str,
        hours_ahead: int,
        stage: str = "",
        *,
        league_code: str = "",
    ) -> UpcomingFixture | None:
        date_str = event.get("date", "")
        if not date_str:
            return None

        try:
            kickoff = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None

        if not self._within_window(kickoff, hours_ahead):
            return None

        comp = event.get("competitions", [{}])[0]
        status = comp.get("status", {}).get("type", {})
        state = status.get("state", "")
        name = status.get("name", "")

        if status.get("completed") or state == "post" or name == "STATUS_FULL_TIME":
            return None

        competitors = comp.get("competitors", [])
        home = away = ""
        for c in competitors:
            side = c.get("homeAway", "")
            team = c.get("team", {}).get("displayName", "")
            if side == "home":
                home = team
            elif side == "away":
                away = team

        if not home or not away:
            title = event.get("name", "")
            if " at " in title:
                away, home = title.split(" at ", 1)
            elif " vs " in title.lower():
                parts = title.lower().split(" vs ", 1)
                if len(parts) == 2:
                    home, away = parts[0], parts[1]

        if not home or not away:
            return None

        odds_hint = extract_match_odds(comp) or {}

        return UpcomingFixture(
            home=home.strip(),
            away=away.strip(),
            league=league_name,
            kickoff=kickoff.isoformat().replace("+00:00", "Z"),
            country="EU",
            source="espn_web",
            stage=stage,
            espn_event_id=str(event.get("id") or ""),
            espn_league_code=league_code,
            odds_hint=odds_hint,
        )

    def _scan_thesportsdb(self, hours_ahead: int) -> list[UpcomingFixture]:
        fixtures: list[UpcomingFixture] = []
        now = datetime.now(timezone.utc)

        for offset in (0, 1):
            day = (now + timedelta(days=offset)).strftime("%Y-%m-%d")
            url = (
                "https://www.thesportsdb.com/api/v1/json/3/"
                f"eventsday.php?d={day}&s=Soccer"
            )
            data = self.browser.fetch_json(
                url, cache_ns="thesportsdb_events", cache_ttl=600
            )
            if not isinstance(data, dict):
                continue

            for event in data.get("events") or []:
                if not event:
                    continue
                date_ev = event.get("dateEvent", "")
                time_ev = (event.get("strTime") or "12:00:00")[:8]
                try:
                    kickoff = datetime.strptime(
                        f"{date_ev} {time_ev}", "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue

                if not self._within_window(kickoff, hours_ahead):
                    continue

                home = event.get("strHomeTeam", "").strip()
                away = event.get("strAwayTeam", "").strip()
                if not home or not away:
                    continue

                fixtures.append(
                    UpcomingFixture(
                        home=home,
                        away=away,
                        league=event.get("strLeague", "Soccer"),
                        kickoff=kickoff.isoformat().replace("+00:00", "Z"),
                        country="EU",
                        source="thesportsdb_web",
                    )
                )

        return fixtures

    def _scan_web_search(self, hours_ahead: int) -> list[UpcomingFixture]:
        """Fallback leve — só snippets Bing, sem abrir páginas."""
        hits = self.browser.search(BING_FIXTURE_QUERY, max_results=4)
        return self._fixtures_from_search_hits(hits, hours_ahead)

    def _is_trusted_fixture_url(self, url: str) -> bool:
        lower = url.lower()
        return any(domain in lower for domain in TRUSTED_DOMAINS)

    def _fixtures_from_search_hits(
        self, hits: list[WebSearchHit], hours_ahead: int
    ) -> list[UpcomingFixture]:
        fixtures: list[UpcomingFixture] = []
        for hit in hits:
            text = f"{hit.title} {hit.snippet}"
            fixtures.extend(
                self._fixtures_from_free_text(text, "bing_search", hours_ahead)
            )
        return fixtures

    def _fixtures_from_free_text(
        self, text: str, source: str, hours_ahead: int
    ) -> list[UpcomingFixture]:
        fixtures: list[UpcomingFixture] = []
        pairs = self.browser.extract_vs_pairs(text)
        if not pairs:
            return fixtures

        now = datetime.now(timezone.utc)
        kickoff = now + timedelta(hours=min(3, hours_ahead))

        for home, away in pairs[:5]:
            home = self._clean_team(home)
            away = self._clean_team(away)
            if not home or not away:
                continue
            fixtures.append(
                UpcomingFixture(
                    home=home,
                    away=away,
                    league="Web",
                    kickoff=kickoff.isoformat().replace("+00:00", "Z"),
                    country="EU",
                    source=source,
                )
            )
        return fixtures

    @staticmethod
    def _clean_team(name: str) -> str:
        name = name.strip(" .,-")
        junk = ("fixture", "schedule", "today", "tomorrow", "football", "soccer")
        if name.lower() in junk or len(name) < 3:
            return ""
        return name[:50]

    def scan(self, hours_ahead: int = 12) -> list[UpcomingFixture]:
        collected = self._scan_espn(hours_ahead, ESPN_PRIORITY)
        if not collected:
            collected = self._scan_espn(hours_ahead, ESPN_EXTRA)
        if not collected:
            collected.extend(self._scan_thesportsdb(hours_ahead))
        if not collected:
            collected.extend(self._scan_web_search(hours_ahead))
        return self._dedupe(collected)

    @staticmethod
    def _dedupe(fixtures: list[UpcomingFixture]) -> list[UpcomingFixture]:
        seen: set[str] = set()
        unique: list[UpcomingFixture] = []
        for fx in fixtures:
            key = f"{fx.home.lower()}|{fx.away.lower()}"
            if key not in seen:
                seen.add(key)
                unique.append(fx)
        unique.sort(key=lambda f: f.kickoff)
        return unique