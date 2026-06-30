"""Estatísticas live via ESPN summary — fallback gratuito (cantos, remates)."""

from __future__ import annotations

from datetime import datetime

from discovery.match_stats_types import MatchLiveStatsBundle, TeamLiveStats
from discovery.web_browser import WebBrowser

_CORNER_KEYS = frozenset(
    {"corners", "corner kicks", "corner_kicks", "cornerkicks", "corner kick"}
)
_SHOTS_ON_KEYS = frozenset({"shots on target", "shots on goal", "shots_on_goal"})
_SHOTS_TOTAL_KEYS = frozenset({"total shots", "shots", "shots total"})
_POSSESSION_KEYS = frozenset({"possession", "ball possession", "possession %"})


def _norm_key(value: str) -> str:
    return (value or "").strip().lower().replace("%", "").replace("_", " ")


def _parse_stat_value(raw) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip().replace("%", "")
    if not text or text == "-":
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _stat_map(items: list) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = _norm_key(str(item.get("name") or item.get("label") or item.get("type") or ""))
        val = _parse_stat_value(item.get("displayValue") or item.get("value"))
        if name and val is not None:
            out[name] = val
    return out


def _pick(stats: dict[str, int], keys: frozenset[str]) -> int | None:
    for k, v in stats.items():
        if k in keys or any(alias in k for alias in keys):
            return v
    return None


def _team_from_box_row(row: dict) -> tuple[str, TeamLiveStats]:
    team_name = (row.get("team") or {}).get("displayName") or (row.get("team") or {}).get("name") or ""
    home_away = str(row.get("homeAway") or "")
    stats = _stat_map(row.get("statistics") or [])
    return team_name, TeamLiveStats(
        team=team_name or ("Casa" if home_away == "home" else "Fora"),
        corners=_pick(stats, _CORNER_KEYS),
        shots_on=_pick(stats, _SHOTS_ON_KEYS),
        shots_total=_pick(stats, _SHOTS_TOTAL_KEYS),
        possession_pct=_pick(stats, _POSSESSION_KEYS),
        xg_source="none",
    )


def parse_espn_summary(
    payload: dict | None,
    *,
    fixture_id: int | None = None,
    home_name: str = "",
    away_name: str = "",
) -> MatchLiveStatsBundle | None:
    if not payload:
        return None

    teams = (payload.get("boxscore") or {}).get("teams") or []
    if len(teams) < 2:
        competitors = (
            ((payload.get("header") or {}).get("competitions") or [{}])[0].get("competitors") or []
        )
        if len(competitors) >= 2:
            teams = competitors

    if len(teams) < 2:
        return None

    home_stats = away_stats = None
    for row in teams:
        _, ts = _team_from_box_row(row)
        side = str(row.get("homeAway") or "").lower()
        name = (ts.team or "").lower()
        if side == "home" or (home_name and home_name.lower() in name):
            home_stats = ts
        elif side == "away" or (away_name and away_name.lower() in name):
            away_stats = ts

    if not home_stats or not away_stats:
        t0_name, t0 = _team_from_box_row(teams[0])
        t1_name, t1 = _team_from_box_row(teams[1])
        home_stats = t0
        away_stats = t1
        if home_name and away_name:
            if away_name.lower() in t0_name.lower():
                home_stats, away_stats = t1, t0
            elif away_name.lower() in t1_name.lower():
                home_stats, away_stats = t0, t1

    if home_stats.corners is None and away_stats.corners is None:
        return None

    fid = fixture_id or 0
    try:
        fid = int((payload.get("header") or {}).get("id") or fid)
    except (TypeError, ValueError):
        pass

    bundle = MatchLiveStatsBundle(
        fixture_id=fid,
        home=home_stats,
        away=away_stats,
        fetched_at=datetime.now().isoformat(timespec="seconds"),
        xg_source="none",
    )
    bundle.xg_source = "espn"
    return bundle


def fetch_espn_live_stats(
    league_code: str,
    event_id: str,
    *,
    browser: WebBrowser | None = None,
    home_name: str = "",
    away_name: str = "",
) -> MatchLiveStatsBundle | None:
    if not league_code or not event_id:
        return None
    br = browser or WebBrowser()
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/soccer/"
        f"{league_code}/summary?event={event_id}"
    )
    data = br.fetch_json(url, cache_ns="espn_live_summary", cache_ttl=45)
    try:
        fid = int(event_id)
    except (TypeError, ValueError):
        fid = None
    return parse_espn_summary(data, fixture_id=fid, home_name=home_name, away_name=away_name)