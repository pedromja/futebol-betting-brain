"""Obtém resultado final de jogos — API-Football com cache longo."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from discovery.api_football_client import ApiFootballClient

_FINISHED = frozenset({"FT", "AET", "PEN", "AWD", "WO"})


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


class ResultFetcher:
    def __init__(self, client: ApiFootballClient | None = None):
        self.client = client or ApiFootballClient()

    def by_fixture_id(self, fixture_id: int) -> FinalScore | None:
        if not self.client.is_configured or not fixture_id:
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
        if not self.client.is_configured or not kickoff:
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
        return self.by_teams_and_kickoff(home, away, kickoff)