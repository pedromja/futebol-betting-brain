"""
Cliente The-Odds-API v4 — odds decimais de casas de apostas.

Documentação: https://the-odds-api.com/liveapi/guides/v4/
Env: THE_ODDS_API_KEY

Mercados soccer suportados:
  h2h_3_way (1X2), totals (over/under golos), spreads (handicap asiático)
  btts (quando disponível no endpoint de evento)
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from markets.extended import ExtendedOdds
from models.team_stats import MatchOdds

from discovery.quota_guard import PROVIDER_THE_ODDS, is_exhausted, mark_exhausted

from .types import OddsFetchResult

BASE_URL = "https://api.the-odds-api.com/v4"

PREFERRED_BOOKMAKERS = [
    "pinnacle",
    "betfair_ex_uk",
    "draftkings",
    "fanduel",
    "bet365",
    "williamhill",
    "unibet",
    "betmgm",
]

# Casas de nicho (região EU) — 22bet não está na The-Odds-API; 1xBet = onexbet
NICHE_BOOKMAKERS = [
    "onexbet",
    "marathonbet",
    "suprabets",
    "betanysports",
    "coolbet",
    "mybookieag",
    "gtbets",
    "everygame",
]

DEFAULT_MARKETS = "h2h_3_way,totals,spreads"
EVENT_MARKETS = "h2h_3_way,totals,spreads,btts"


class TheOddsApiClient:
    def __init__(
        self,
        api_key: str | None = None,
        region: str = "eu",
        odds_format: str = "decimal",
    ):
        self.api_key = api_key or os.getenv("THE_ODDS_API_KEY", "")
        self.region = region
        self.odds_format = odds_format
        self._last_headers: dict[str, str] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _request(self, path: str, params: dict | None = None) -> list | dict | None:
        if not self.is_configured:
            return None
        if is_exhausted(PROVIDER_THE_ODDS):
            return None
        q = {"apiKey": self.api_key, **(params or {})}
        url = f"{BASE_URL}{path}?{urllib.parse.urlencode(q)}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                self._last_headers = {
                    k.lower(): v
                    for k, v in resp.headers.items()
                    if k.lower().startswith("x-requests")
                }
                remaining = self._credits_remaining()
                if remaining is not None and remaining <= 0:
                    mark_exhausted(PROVIDER_THE_ODDS, "credits 0")
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            if exc.code in (402, 429):
                mark_exhausted(PROVIDER_THE_ODDS, f"http {exc.code}")
            return None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return None

    def _credits_remaining(self) -> int | None:
        raw = self._last_headers.get("x-requests-remaining")
        try:
            return int(raw) if raw else None
        except ValueError:
            return None

    def list_soccer_sports(self) -> list[dict]:
        data = self._request("/sports", {"all": "true"})
        if not isinstance(data, list):
            return []
        return [
            s for s in data
            if isinstance(s, dict)
            and str(s.get("key", "")).startswith("soccer_")
            and s.get("active")
        ]

    def _norm(self, name: str) -> str:
        n = name.lower().strip()
        for ch in ".-'":
            n = n.replace(ch, " ")
        return re.sub(r"\s+", " ", n)

    def _teams_match(
        self, home: str, away: str, ev_home: str, ev_away: str
    ) -> bool:
        h, a = self._norm(home), self._norm(away)
        eh, ea = self._norm(ev_home), self._norm(ev_away)
        aliases = {
            "brazil": {"brazil", "brasil"},
            "japan": {"japan", "japao", "japão"},
        }

        def in_aliases(team: str, pool: set[str]) -> bool:
            for key, vals in aliases.items():
                if team in vals or key in team:
                    return any(v in pool or v in team for v in vals)
            return team in pool or any(team in p or p in team for p in pool)

        direct = (h in eh or eh in h) and (a in ea or ea in a)
        swap = (h in ea or ea in h) and (a in eh or eh in a)
        return direct or swap or (in_aliases(h, {eh}) and in_aliases(a, {ea}))

    def _pick_bookmaker(self, bookmakers: list[dict]) -> dict | None:
        if not bookmakers:
            return None
        by_key = {b.get("key", ""): b for b in bookmakers if isinstance(b, dict)}
        for pref in PREFERRED_BOOKMAKERS:
            if pref in by_key:
                return by_key[pref]
        return bookmakers[0]

    def _pick_niche_bookmaker(
        self, bookmakers: list[dict], event: dict
    ) -> dict | None:
        if not bookmakers:
            return None
        by_key = {b.get("key", ""): b for b in bookmakers if isinstance(b, dict)}
        for pref in NICHE_BOOKMAKERS:
            bm = by_key.get(pref)
            if not bm:
                continue
            match_odds, _ = self._parse_event(event, bm)
            if match_odds.home_win >= 1.05 and match_odds.away_win >= 1.05:
                return bm
        return None

    def _market_outcomes(self, bookmaker: dict, market_key: str) -> list[dict]:
        for m in bookmaker.get("markets", []):
            if m.get("key") == market_key:
                return m.get("outcomes", [])
        return []

    def _parse_event(
        self,
        event: dict,
        bookmaker: dict,
    ) -> tuple[MatchOdds, ExtendedOdds]:
        home = event.get("home_team", "")
        away = event.get("away_team", "")

        home_win = draw = away_win = 0.0
        for o in self._market_outcomes(bookmaker, "h2h_3_way"):
            name = o.get("name", "")
            price = float(o.get("price", 0))
            if name == "Draw":
                draw = price
            elif self._norm(name) == self._norm(home) or home in name:
                home_win = price
            elif self._norm(name) == self._norm(away) or away in name:
                away_win = price

        if not draw:
            for o in self._market_outcomes(bookmaker, "h2h"):
                name = o.get("name", "")
                price = float(o.get("price", 0))
                if self._norm(name) == self._norm(home) or home in name:
                    home_win = price
                elif self._norm(name) == self._norm(away) or away in name:
                    away_win = price

        over_25 = under_25 = 0.0
        totals_line = 2.5
        for o in self._market_outcomes(bookmaker, "totals"):
            point = float(o.get("point", 0))
            if abs(point - 2.5) < 0.01:
                totals_line = point
                label = o.get("name", "").lower()
                price = float(o.get("price", 0))
                if "over" in label:
                    over_25 = price
                elif "under" in label:
                    under_25 = price

        btts_yes = btts_no = 0.0
        for o in self._market_outcomes(bookmaker, "btts"):
            label = o.get("name", "").lower()
            price = float(o.get("price", 0))
            if label in ("yes", "sim"):
                btts_yes = price
            elif label in ("no", "não", "nao"):
                btts_no = price

        hc_home = hc_away = 0.0
        hc_home_line = hc_away_line = 0.0
        for o in self._market_outcomes(bookmaker, "spreads"):
            name = o.get("name", "")
            point = float(o.get("point", 0))
            price = float(o.get("price", 0))
            if self._norm(name) == self._norm(home) or home in name:
                hc_home = price
                hc_home_line = point
            elif self._norm(name) == self._norm(away) or away in name:
                hc_away = price
                hc_away_line = point

        match_odds = MatchOdds(
            home_win=home_win or 0,
            draw=draw or 0,
            away_win=away_win or 0,
            over_25=over_25 or 0,
            under_25=under_25 or 0,
            btts_yes=btts_yes or 0,
            btts_no=btts_no or 0,
        )

        extended = ExtendedOdds(
            handicap_home_line=hc_home_line,
            handicap_home=hc_home,
            handicap_away_line=hc_away_line,
            handicap_away=hc_away,
            corners_line=6.5,
            source=bookmaker.get("key", "the-odds-api"),
        )

        return match_odds, extended

    def _search_events(
        self,
        home: str,
        away: str,
        sport_keys: list[str] | None = None,
    ) -> tuple[dict | None, str]:
        keys = sport_keys or []
        if not keys:
            keys = [s["key"] for s in self.list_soccer_sports()]
            keys.insert(0, "upcoming")

        for sport in keys[:15]:
            data = self._request(
                f"/sports/{sport}/odds",
                {
                    "regions": self.region,
                    "markets": DEFAULT_MARKETS,
                    "oddsFormat": self.odds_format,
                },
            )
            if not isinstance(data, list):
                continue
            for ev in data:
                if not isinstance(ev, dict):
                    continue
                if self._teams_match(
                    home, away,
                    ev.get("home_team", ""),
                    ev.get("away_team", ""),
                ):
                    return ev, sport
        return None, ""

    def fetch_event_odds(
        self,
        event_id: str,
        sport_key: str,
    ) -> dict | None:
        return self._request(
            f"/sports/{sport_key}/events/{event_id}/odds",
            {
                "regions": self.region,
                "markets": EVENT_MARKETS,
                "oddsFormat": self.odds_format,
            },
        )

    def fetch_niche_for_teams(
        self,
        home: str,
        away: str,
        sport_key: str | None = None,
    ) -> OddsFetchResult | None:
        """Odds decimais de casas de nicho (1xBet, Marathon, etc.) — região EU."""
        if not self.is_configured:
            return None

        sport_keys = [sport_key] if sport_key else None
        event, found_sport = self._search_events(home, away, sport_keys)
        if not event:
            return None

        event_id = event.get("id", "")
        sport = found_sport or event.get("sport_key", "")

        detailed = self.fetch_event_odds(event_id, sport)
        if isinstance(detailed, dict) and detailed.get("bookmakers"):
            event = detailed

        bookmakers = event.get("bookmakers", [])
        bm = self._pick_niche_bookmaker(bookmakers, event)
        if not bm:
            return None

        match_odds, extended = self._parse_event(event, bm)
        if not (
            match_odds.home_win >= 1.05
            and match_odds.away_win >= 1.05
        ):
            return None

        return OddsFetchResult(
            match_odds=match_odds,
            extended=extended,
            event_id=event_id,
            sport_key=sport,
            home_team=event.get("home_team", home),
            away_team=event.get("away_team", away),
            bookmaker=bm.get("key", ""),
            bookmaker_title=bm.get("title", ""),
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            credits_remaining=self._credits_remaining(),
            region=self.region,
            source="the-odds-api-niche",
            all_bookmakers=[b.get("key", "") for b in bookmakers if isinstance(b, dict)],
        )

    def fetch_for_teams(
        self,
        home: str,
        away: str,
        sport_key: str | None = None,
    ) -> OddsFetchResult | None:
        if not self.is_configured:
            return None

        sport_keys = [sport_key] if sport_key else None
        event, found_sport = self._search_events(home, away, sport_keys)
        if not event:
            return None

        event_id = event.get("id", "")
        sport = found_sport or event.get("sport_key", "")

        detailed = self.fetch_event_odds(event_id, sport)
        if isinstance(detailed, dict) and detailed.get("bookmakers"):
            event = detailed

        bookmakers = event.get("bookmakers", [])
        bm = self._pick_bookmaker(bookmakers)
        if not bm:
            return None

        match_odds, extended = self._parse_event(event, bm)

        required = [match_odds.home_win, match_odds.away_win]
        if not any(x >= 1.05 for x in required):
            return None

        return OddsFetchResult(
            match_odds=match_odds,
            extended=extended,
            event_id=event_id,
            sport_key=sport,
            home_team=event.get("home_team", home),
            away_team=event.get("away_team", away),
            bookmaker=bm.get("key", ""),
            bookmaker_title=bm.get("title", ""),
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            credits_remaining=self._credits_remaining(),
            region=self.region,
            all_bookmakers=[b.get("key", "") for b in bookmakers if isinstance(b, dict)],
        )


def match_odds_to_hint(match_odds: MatchOdds) -> dict:
    """Converte MatchOdds → dict odds_hint (decimal)."""
    return {
        "home_win": match_odds.home_win or 0,
        "draw": match_odds.draw or 0,
        "away_win": match_odds.away_win or 0,
        "over_25": match_odds.over_25 or 0,
        "under_25": match_odds.under_25 or 0,
        "btts_yes": match_odds.btts_yes or 0,
        "btts_no": match_odds.btts_no or 0,
        "double_chance_1x": match_odds.double_chance_1x or 0,
        "double_chance_x2": match_odds.double_chance_x2 or 0,
        "double_chance_12": match_odds.double_chance_12 or 0,
    }