"""Obtém resultado final de jogos — API-Football + fallback ESPN."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from discovery.api_football_client import ApiFootballClient
from discovery.quota_guard import PROVIDER_API_FOOTBALL, is_exhausted
from discovery.web_browser import WebBrowser
from discovery.web_fixture_scanner import ESPN_EXTRA, ESPN_PRIORITY

_FINISHED = frozenset({"FT", "AET", "PEN", "AWD", "WO"})
_ESPN_FINISHED_NAMES = frozenset(
    {"STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_AFTER_PENALTIES", "STATUS_AFTER_EXTRA_TIME"}
)
_ESPN_LEAGUES: dict[str, str] = {**ESPN_PRIORITY, **ESPN_EXTRA}

# Grupos de nomes equivalentes (chaves já normalizadas: só a-z0-9).
_TEAM_ALIAS_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"ivorycoast", "ctedivoire", "cotedivoire"}),
    frozenset({"unitedstates", "usa", "usmnt"}),
    frozenset({"southkorea", "korearepublic", "republicofkorea"}),
    frozenset({"czechrepublic", "czechia"}),
    frozenset({"northmacedonia", "macedonia"}),
    frozenset({"bosniaandherzegovina", "bosniaherzegovina"}),
    frozenset({"drcongo", "congodr", "democraticrepublicofcongo"}),
    frozenset({"republicofireland", "ireland"}),
    frozenset({"northernireland", "nireland"}),
)


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


def _team_keys(name: str) -> set[str]:
    n = _normalize(name)
    keys = {n}
    for group in _TEAM_ALIAS_GROUPS:
        if n in group:
            keys |= group
    return keys


def _names_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    a_keys = _team_keys(a)
    b_keys = _team_keys(b)
    if a_keys & b_keys:
        return True
    an, bn = _normalize(a), _normalize(b)
    return an in bn or bn in an


def _teams_match(home: str, away: str, item: dict) -> bool:
    teams = item.get("teams") or {}
    eh = (teams.get("home") or {}).get("name", "")
    ea = (teams.get("away") or {}).get("name", "")
    direct = _names_match(home, eh) and _names_match(away, ea)
    swap = _names_match(home, ea) and _names_match(away, eh)
    return direct or swap


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


def _espn_summary_to_final(payload: dict) -> FinalScore | None:
    header = payload.get("header") or {}
    comps = (header.get("competitions") or [{}])[0]
    return _espn_comp_to_final(comps)


def _espn_teams_match(home: str, away: str, comp: dict) -> bool:
    names: list[str] = []
    for c in comp.get("competitors") or []:
        team = (c.get("team") or {}).get("displayName", "")
        if team:
            names.append(team)
    if len(names) < 2:
        return False
    direct = _names_match(home, names[0]) and _names_match(away, names[1])
    swap = _names_match(home, names[1]) and _names_match(away, names[0])
    return direct or swap


def _parse_kickoff(kickoff: str) -> datetime | None:
    if not kickoff:
        return None
    try:
        dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _espn_date_keys(kickoff: str) -> list[str]:
    """Datas ESPN a consultar — inclui dia anterior/seguinte para jogos noturnos."""
    dt = _parse_kickoff(kickoff)
    if not dt:
        return []
    keys = [dt.strftime("%Y%m%d")]
    if dt.hour < 8:
        prev = (dt - timedelta(days=1)).strftime("%Y%m%d")
        if prev not in keys:
            keys.insert(0, prev)
    if dt.hour >= 20:
        nxt = (dt + timedelta(days=1)).strftime("%Y%m%d")
        if nxt not in keys:
            keys.append(nxt)
    return keys


def _is_world_cup_league(league: str) -> bool:
    low = (league or "").lower()
    return any(
        token in low
        for token in ("world cup", "fifa world", "mundial", "copa do mundo")
    )


def _espn_league_codes_for_resolve(
    *,
    league: str = "",
    espn_league_code: str | None = None,
) -> list[str]:
    codes: list[str] = []
    seen: set[str] = set()

    def _add(code: str) -> None:
        if code and code not in seen:
            codes.append(code)
            seen.add(code)

    if espn_league_code:
        _add(espn_league_code)
    if _is_world_cup_league(league):
        _add("fifa.world")
    for code in _ESPN_LEAGUES:
        _add(code)
    return codes


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
        dt = _parse_kickoff(kickoff)
        if not dt:
            return None
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

    def by_espn_event_id(
        self,
        event_id: str,
        *,
        league_code: str | None = None,
        league: str = "",
    ) -> FinalScore | None:
        if not event_id:
            return None
        for code in _espn_league_codes_for_resolve(
            league=league, espn_league_code=league_code
        ):
            url = (
                "https://site.api.espn.com/apis/site/v2/sports/soccer/"
                f"{code}/summary?event={event_id}"
            )
            data = self.browser.fetch_json(
                url, cache_ns="espn_result_summary", cache_ttl=3600
            )
            if not isinstance(data, dict):
                continue
            header = data.get("header") or {}
            hid = str(header.get("id") or "")
            if hid and hid != str(event_id):
                continue
            final = _espn_summary_to_final(data)
            if final:
                return final
        return None

    def by_espn(
        self,
        home: str,
        away: str,
        kickoff: str,
        *,
        league: str = "",
        espn_league_code: str | None = None,
    ) -> FinalScore | None:
        if not kickoff:
            return None
        date_keys = _espn_date_keys(kickoff)
        if not date_keys:
            return None

        league_codes = _espn_league_codes_for_resolve(
            league=league, espn_league_code=espn_league_code
        )
        for date_key in date_keys:
            for code in league_codes:
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
        *,
        espn_event_id: str | None = None,
        espn_league_code: str | None = None,
        league: str = "",
    ) -> FinalScore | None:
        if espn_event_id:
            found = self.by_espn_event_id(
                espn_event_id,
                league_code=espn_league_code,
                league=league,
            )
            if found:
                return found
        if fixture_id:
            found = self.by_fixture_id(fixture_id)
            if found:
                return found
        found = self.by_teams_and_kickoff(home, away, kickoff)
        if found:
            return found
        return self.by_espn(
            home,
            away,
            kickoff,
            league=league,
            espn_league_code=espn_league_code,
        )