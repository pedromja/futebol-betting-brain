"""
Descobre jogos de futebol 11 nas próximas N horas via web, APIs e (opcional) X.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from discovery.api_football_client import ApiFootballClient
from discovery.fixture_types import UpcomingFixture
from discovery.quota_guard import PROVIDER_API_FOOTBALL, is_exhausted
from discovery.web_fixture_scanner import WebFixtureScanner
from discovery.x_client import XSearchClient


FIXTURE_X_PROMPT = """Pesquisa no X e na web jogos de FUTEBOL 11 (soccer) que vão COMEÇAR \
nas próximas {hours} horas a partir de agora ({now}).

Inclui ligas: Primeira Liga, Liga Portugal, Premier League, La Liga, Serie A, \
Bundesliga, Ligue 1, Champions League, Europa League.

Para cada jogo confirma equipa CASA e equipa FORA, competição e hora de início.

Responde APENAS com JSON (array), sem markdown:
[
  {{
    "home": "equipa casa",
    "away": "equipa fora",
    "league": "nome da liga",
    "kickoff": "AAAA-MM-DDTHH:MM:SS",
    "country": "PT",
    "credibility": 0.0-1.0
  }}
]

Só inclui jogos com credibilidade >= 0.5. Se não houver jogos, responde: []"""


class FixtureScanner:
    def __init__(
        self,
        xai_api_key: str | None = None,
        football_data_key: str | None = None,
        api_football_key: str | None = None,
        hours_ahead: int = 12,
    ):
        self.x_client = XSearchClient(api_key=xai_api_key)
        self.web_scanner = WebFixtureScanner()
        self.api_football = ApiFootballClient(api_key=api_football_key)
        self.fd_key = football_data_key or os.getenv("FOOTBALL_DATA_API_KEY", "")
        self.hours_ahead = hours_ahead

    def _within_window(self, kickoff: datetime) -> bool:
        now = datetime.now(timezone.utc)
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        limit = now + timedelta(hours=self.hours_ahead)
        return now <= kickoff <= limit

    def _scan_x(self) -> list[UpcomingFixture]:
        if not self.x_client.is_live:
            return []

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        prompt = FIXTURE_X_PROMPT.format(hours=self.hours_ahead, now=now)
        text, _ = self.x_client.query(prompt, days_back=2)

        fixtures: list[UpcomingFixture] = []
        for entry in self.x_client.parse_json_array(text):
            if not isinstance(entry, dict):
                continue
            cred = float(entry.get("credibility", 0.5))
            if cred < 0.5:
                continue
            kickoff = entry.get("kickoff", "")
            dt = None
            try:
                dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
            except ValueError:
                pass
            if dt and not self._within_window(dt):
                continue
            fixtures.append(
                UpcomingFixture(
                    home=entry.get("home", "").strip(),
                    away=entry.get("away", "").strip(),
                    league=entry.get("league", "").strip(),
                    kickoff=kickoff,
                    country=entry.get("country", "PT"),
                    source="x_search",
                )
            )
        return fixtures

    def _scan_football_data(self) -> list[UpcomingFixture]:
        if not self.fd_key:
            return []

        today = datetime.now(timezone.utc).date()
        tomorrow = today + timedelta(days=1)
        params = urllib.parse.urlencode({
            "dateFrom": today.isoformat(),
            "dateTo": tomorrow.isoformat(),
            "status": "SCHEDULED",
        })
        url = f"https://api.football-data.org/v4/matches?{params}"
        req = urllib.request.Request(
            url,
            headers={"X-Auth-Token": self.fd_key},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return []

        fixtures: list[UpcomingFixture] = []
        for m in data.get("matches", []):
            utc_date = m.get("utcDate", "")
            try:
                dt = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
            except ValueError:
                continue
            if not self._within_window(dt):
                continue
            home = m.get("homeTeam", {}).get("name", "")
            away = m.get("awayTeam", {}).get("name", "")
            comp = m.get("competition", {}).get("name", "")
            fixtures.append(
                UpcomingFixture(
                    home=home,
                    away=away,
                    league=comp,
                    kickoff=utc_date,
                    country=m.get("area", {}).get("code", "EU"),
                    source="football-data.org",
                )
            )
        return fixtures

    def _load_sample(self) -> list[UpcomingFixture]:
        path = os.path.join(
            os.path.dirname(__file__), "..", "data", "sample_fixtures.json"
        )
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        now = datetime.now(timezone.utc)
        result: list[UpcomingFixture] = []
        for entry in data:
            kickoff = entry.get("kickoff", "")
            try:
                dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                dt = now + timedelta(hours=2)
            if dt < now:
                dt = now + timedelta(hours=entry.get("hours_from_now", 3))
                kickoff = dt.isoformat()
            if not self._within_window(dt):
                continue
            result.append(
                UpcomingFixture(
                    home=entry["home"],
                    away=entry["away"],
                    league=entry.get("league", ""),
                    kickoff=kickoff,
                    country=entry.get("country", "PT"),
                    source="sample",
                    odds_hint=entry.get("odds", {}),
                    stats_hint=entry.get("stats", {}),
                )
            )
        return result

    def _dedupe(self, fixtures: list[UpcomingFixture]) -> list[UpcomingFixture]:
        seen: set[str] = set()
        unique: list[UpcomingFixture] = []
        for f in fixtures:
            key = f"{f.home.lower()}|{f.away.lower()}"
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique

    def _scan_web(self) -> list[UpcomingFixture]:
        return self.web_scanner.scan(self.hours_ahead)

    def _scan_api_football(self) -> list[UpcomingFixture]:
        return self.api_football.scan_fixtures(self.hours_ahead)

    def scan(self, *, allow_sample: bool = True) -> list[UpcomingFixture]:
        collected: list[UpcomingFixture] = []
        collected.extend(self._scan_web())
        if not is_exhausted(PROVIDER_API_FOOTBALL):
            collected.extend(self._scan_api_football())
        collected.extend(self._scan_football_data())
        collected.extend(self._scan_x())

        collected = self._dedupe(collected)
        collected.sort(key=lambda f: f.kickoff)

        if not collected and allow_sample:
            collected = self._load_sample()

        return collected