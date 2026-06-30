"""Cruza odds ESPN com casas de nicho (The-Odds-API) — usa a menos favorável."""

from __future__ import annotations

import os

from discovery.live_fixture_types import LiveFixture
from discovery.quota_guard import PROVIDER_THE_ODDS, is_exhausted
from discovery.response_cache import get as cache_get
from discovery.response_cache import set as cache_set
from odds.conservative_merge import merge_conservative_odds, public_odds_compare
from odds.the_odds_api import TheOddsApiClient, match_odds_to_hint

_CACHE_TTL = 120

_ESPN_LEAGUE_TO_SPORT: dict[str, str] = {
    "fifa.world": "soccer_fifa_world_cup",
    "eng.1": "soccer_epl",
    "esp.1": "soccer_spain_la_liga",
    "ita.1": "soccer_italy_serie_a",
    "ger.1": "soccer_germany_bundesliga",
    "fra.1": "soccer_france_ligue_one",
    "por.1": "soccer_portugal_primeira_liga",
    "uefa.champions": "soccer_uefa_champs_league",
    "uefa.europa": "soccer_uefa_europa_league",
}


def _sport_key_for_fixture(fx: LiveFixture) -> str | None:
    code = str(fx.espn_league_code or "").strip()
    if code in _ESPN_LEAGUE_TO_SPORT:
        return _ESPN_LEAGUE_TO_SPORT[code]
    league = (fx.league or "").lower()
    for pattern, sport in _ESPN_LEAGUE_TO_SPORT.items():
        if pattern.replace(".", " ") in league or pattern.split(".")[0] in league:
            return sport
    return None


def _fetch_niche_hint(
    fx: LiveFixture,
    client: TheOddsApiClient,
) -> tuple[dict | None, str]:
    cache_id = f"{fx.home}|{fx.away}|{fx.espn_league_code}"
    cached = cache_get("niche_odds_hint", cache_id, _CACHE_TTL)
    if isinstance(cached, dict) and cached.get("hint"):
        return cached.get("hint"), str(cached.get("book") or "")

    sport = _sport_key_for_fixture(fx)
    result = client.fetch_niche_for_teams(fx.home, fx.away, sport_key=sport)
    if not result:
        return None, ""

    hint = match_odds_to_hint(result.match_odds)
    book = result.bookmaker or ""
    cache_set(
        "niche_odds_hint",
        cache_id,
        {"hint": hint, "book": book, "book_title": result.bookmaker_title},
    )
    return hint, book


def enrich_live_odds(fx: LiveFixture) -> None:
    """
    Enriquece odds_hint: por mercado, min(ESPN, casa de nicho).
    Requer THE_ODDS_API_KEY; sem chave mantém só ESPN.
    """
    if not fx.odds_hint:
        return
    if fx.odds_hint.get("_odds_enriched"):
        return

    api_key = os.getenv("THE_ODDS_API_KEY", "")
    if not api_key or is_exhausted(PROVIDER_THE_ODDS):
        fx.odds_source = fx.odds_source or "espn-live"
        return

    client = TheOddsApiClient(api_key=api_key, region="eu")
    if not client.is_configured:
        fx.odds_source = fx.odds_source or "espn-live"
        return

    espn_hint = dict(fx.odds_hint)
    niche_hint, niche_book = _fetch_niche_hint(fx, client)
    if not niche_hint:
        fx.odds_source = fx.odds_source or "espn-live"
        return

    fx.odds_hint = merge_conservative_odds(espn_hint, niche_hint, niche_book=niche_book)
    fx.odds_source = "espn+niche-min"


def odds_compare_summary(fx: LiveFixture) -> dict | None:
    return public_odds_compare(fx.odds_hint)