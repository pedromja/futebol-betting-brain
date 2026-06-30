"""Sync automático Transfermarkt para equipas do calendário do dia."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Iterable

from prematch.transfermarkt import api_client
from prematch.transfermarkt.cache import load_squads
from prematch.transfermarkt.match_names import find_in_index, normalize_team
from prematch.transfermarkt.sync import log_sync_event, sync_team_from_api
from prematch.transfermarkt.store import get_store

if TYPE_CHECKING:
    from discovery.fixture_types import UpcomingFixture

_INTERNATIONAL_MARKERS = (
    "world cup",
    "copa do mundo",
    "euro 20",
    "european championship",
    "uefa nations",
    "nations league",
    "international",
    "friendly",
    "amigável",
    "amigavel",
    "fifa",
    "qualification",
    "qualificação",
    "qualificacao",
    "copa america",
    "africa cup",
    "asian cup",
    "concacaf",
)

_LEAGUE_COUNTRY: dict[str, str] = {
    "primeira liga": "Portugal",
    "liga portugal": "Portugal",
    "segunda liga": "Portugal",
    "ligue 1": "France",
    "ligue 2": "France",
    "premier league": "England",
    "championship": "England",
    "la liga": "Spain",
    "bundesliga": "Germany",
    "serie a": "Italy",
    "eredivisie": "Netherlands",
    "pro league": "Belgium",
}

_ISO_COUNTRY: dict[str, str] = {
    "PT": "Portugal",
    "FR": "France",
    "GB": "England",
    "EN": "England",
    "ES": "Spain",
    "DE": "Germany",
    "IT": "Italy",
    "NL": "Netherlands",
    "BE": "Belgium",
    "NO": "Norway",
    "CI": "Ivory Coast",
    "BR": "Brazil",
    "JP": "Japan",
}

_NATIONAL_SEARCH_ALIASES: dict[str, str] = {
    "ivory coast": "Côte d'Ivoire",
    "cote divoire": "Côte d'Ivoire",
    "usa": "United States",
    "u.s.a.": "United States",
    "south korea": "Korea Republic",
    "korea republic": "Korea Republic",
    "czech republic": "Czechia",
}

_SESSION_SYNCED: set[str] = set()


def auto_sync_enabled() -> bool:
    return os.getenv("TRANSFERMARKT_AUTO_SYNC", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def auto_sync_max_teams() -> int:
    try:
        return max(1, min(32, int(os.getenv("TRANSFERMARKT_AUTO_SYNC_MAX", "8"))))
    except ValueError:
        return 8


def is_international_fixture(league: str = "", stage: str = "") -> bool:
    text = f"{league} {stage}".lower()
    return any(marker in text for marker in _INTERNATIONAL_MARKERS)


def prefer_country_for_fixture(
    league: str = "",
    fixture_country: str = "",
    *,
    national: bool = False,
    team: str = "",
) -> str:
    if national:
        key = team_key(team)
        if key in _NATIONAL_SEARCH_ALIASES:
            return _NATIONAL_SEARCH_ALIASES[key]
        return normalize_team(team) or "World"
    league_l = (league or "").lower()
    for hint, country in _LEAGUE_COUNTRY.items():
        if hint in league_l:
            return country
    iso = (fixture_country or "").strip().upper()
    return _ISO_COUNTRY.get(iso, "Portugal")


def team_key(name: str) -> str:
    return normalize_team(name).lower()


def national_search_terms(team: str) -> list[str]:
    label = normalize_team(team)
    if not label:
        return []
    terms = [label]
    alias = _NATIONAL_SEARCH_ALIASES.get(label.lower())
    if alias and alias not in terms:
        terms.append(alias)
    return terms


def squad_needs_sync(team: str, squads: dict[str, dict] | None = None) -> bool:
    index = squads if squads is not None else load_squads()
    hit = find_in_index(team, index)
    if not hit:
        return True
    _, row = hit
    if not row.get("tm_club_id"):
        return True
    if str(row.get("source") or "") != "transfermarkt-api":
        return True
    return False


def _collect_team_jobs(
    fixtures: Iterable[UpcomingFixture],
) -> list[tuple[str, str, bool]]:
    """(team, prefer_country, national) únicos, ordem estável."""
    seen: set[str] = set()
    jobs: list[tuple[str, str, bool]] = []
    squads = load_squads()

    for fx in fixtures:
        if getattr(fx, "source", "") == "sample":
            continue
        national = is_international_fixture(fx.league, fx.stage)
        for team in (fx.home, fx.away):
            key = team_key(team)
            if not key or key in seen:
                continue
            seen.add(key)
            if not squad_needs_sync(team, squads):
                continue
            prefer = prefer_country_for_fixture(
                fx.league,
                fx.country,
                national=national,
                team=team,
            )
            jobs.append((team, prefer, national))
    return jobs


def _sync_one_team(team: str, prefer_country: str, national: bool) -> dict:
    fast = {"fetch_injury_history": False}
    if national:
        for term in national_search_terms(team):
            result = sync_team_from_api(
                term, prefer_country=prefer_country, national=True, **fast
            )
            if result.get("ok"):
                return result
        return sync_team_from_api(
            team, prefer_country=prefer_country, national=True, **fast
        )
    result = sync_team_from_api(
        team, prefer_country=prefer_country, national=False, **fast
    )
    if result.get("ok"):
        return result
    return sync_team_from_api(team, prefer_country=prefer_country, national=True, **fast)


def sync_calendar_teams(
    fixtures: Iterable[UpcomingFixture],
    *,
    max_teams: int | None = None,
    log: bool = True,
) -> dict | None:
    """
    Sincroniza equipas em falta no cache para o calendário indicado.
    Devolve resumo ou None se desactivado / sem trabalho / API indisponível.
    """
    if not auto_sync_enabled() or not api_client.is_configured():
        return None

    limit = max_teams if max_teams is not None else auto_sync_max_teams()
    jobs = _collect_team_jobs(fixtures)
    if not jobs:
        return None

    results: list[dict] = []
    for team, prefer, national in jobs:
        if len(results) >= limit:
            break
        key = team_key(team)
        if key in _SESSION_SYNCED:
            continue
        row = _sync_one_team(team, prefer, national)
        results.append(row)
        if row.get("ok"):
            _SESSION_SYNCED.add(team_key(row.get("team") or team))

    if not results:
        return None

    ok = sum(1 for r in results if r.get("ok"))
    summary = {
        "synced": ok,
        "total": len(results),
        "results": results,
        "api_base": api_client.api_base_url(),
        "trigger": "calendar",
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if log:
        log_sync_event(summary)
    get_store().reload()
    return summary


def sync_match_teams(
    home: str,
    away: str,
    *,
    league: str = "",
    stage: str = "",
    fixture_country: str = "",
    log: bool = False,
) -> dict | None:
    """Sync on-demand para um confronto (ex.: abrir detalhe do jogo)."""

    class _Fx:
        pass

    fx = _Fx()
    fx.home = home
    fx.away = away
    fx.league = league
    fx.stage = stage
    fx.country = fixture_country
    fx.source = "api"
    return sync_calendar_teams([fx], max_teams=2, log=log)