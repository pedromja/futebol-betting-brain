"""Obtém resultado final de jogos — API-Football + fallback ESPN."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from discovery.api_football_client import ApiFootballClient
from discovery.quota_guard import PROVIDER_API_FOOTBALL, is_exhausted
from discovery.web_browser import WebBrowser
from discovery.web_fixture_scanner import ESPN_EXTRA, ESPN_PRIORITY

_FINISHED = frozenset({"FT", "AET", "PEN", "AWD", "WO"})
_ESPN_FINISHED_NAMES = frozenset(
    {"STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_AFTER_PENALTIES", "STATUS_AFTER_EXTRA_TIME"}
)
_ESPN_LEAGUES: dict[str, str] = {**ESPN_PRIORITY, **ESPN_EXTRA}


@dataclass
class FinalScore:
    home: str
    away: str
    home_goals: int
    away_goals: int
    score_label: str
    status: str
    fixture_id: int | None = None


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _teams_match(home: str, away: str, item: dict) -> bool:
    teams = item.get("teams") or {}
    eh = (teams.get("home") or {}).get("name", "")
    ea = (teams.get("away") or {}).get("name", "")
    nh, na, eh_n, ea_n = map(_normalize, (home, away, eh, ea))
    return (
        (nh in eh_n or eh_n in nh) and (na in ea_n or ea_n in na)
    ) or (
        (nh in ea_n or ea_n in nh) and (na in eh_n or eh_n in na)
    )


def _item_to_final(item: dict) -> FinalScore | None:
    fix = item.get("fixture") or {}
    status = str((fix.get("status") or {}).get("short") or "").upper()
    if status not in _FINISHED:
        return None

    teams = item.get("teams") or {}
    home = (teams.get("home") or {}).get("name", "").strip()
    away = (teams.get("away") or {}).get("name", "").strip()
    goals = item.get("goals") or {}
    hg = goals.get("home")
    ag = goals.get("away")
    if hg is None or ag is None:
        score = item.get("score", {}).get("fulltime") or {}
        hg = score.get("home")
        ag = score.get("away")
    if hg is None or ag is None:
        return None

    home_goals, away_goals = int(hg), int(ag)
    return FinalScore(
        home=home,
        away=away,
        home_goals=home_goals,
        away_goals=away_goals,
        score_label=f"{home_goals}-{away_goals}",
        status=status,
        fixture_id=fix.get("id"),
    )


def _espn_is_finished(status_type: dict) -> bool:
    if status_type.get("completed"):
        return True
    state = str(status_type.get("state") or "").lower()
    if state == "post":
        return True
    name = str(status_type.get("name") or "").upper()
    return name in _ESPN_FINISHED_NAMES or "FULL_TIME" in name


def _espn_comp_to_final(comp: dict) -> FinalScore | None:
    status = (comp.get("status") or {}).get("type") or {}
    if not _espn_is_finished(status):
        return None

    home_name = away_name = ""
    home_goals = away_goals = None
    for c in comp.get("competitors") or []:
        side = c.get("homeAway", "")
        team = (c.get("team") or {}).get("displayName", "").strip()
        score_raw = c.get("score")
        try:
            goals = int(score_raw) if score_raw is not None else None
        except (TypeError, ValueError):
            goals = None
        if side == "home":
            home_name = team
            home_goals = goals
        elif side == "away":
            away_name = team
            away_goals = goals

    if home_goals is None or away_goals is None or not home_name or not away_name:
        return None

    return FinalScore(
        home=home_name,
        away=away_name,
        home_goals=home_goals,
        away_goals=away_goals,
        score_label=f"{home_goals}-{away_goals}",
        status="FT",
        fixture_id=None,
    )


def _espn_teams_match(home: str, away: str, comp: dict) -> bool:
    names: list[str] = []
    for c in comp.get("competitors") or []:
        team = (c.get("team") or {}).get("displayName", "")
        if team:
            names.append(team)
    if len(names) < 2:
        return False
    nh, na = map(_normalize, (home, away))
    cn = [_normalize(n) for n in names]
    return (
        (nh in cn[0] or cn[0] in nh) and (na in cn[1] or cn[1] in na)
    ) or (
        (nh in cn[1] or cn[1] in nh) and (na in cn[0] or cn[0] in na)
    )


class ResultFetcher:
    def __init__(
        self,
        client: ApiFootballClient | None = None,
        browser: WebBrowser | None = None,
    ):
        self.client = client or ApiFootballClient()
        self.browser = browser or WebBrowser()

    def _api_available(self) -> bool:
        return self.client.is_configured and not is_exhausted(PROVIDER_API_FOOTBALL)

    def by_fixture_id(self, fixture_id: int) -> FinalScore | None:
        if not self._api_available() or not fixture_id:
            return None
        data = self.client._request(
            "/fixtures",
            {"id": int(fixture_id)},
            cache_ttl=86400,
        )
        for item in (data or {}).get("response") or []:
            final = _item_to_final(item)
            if final:
                return final
        return None

    def by_teams_and_kickoff(
        self,
        home: str,
        away: str,
        kickoff: str,
    ) -> FinalScore | None:
        if not self._api_available() or not kickoff:
            return None
        try:
            dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        date = dt.date().isoformat()

        data = self.client._request(
            "/fixtures",
            {"date": date},
            cache_ttl=86400,
        )
        for item in (data or {}).get("response") or []:
            if not _teams_match(home, away, item):
                continue
            final = _item_to_final(item)
            if final:
                return final
        return None

    def by_espn(
        self,
        home: str,
        away: str,
        kickoff: str,
    ) -> FinalScore | None:
        if not kickoff:
            return None
        try:
            dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        date_key = dt.strftime("%Y%m%d")

        for code in _ESPN_LEAGUES:
            url = (
                "https://site.api.espn.com/apis/site/v2/sports/soccer/"
                f"{code}/scoreboard?dates={date_key}"
            )
            data = self.browser.fetch_json(
                url, cache_ns="espn_result_scoreboard", cache_ttl=3600
            )
            if not isinstance(data, dict):
                continue
            for event in data.get("events") or []:
                comp = (event.get("competitions") or [{}])[0]
                if not _espn_teams_match(home, away, comp):
                    continue
                final = _espn_comp_to_final(comp)
                if final:
                    return final
        return None

    def resolve(
        self,
        home: str,
        away: str,
        kickoff: str,
        fixture_id: int | None = None,
    ) -> FinalScore | None:
        if fixture_id:
            found = self.by_fixture_id(fixture_id)
            if found:
                return found
        found = self.by_teams_and_kickoff(home, away, kickoff)
        if found:
            return found
        return self.by_espn(home, away, kickoff)