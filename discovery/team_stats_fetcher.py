"""
Stats de forma recente — APIs gratuitas com cache e limitador.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from discovery.api_football_client import ApiFootballClient
from discovery.rate_limiter import MinIntervalLimiter
from discovery.response_cache import get as cache_get
from discovery.response_cache import set as cache_set
from discovery.web_browser import WebBrowser
from models.team_stats import TeamForm

FD_BASE = "https://api.football-data.org/v4"
SPORTS_DB = "https://www.thesportsdb.com/api/v1/json/3"
_FD_LIMITER = MinIntervalLimiter(6.5)
_STATS_TTL = 86400
# Free tier: /teams?name= ignora o filtro; IDs vêm das plantéis destas competições.
_FD_FREE_COMPETITIONS = ("WC", "EC", "CL", "PL", "PD", "BL1", "SA", "DED", "PPL", "CLI")
_FD_TEAM_INDEX_KEY = "team_index_v1"


@dataclass
class FormSnapshot:
    scored_avg: float
    conceded_avg: float
    games_played: int
    scored_in_last_n: int
    conceded_in_last_n: int
    last_n: int
    source: str


class TeamStatsFetcher:
    def __init__(
        self,
        football_data_key: str | None = None,
        api_football_key: str | None = None,
        browser: WebBrowser | None = None,
        last_n: int = 10,
    ):
        self.fd_key = football_data_key or os.getenv("FOOTBALL_DATA_API_KEY", "")
        self.api_football = ApiFootballClient(api_key=api_football_key)
        self.browser = browser or WebBrowser()
        self.last_n = last_n
        self._session: dict[str, FormSnapshot | None] = {}
        self._fd_team_index: dict[str, int] | None = None

    def _cache_key(self, team_name: str) -> str:
        return team_name.strip().lower()

    def _load_cached_snapshot(self, team_name: str) -> FormSnapshot | None:
        key = self._cache_key(team_name)
        if key in self._session:
            return self._session[key]

        raw = cache_get("team_stats", key, _STATS_TTL)
        if raw and isinstance(raw, dict):
            snap = FormSnapshot(**raw)
            self._session[key] = snap
            return snap
        return None

    def _store_snapshot(self, team_name: str, snap: FormSnapshot | None) -> None:
        key = self._cache_key(team_name)
        self._session[key] = snap
        if snap:
            cache_set("team_stats", key, snap.__dict__)

    def _fd_request(self, path: str, params: dict | None = None) -> dict | None:
        if not self.fd_key:
            return None
        q = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{FD_BASE}{path}{q}"
        cached = cache_get("football_data", url, _STATS_TTL)
        if cached is not None:
            return cached

        _FD_LIMITER.wait()
        req = urllib.request.Request(
            url,
            headers={"X-Auth-Token": self.fd_key},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return None

        if data:
            cache_set("football_data", url, data)
        return data

    def _snapshot_from_scores(
        self, team_name: str, scored: list[int], conceded: list[int], source: str
    ) -> FormSnapshot | None:
        if not scored:
            return None
        n = len(scored)
        return FormSnapshot(
            scored_avg=round(sum(scored) / n, 2),
            conceded_avg=round(sum(conceded) / n, 2),
            games_played=n,
            scored_in_last_n=sum(1 for g in scored if g > 0),
            conceded_in_last_n=sum(1 for g in conceded if g > 0),
            last_n=n,
            source=source,
        )

    @staticmethod
    def _normalize_team_name(name: str) -> str:
        return name.strip().lower()

    def _thesportsdb_aliases(self, team_name: str) -> list[str]:
        search_url = f"{SPORTS_DB}/searchteams.php?t={urllib.parse.quote(team_name)}"
        data = self.browser.fetch_json(
            search_url, cache_ns="thesportsdb_team", cache_ttl=_STATS_TTL
        )
        teams = (data or {}).get("teams") or []
        if not teams:
            return [team_name]

        team = teams[0]
        aliases = [team_name, team.get("strTeam", ""), team.get("strTeamShort", "")]
        alt = team.get("strTeamAlternate") or ""
        aliases.extend(part.strip() for part in alt.split(",") if part.strip())
        return list(dict.fromkeys(a for a in aliases if a))

    def _load_fd_team_index(self) -> dict[str, int]:
        if self._fd_team_index is not None:
            return self._fd_team_index

        cached = cache_get("football_data", _FD_TEAM_INDEX_KEY, _STATS_TTL)
        if isinstance(cached, dict) and cached:
            self._fd_team_index = {str(k): int(v) for k, v in cached.items()}
            return self._fd_team_index

        index: dict[str, int] = {}
        for code in _FD_FREE_COMPETITIONS:
            data = self._fd_request(f"/competitions/{code}/teams")
            for team in (data or {}).get("teams") or []:
                team_id = team.get("id")
                if not team_id:
                    continue
                for field in ("name", "shortName", "tla"):
                    label = team.get(field)
                    if label:
                        index[self._normalize_team_name(label)] = int(team_id)

        if index:
            cache_set("football_data", _FD_TEAM_INDEX_KEY, index)
        self._fd_team_index = index
        return index

    def _resolve_fd_team_id(self, team_name: str) -> int | None:
        index = self._load_fd_team_index()
        if not index:
            return None

        aliases = self._thesportsdb_aliases(team_name)
        for alias in aliases:
            hit = index.get(self._normalize_team_name(alias))
            if hit:
                return hit

        needle = self._normalize_team_name(team_name)
        for label, team_id in index.items():
            if needle in label or label in needle:
                return team_id
        return None

    def _fetch_football_data(self, team_name: str) -> FormSnapshot | None:
        team_id = self._resolve_fd_team_id(team_name)
        if not team_id:
            return None
        matches = self._fd_request(
            f"/teams/{team_id}/matches",
            {"status": "FINISHED", "limit": self.last_n},
        )
        if not matches:
            return None

        scored: list[int] = []
        conceded: list[int] = []
        for m in (matches.get("matches") or [])[: self.last_n]:
            home = m.get("score", {}).get("fullTime", {}).get("home")
            away = m.get("score", {}).get("fullTime", {}).get("away")
            if home is None or away is None:
                continue
            is_home = m.get("homeTeam", {}).get("name", "").lower() == team_name.lower()
            if is_home:
                scored.append(home)
                conceded.append(away)
            else:
                scored.append(away)
                conceded.append(home)

        return self._snapshot_from_scores(team_name, scored, conceded, "football-data.org")

    def _fetch_thesportsdb(self, team_name: str) -> FormSnapshot | None:
        search_url = f"{SPORTS_DB}/searchteams.php?t={urllib.parse.quote(team_name)}"
        data = self.browser.fetch_json(
            search_url, cache_ns="thesportsdb_team", cache_ttl=_STATS_TTL
        )
        teams = (data or {}).get("teams") or []
        if not teams:
            return None

        team_id = teams[0]["idTeam"]
        last_url = f"{SPORTS_DB}/eventslast.php?id={team_id}"
        last = self.browser.fetch_json(
            last_url, cache_ns="thesportsdb_last", cache_ttl=_STATS_TTL
        )
        results = (last or {}).get("results") or []

        scored: list[int] = []
        conceded: list[int] = []
        for ev in results[: self.last_n]:
            home_team = ev.get("strHomeTeam", "")
            try:
                hs = int(ev.get("intHomeScore", 0))
                aws = int(ev.get("intAwayScore", 0))
            except (TypeError, ValueError):
                continue
            if team_name.lower() in home_team.lower():
                scored.append(hs)
                conceded.append(aws)
            elif team_name.lower() in ev.get("strAwayTeam", "").lower():
                scored.append(aws)
                conceded.append(hs)

        return self._snapshot_from_scores(team_name, scored, conceded, "thesportsdb_web")

    def _fetch_api_football(self, team_name: str) -> FormSnapshot | None:
        if not self.api_football.is_configured:
            return None
        scores = self.api_football.team_form_scores(team_name, last_n=self.last_n)
        if not scores:
            return None
        scored, conceded = scores
        return self._snapshot_from_scores(
            team_name, scored, conceded, "api-football"
        )

    def _pick_best_snapshot(
        self, *candidates: FormSnapshot | None
    ) -> FormSnapshot | None:
        valid = [snap for snap in candidates if snap and snap.games_played > 0]
        if not valid:
            return None
        return max(valid, key=lambda snap: snap.games_played)

    def fetch_form(self, team_name: str) -> FormSnapshot | None:
        cached = self._load_cached_snapshot(team_name)
        if cached and cached.games_played >= min(3, self.last_n):
            return cached

        tsdb_snap = self._fetch_thesportsdb(team_name)
        af_snap = self._fetch_api_football(team_name)
        fd_snap = self._fetch_football_data(team_name) if self.fd_key else None
        snap = self._pick_best_snapshot(tsdb_snap, af_snap, fd_snap) or cached
        self._store_snapshot(team_name, snap)
        return snap

    def warm_teams(self, team_names: list[str], max_workers: int = 4) -> None:
        unique = list(dict.fromkeys(t for t in team_names if t))
        if not unique:
            return
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            list(pool.map(self.fetch_form, unique))

    def to_team_form(self, team_name: str, snapshot: FormSnapshot | None) -> TeamForm:
        if not snapshot:
            return TeamForm(name=team_name, goals_scored_avg=1.3, goals_conceded_avg=1.3)
        return TeamForm(
            name=team_name,
            goals_scored_avg=snapshot.scored_avg,
            goals_conceded_avg=snapshot.conceded_avg,
            games_played=snapshot.games_played,
            scored_in_last_n=snapshot.scored_in_last_n,
            conceded_in_last_n=snapshot.conceded_in_last_n,
            last_n=snapshot.last_n,
        )