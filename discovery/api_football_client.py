"""
Cliente API-Football (API-Sports v3).

Dashboard / tester: https://dashboard.api-football.com/soccer/tester
Documentação: https://www.api-football.com/documentation-v3

Plano gratuito: ~100 pedidos/dia — usar cache agressivo.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from discovery.fixture_types import UpcomingFixture
from discovery.live_fixture_types import LiveFixture
from discovery.quota_guard import (
    PROVIDER_API_FOOTBALL,
    is_exhausted,
    is_quota_error,
    mark_exhausted,
)
from discovery.rate_limiter import MinIntervalLimiter
from discovery.response_cache import get as cache_get
from discovery.response_cache import set as cache_set

BASE_URL = "https://v3.football.api-sports.io"
_LIMITER = MinIntervalLimiter(6.5)
_FIXTURE_TTL = 600
_LIVE_TTL = 45
_LIVE_ODDS_TTL = 30
_ODDS_TTL = 3600
_DEFAULT_TTL = 86400

_FINISHED = frozenset({"FT", "AET", "PEN", "CANC", "ABD", "AWD", "WO"})
_LIVE_ACTIVE = frozenset({"1H", "2H", "HT", "ET", "BT", "P", "LIVE", "INT"})


class ApiFootballClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = (
            api_key
            or os.getenv("API_FOOTBALL_KEY", "")
            or os.getenv("APISPORTS_KEY", "")
        )
        self.last_error: str | None = None
        self.last_live_source: str = "none"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def quota_exhausted(self) -> bool:
        return is_exhausted(PROVIDER_API_FOOTBALL)

    def _request(
        self,
        path: str,
        params: dict | None = None,
        *,
        cache_ns: str = "api_football",
        cache_ttl: int = _DEFAULT_TTL,
    ) -> dict | None:
        if not self.api_key:
            return None

        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{BASE_URL}{path}{query}"
        cached = cache_get(cache_ns, url, cache_ttl)
        if cached is not None:
            return cached

        if is_exhausted(PROVIDER_API_FOOTBALL):
            self.last_error = self.last_error or (
                "requests: quota diária esgotada — fallback ESPN/football-data"
            )
            return None

        _LIMITER.wait()
        req = urllib.request.Request(
            url,
            headers={"x-apisports-key": self.api_key},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return None

        errors = data.get("errors") or {}
        if errors:
            self.last_error = "; ".join(
                f"{k}: {v}" for k, v in errors.items() if v
            ) or "api-football error"
            if is_quota_error(self.last_error):
                mark_exhausted(PROVIDER_API_FOOTBALL, self.last_error)
            return None

        self.last_error = None

        if data:
            cache_set(cache_ns, url, data)
        return data

    def ping(self) -> bool:
        data = self._request("/status", cache_ttl=300)
        return data is not None and not data.get("errors")

    def quota_hint(self) -> str | None:
        """Pedido mínimo para ler cabeçalhos de quota (não cacheado)."""
        if not self.api_key:
            return None
        _LIMITER.wait()
        req = urllib.request.Request(
            f"{BASE_URL}/status",
            headers={"x-apisports-key": self.api_key},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                remaining = resp.headers.get("x-ratelimit-requests-remaining")
                limit = resp.headers.get("x-ratelimit-requests-limit")
                if remaining and limit:
                    if remaining == "0":
                        mark_exhausted(PROVIDER_API_FOOTBALL, "daily limit 0")
                    return f"{remaining}/{limit} pedidos restantes hoje"
        except (urllib.error.URLError, TimeoutError):
            pass
        return None

    def _within_window(self, kickoff: datetime, hours_ahead: int) -> bool:
        now = datetime.now(timezone.utc)
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        return now <= kickoff <= now + timedelta(hours=hours_ahead)

    def _item_to_fixture(
        self, item: dict, hours_ahead: int
    ) -> UpcomingFixture | None:
        fix = item.get("fixture") or {}
        status = (fix.get("status") or {}).get("short", "")
        if status in _FINISHED:
            return None

        date_str = fix.get("date", "")
        if not date_str:
            return None
        try:
            kickoff = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None
        if not self._within_window(kickoff, hours_ahead):
            return None

        league = item.get("league") or {}
        teams = item.get("teams") or {}
        home = (teams.get("home") or {}).get("name", "").strip()
        away = (teams.get("away") or {}).get("name", "").strip()
        if not home or not away:
            return None

        goals = item.get("goals") or {}
        return UpcomingFixture(
            home=home,
            away=away,
            league=league.get("name", "Soccer"),
            kickoff=kickoff.isoformat().replace("+00:00", "Z"),
            country=(league.get("country") or "EU")[:2].upper() or "EU",
            source="api-football",
            stage=str(league.get("round") or ""),
            stats_hint={"api_football_fixture_id": fix.get("id")},
        )

    @staticmethod
    def _extract_odds_hint(bookmakers: list) -> dict | None:
        if not bookmakers:
            return None
        bets = (bookmakers[0] or {}).get("bets") or []
        out: dict[str, float] = {}
        for bet in bets:
            name = (bet.get("name") or "").lower()
            values = bet.get("values") or []
            if "match winner" in name or name == "home/draw/away":
                for v in values:
                    val = (v.get("value") or "").lower()
                    try:
                        odd = float(v.get("odd", 0))
                    except (TypeError, ValueError):
                        continue
                    if val == "home":
                        out["home_win"] = odd
                    elif val == "draw":
                        out["draw"] = odd
                    elif val == "away":
                        out["away_win"] = odd
            elif "over/under" in name or "goals over" in name:
                for v in values:
                    label = (v.get("value") or "").lower()
                    try:
                        odd = float(v.get("odd", 0))
                    except (TypeError, ValueError):
                        continue
                    if "over 2.5" in label:
                        out["over_25"] = odd
                    elif "under 2.5" in label:
                        out["under_25"] = odd
            elif "both teams" in name or "btts" in name:
                for v in values:
                    val = (v.get("value") or "").lower()
                    try:
                        odd = float(v.get("odd", 0))
                    except (TypeError, ValueError):
                        continue
                    if val in ("yes", "sim"):
                        out["btts_yes"] = odd
                    elif val in ("no", "não", "nao"):
                        out["btts_no"] = odd

        required = ("home_win", "draw", "away_win")
        if not all(k in out for k in required):
            return None
        out.setdefault("over_25", 1.90)
        out.setdefault("under_25", 1.90)
        out.setdefault("btts_yes", round((out["over_25"] + out["under_25"]) / 2.05, 2))
        out.setdefault("btts_no", round(max(1.55, 3.6 - out["btts_yes"]), 2))
        out.setdefault("double_chance_1x", 0.0)
        out.setdefault("double_chance_x2", 0.0)
        out.setdefault("double_chance_12", 0.0)
        return out

    @staticmethod
    def _active_odd(value: dict) -> float | None:
        if value.get("suspended"):
            return None
        try:
            odd = float(value.get("odd", 0))
        except (TypeError, ValueError):
            return None
        if odd <= 1.0:
            return None
        return odd

    def _extract_live_odds_hint(self, odds_markets: list) -> dict | None:
        """Parser para GET /odds/live (estrutura odds[] sem bookmakers)."""
        out: dict[str, float] = {}
        for market in odds_markets or []:
            name = (market.get("name") or "").lower()
            values = market.get("values") or []

            if name == "fulltime result":
                for v in values:
                    odd = self._active_odd(v)
                    if not odd:
                        continue
                    val = (v.get("value") or "").lower()
                    if val == "home":
                        out["home_win"] = odd
                    elif val == "draw":
                        out["draw"] = odd
                    elif val == "away":
                        out["away_win"] = odd

            elif name in ("over/under line", "match goals"):
                for v in values:
                    odd = self._active_odd(v)
                    if not odd:
                        continue
                    try:
                        line = float(v.get("handicap") or 0)
                    except (TypeError, ValueError):
                        continue
                    if abs(line - 2.5) > 0.01:
                        continue
                    side = (v.get("value") or "").lower()
                    if side == "over":
                        out["over_25"] = odd
                    elif side == "under":
                        out["under_25"] = odd

            elif "both teams" in name and "half" not in name and "2nd" not in name:
                for v in values:
                    odd = self._active_odd(v)
                    if not odd:
                        continue
                    val = (v.get("value") or "").lower()
                    if val in ("yes", "sim"):
                        out["btts_yes"] = odd
                    elif val in ("no", "não", "nao"):
                        out["btts_no"] = odd

            elif name == "double chance":
                for v in values:
                    odd = self._active_odd(v)
                    if not odd:
                        continue
                    val = (v.get("value") or "").lower()
                    if "home" in val and "draw" in val:
                        out["double_chance_1x"] = odd
                    elif "away" in val and "draw" in val:
                        out["double_chance_x2"] = odd
                    elif "home" in val and "away" in val:
                        out["double_chance_12"] = odd

        required = ("home_win", "draw", "away_win")
        if not all(k in out for k in required):
            return None
        out.setdefault("over_25", 1.90)
        out.setdefault("under_25", 1.90)
        out.setdefault("btts_yes", round((out["over_25"] + out["under_25"]) / 2.05, 2))
        out.setdefault("btts_no", round(max(1.55, 3.6 - out["btts_yes"]), 2))
        out.setdefault("double_chance_1x", 0.0)
        out.setdefault("double_chance_x2", 0.0)
        out.setdefault("double_chance_12", 0.0)
        return out

    def fetch_live_odds(self, fixture_id: int) -> dict | None:
        """Odds in-play por fixture (1 pedido, cache 30s)."""
        data = self._request(
            "/odds/live",
            {"fixture": fixture_id},
            cache_ttl=_LIVE_ODDS_TTL,
        )
        items = (data or {}).get("response") or []
        if not items:
            return None
        item = items[0]
        live_markets = item.get("odds")
        if live_markets:
            return self._extract_live_odds_hint(live_markets)
        return self._extract_odds_hint(item.get("bookmakers") or [])

    def fetch_fixture_odds(self, fixture_id: int) -> dict | None:
        """Odds pré-jogo por fixture (1 pedido, cache 1h)."""
        data = self._request(
            "/odds",
            {"fixture": fixture_id},
            cache_ttl=_ODDS_TTL,
        )
        items = (data or {}).get("response") or []
        if not items:
            return None
        return self._extract_odds_hint(items[0].get("bookmakers") or [])

    def _item_to_live_fixture(self, item: dict) -> LiveFixture | None:
        fix = item.get("fixture") or {}
        status = fix.get("status") or {}
        short = str(status.get("short") or "").upper()
        if short not in _LIVE_ACTIVE:
            return None

        league = item.get("league") or {}
        teams = item.get("teams") or {}
        home = (teams.get("home") or {}).get("name", "").strip()
        away = (teams.get("away") or {}).get("name", "").strip()
        if not home or not away:
            return None

        goals = item.get("goals") or {}
        hs = goals.get("home")
        aw = goals.get("away")
        home_score = int(hs) if hs is not None else 0
        away_score = int(aw) if aw is not None else 0
        elapsed = int(status.get("elapsed") or 0)
        extra = int(status.get("extra") or 0)

        ht_home = ht_away = None
        ht = (item.get("score") or {}).get("halftime") or {}
        if ht.get("home") is not None and ht.get("away") is not None:
            ht_home = int(ht["home"])
            ht_away = int(ht["away"])

        return LiveFixture(
            home=home,
            away=away,
            league=league.get("name", "Soccer"),
            stage=str(league.get("round") or ""),
            kickoff=str(fix.get("date") or ""),
            home_score=home_score,
            away_score=away_score,
            minute=elapsed,
            injury_time=extra,
            ht_home_score=ht_home,
            ht_away_score=ht_away,
            status_short=short,
            fixture_id=fix.get("id"),
            source="api-football",
        )

    def _scan_live_api_football(self) -> list[LiveFixture]:
        if not self.is_configured:
            return []

        data = self._request(
            "/fixtures",
            {"live": "all"},
            cache_ttl=_LIVE_TTL,
        )
        fixtures: list[LiveFixture] = []
        for item in (data or {}).get("response") or []:
            live = self._item_to_live_fixture(item)
            if live:
                fixtures.append(live)
        fixtures.sort(key=lambda f: f.league)
        return fixtures

    def scan_live(self) -> list[LiveFixture]:
        """Jogos ao vivo — API-Football, com fallback ESPN (grátis)."""
        fixtures = self._scan_live_api_football()
        if fixtures:
            self.last_live_source = "api-football"
            return fixtures

        from discovery.espn_live_scanner import EspnLiveScanner

        fixtures = EspnLiveScanner().scan()
        self.last_live_source = "espn" if fixtures else "none"
        return fixtures

    def enrich_live_odds(
        self,
        fixtures: list[LiveFixture],
        *,
        prefer_live: bool = True,
    ) -> None:
        """Delegado em LiveOddsFetcher — mantido por compatibilidade."""
        from discovery.live_odds_fetcher import LiveOddsFetcher

        LiveOddsFetcher(self).enrich(fixtures, prefer_live=prefer_live)

    def scan_fixtures(self, hours_ahead: int = 12) -> list[UpcomingFixture]:
        """Jogos por data (1 pedido por dia — económico no plano grátis)."""
        if not self.is_configured:
            return []

        now = datetime.now(timezone.utc)
        dates = [now.date().isoformat()]
        if hours_ahead > 8:
            dates.append((now + timedelta(days=1)).date().isoformat())

        fixtures: list[UpcomingFixture] = []
        for day in dates:
            data = self._request(
                "/fixtures",
                {"date": day, "timezone": "UTC"},
                cache_ttl=_FIXTURE_TTL,
            )
            for item in (data or {}).get("response") or []:
                fx = self._item_to_fixture(item, hours_ahead)
                if fx:
                    fixtures.append(fx)
        return fixtures

    def resolve_team_id(self, team_name: str) -> int | None:
        key = team_name.strip().lower()
        cached = cache_get("api_football_team_id", key, _DEFAULT_TTL)
        if cached is not None:
            return int(cached)

        search = self._request(
            "/teams",
            {"search": team_name},
            cache_ttl=_DEFAULT_TTL,
        )
        teams = (search or {}).get("response") or []
        if not teams:
            return None

        team_id = teams[0].get("team", {}).get("id")
        if not team_id:
            return None
        cache_set("api_football_team_id", key, int(team_id))
        return int(team_id)

    def team_last_fixtures(
        self, team_name: str, last_n: int = 10
    ) -> list[dict]:
        """Últimos jogos terminados — 1 pedido se o ID já estiver em cache."""
        team_id = self.resolve_team_id(team_name)
        if not team_id:
            return []

        data = self._request(
            "/fixtures",
            {"team": team_id, "last": last_n, "status": "FT"},
            cache_ttl=_DEFAULT_TTL,
        )
        return (data or {}).get("response") or []

    def fetch_fixture_statistics(self, fixture_id: int) -> dict | None:
        """Estatísticas ao vivo — posse, chutes, cantos, etc. (cache 45s)."""
        return self._request(
            "/fixtures/statistics",
            {"fixture": fixture_id},
            cache_ttl=_LIVE_TTL,
        )

    def fetch_fixture_statistics_ft(self, fixture_id: int) -> dict | None:
        """Estatísticas finais pós-jogo (cache 24h)."""
        return self._request(
            "/fixtures/statistics",
            {"fixture": fixture_id},
            cache_ttl=_DEFAULT_TTL,
        )

    def fetch_fixture_events(self, fixture_id: int) -> dict | None:
        """Eventos do jogo — golos, cartões, substituições (cache 45s)."""
        return self._request(
            "/fixtures/events",
            {"fixture": fixture_id},
            cache_ttl=_LIVE_TTL,
        )

    def fetch_fixture_events_ft(self, fixture_id: int) -> dict | None:
        """Eventos finais pós-jogo (cache 24h)."""
        return self._request(
            "/fixtures/events",
            {"fixture": fixture_id},
            cache_ttl=_DEFAULT_TTL,
        )

    def team_form_scores(
        self, team_name: str, last_n: int = 10
    ) -> tuple[list[int], list[int]] | None:
        """Extrai golos marcados/sofridos dos últimos jogos."""
        needle = team_name.strip().lower()
        scored: list[int] = []
        conceded: list[int] = []

        for item in self.team_last_fixtures(team_name, last_n=last_n):
            teams = item.get("teams") or {}
            goals = item.get("goals") or {}
            home = (teams.get("home") or {}).get("name", "")
            away = (teams.get("away") or {}).get("name", "")
            hs = goals.get("home")
            aw = goals.get("away")
            if hs is None or aw is None:
                continue
            if needle in home.lower():
                scored.append(int(hs))
                conceded.append(int(aw))
            elif needle in away.lower():
                scored.append(int(aw))
                conceded.append(int(hs))

        if not scored:
            return None
        return scored, conceded