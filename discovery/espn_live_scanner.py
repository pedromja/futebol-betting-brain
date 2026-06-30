"""Jogos ao vivo via ESPN (grátis) — fallback quando API-Football falha ou quota esgotada."""

import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from discovery.espn_odds import extract_match_odds
from discovery.live_fixture_types import LiveFixture
from discovery.web_browser import WebBrowser
from discovery.web_fixture_scanner import ESPN_EXTRA, ESPN_PRIORITY

_ESPN_LIVE_LEAGUES: dict[str, str] = {
    **ESPN_PRIORITY,
    **ESPN_EXTRA,
    "fifa.cwc": "FIFA Club World Cup",
    "concacaf.gold": "CONCACAF Gold Cup",
    "usa.nwsl": "NWSL",
    "mex.1": "Liga MX",
    "arg.1": "Liga Profesional",
    "col.1": "Liga BetPlay",
}

_SCOREBOARD_TTL = 45
_CLOCK_RE = re.compile(r"^(\d+)(?:'|\+)?(?:\+(\d+)'?)?$")


def _parse_display_clock(clock: str) -> tuple[int, int]:
    raw = (clock or "").strip().replace(" ", "")
    if not raw:
        return 0, 0
    m = _CLOCK_RE.match(raw)
    if not m:
        return 0, 0
    minute = int(m.group(1))
    extra = int(m.group(2) or 0)
    return minute, extra


def _espn_status_short(status: dict) -> str:
    stype = status.get("type") or {}
    detail = str(stype.get("detail") or stype.get("shortDetail") or "").upper()
    if detail in {"HT", "1H", "2H", "ET", "BT", "P", "LIVE"}:
        return detail
    name = str(stype.get("name") or "").upper()
    if "HALFTIME" in name or detail == "HT":
        return "HT"
    period = int(status.get("period") or 0)
    if period >= 2:
        return "2H"
    if period == 1:
        return "1H"
    return "LIVE"


class EspnLiveScanner:
    def __init__(self, browser: WebBrowser | None = None):
        self.browser = browser or WebBrowser()

    def _fetch_league(self, code: str, league_name: str) -> list[LiveFixture]:
        self._current_league_code = code
        url = (
            "https://site.api.espn.com/apis/site/v2/sports/soccer/"
            f"{code}/scoreboard"
        )
        data = self.browser.fetch_json(
            url, cache_ns="espn_live_scoreboard", cache_ttl=_SCOREBOARD_TTL
        )
        if not isinstance(data, dict):
            return []

        out: list[LiveFixture] = []
        for event in data.get("events") or []:
            fx = self._event_to_live(event, league_name, code)
            if fx:
                out.append(fx)
        return out

    def _event_to_live(self, event: dict, league_name: str, league_code: str = "") -> LiveFixture | None:
        comp = event.get("competitions", [{}])[0]
        status = comp.get("status") or {}
        stype = status.get("type") or {}
        if stype.get("state") != "in" or stype.get("completed"):
            return None

        home = away = ""
        home_score = away_score = 0
        for c in comp.get("competitors", []):
            side = c.get("homeAway", "")
            team = (c.get("team") or {}).get("displayName", "").strip()
            try:
                score = int(str(c.get("score") or "0"))
            except ValueError:
                score = 0
            if side == "home":
                home, home_score = team, score
            elif side == "away":
                away, away_score = team, score

        if not home or not away:
            title = event.get("name", "")
            if " at " in title:
                away, home = [p.strip() for p in title.split(" at ", 1)]
            elif " vs. " in title.lower():
                parts = re.split(r"\s+vs\.?\s+", title, maxsplit=1, flags=re.I)
                if len(parts) == 2:
                    home, away = parts[0].strip(), parts[1].strip()

        if not home or not away:
            return None

        minute, injury = _parse_display_clock(status.get("displayClock", ""))
        short = _espn_status_short(status)
        if short == "HT" and minute < 45:
            minute = 45

        odds_hint = extract_match_odds(comp) or {}

        return LiveFixture(
            home=home,
            away=away,
            league=league_name,
            stage=str(event.get("season", {}).get("type", "") or ""),
            kickoff=str(event.get("date") or ""),
            home_score=home_score,
            away_score=away_score,
            minute=minute,
            injury_time=injury,
            status_short=short,
            fixture_id=None,
            source="espn",
            odds_hint=odds_hint,
            odds_source="espn-live" if odds_hint else "",
            espn_event_id=str(event.get("id") or ""),
            espn_league_code=league_code,
        )

    def scan(self) -> list[LiveFixture]:
        fixtures: list[LiveFixture] = []
        seen: set[str] = set()

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                pool.submit(self._fetch_league, code, name): code
                for code, name in _ESPN_LIVE_LEAGUES.items()
            }
            for fut in as_completed(futures):
                for fx in fut.result():
                    key = fx.label.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    fixtures.append(fx)

        fixtures.sort(key=lambda f: (f.league, f.minute))
        return fixtures