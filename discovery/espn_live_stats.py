"""Estatísticas live via ESPN summary — fallback gratuito (cantos, remates, cartões, xG)."""

from __future__ import annotations

from datetime import datetime

from discovery.match_stats_types import MatchLiveStatsBundle, TeamLiveStats
from discovery.web_browser import WebBrowser

# Chaves camelCase do campo "name" em boxscore.teams[].statistics
_ESPN_NAME_MAP: dict[str, str] = {
    "possessionpct": "possession_pct",
    "totalshots": "shots_total",
    "shotsontarget": "shots_on",
    "blockedshots": "shots_blocked",
    "woncorners": "corners",
    "foulscommitted": "fouls",
    "offsides": "offsides",
    "yellowcards": "yellow_cards",
    "redcards": "red_cards",
    "saves": "saves",
    "accuratepasses": "passes_accurate",
    "totalpasses": "passes_total",
    "passpct": "passes_pct",
    "expectedgoals": "xg",
}

# Fallback por label normalizado (legado / variações)
_LABEL_ALIASES: dict[str, str] = {
    "corner kicks": "corners",
    "corners": "corners",
    "corner kick": "corners",
    "ball possession": "possession_pct",
    "possession": "possession_pct",
    "shots on goal": "shots_on",
    "on goal": "shots_on",
    "shots": "shots_total",
    "total shots": "shots_total",
    "fouls": "fouls",
    "yellow cards": "yellow_cards",
    "red cards": "red_cards",
    "passes": "passes_total",
    "accurate passes": "passes_accurate",
    "pass completion": "passes_pct",
    "expected goals": "xg",
}

_PERCENT_FIELDS = frozenset({"possession_pct", "passes_pct"})


def _norm_key(value: str) -> str:
    return (value or "").strip().lower().replace("%", "").replace("_", " ")


def _norm_name(value: str) -> str:
    return (value or "").strip().lower().replace("_", "").replace(" ", "").replace("%", "")


def _parse_stat_value(raw, *, percent: bool = False) -> int | float | None:
    if raw is None:
        return None
    text = str(raw).strip().replace("%", "")
    if not text or text == "-":
        return None
    try:
        num = float(text)
    except (TypeError, ValueError):
        return None
    if percent and 0 < num <= 1:
        num *= 100
    if percent or num == int(num):
        return int(round(num))
    return round(num, 2)


def _resolve_field(item: dict) -> tuple[str | None, bool]:
    name_key = _norm_name(str(item.get("name") or ""))
    if name_key in _ESPN_NAME_MAP:
        field = _ESPN_NAME_MAP[name_key]
        return field, field in _PERCENT_FIELDS

    label_key = _norm_key(str(item.get("label") or item.get("displayName") or ""))
    field = _LABEL_ALIASES.get(label_key)
    if field:
        return field, field in _PERCENT_FIELDS

    for alias, mapped in _LABEL_ALIASES.items():
        if alias in label_key or label_key in alias:
            return mapped, mapped in _PERCENT_FIELDS
    return None, False


def _stat_map(items: list) -> dict[str, int | float]:
    out: dict[str, int | float] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        field, is_pct = _resolve_field(item)
        if not field:
            continue
        val = _parse_stat_value(item.get("displayValue") or item.get("value"), percent=is_pct)
        if val is not None:
            out[field] = val
    return out


def _apply_stats(stats: TeamLiveStats, values: dict[str, int | float]) -> TeamLiveStats:
    for field, val in values.items():
        setattr(stats, field, val)
    return stats


def _team_from_box_row(row: dict) -> tuple[str, str, TeamLiveStats]:
    team_obj = row.get("team") or {}
    team_name = team_obj.get("displayName") or team_obj.get("name") or ""
    team_id = str(team_obj.get("id") or "")
    home_away = str(row.get("homeAway") or "")
    stats = _stat_map(row.get("statistics") or [])
    ts = TeamLiveStats(
        team=team_name or ("Casa" if home_away == "home" else "Fora"),
        xg_source="none",
    )
    _apply_stats(ts, stats)
    return team_name, team_id, ts


def _has_any_stat(ts: TeamLiveStats) -> bool:
    return any(
        getattr(ts, field) is not None
        for field in (
            "possession_pct",
            "shots_total",
            "shots_on",
            "shots_blocked",
            "corners",
            "fouls",
            "offsides",
            "yellow_cards",
            "red_cards",
            "saves",
            "passes_total",
            "passes_accurate",
            "passes_pct",
            "xg",
        )
    )


def _stat_value(statistics: list, name: str) -> float | None:
    for item in statistics or []:
        if not isinstance(item, dict):
            continue
        if _norm_name(str(item.get("name") or "")) != _norm_name(name):
            continue
        val = _parse_stat_value(item.get("value") if item.get("value") is not None else item.get("displayValue"))
        if val is not None:
            return float(val)
    return None


def _xg_from_goalkeeper_leaders(payload: dict, home_id: str, away_id: str) -> tuple[float | None, float | None]:
    """xG de equipa = xGC do guarda-redes adversário (secção leaders)."""
    xgc_by_team: dict[str, float] = {}
    for block in payload.get("leaders") or []:
        if not isinstance(block, dict):
            continue
        team_id = str((block.get("team") or {}).get("id") or "")
        if not team_id:
            continue
        for category in block.get("leaders") or []:
            if str(category.get("name") or "").lower() != "saves":
                continue
            for leader in category.get("leaders") or []:
                xgc = _stat_value(leader.get("statistics") or [], "expectedGoalsConceded")
                if xgc is not None:
                    xgc_by_team[team_id] = xgc
                    break

    home_xg = xgc_by_team.get(away_id)
    away_xg = xgc_by_team.get(home_id)
    return home_xg, away_xg


def _assign_home_away(
    teams: list,
    *,
    home_name: str,
    away_name: str,
) -> tuple[TeamLiveStats | None, TeamLiveStats | None, str, str]:
    home_stats = away_stats = None
    home_id = away_id = ""
    for row in teams:
        name, tid, ts = _team_from_box_row(row)
        side = str(row.get("homeAway") or "").lower()
        lname = (name or "").lower()
        if side == "home" or (home_name and home_name.lower() in lname):
            home_stats, home_id = ts, tid
        elif side == "away" or (away_name and away_name.lower() in lname):
            away_stats, away_id = ts, tid

    if not home_stats or not away_stats:
        t0_name, t0_id, t0 = _team_from_box_row(teams[0])
        t1_name, t1_id, t1 = _team_from_box_row(teams[1])
        home_stats, away_stats = t0, t1
        home_id, away_id = t0_id, t1_id
        if home_name and away_name:
            if away_name.lower() in t0_name.lower():
                home_stats, away_stats = t1, t0
                home_id, away_id = t1_id, t0_id
            elif away_name.lower() in t1_name.lower():
                home_stats, away_stats = t0, t1
                home_id, away_id = t0_id, t1_id

    return home_stats, away_stats, home_id, away_id


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

    home_stats, away_stats, home_id, away_id = _assign_home_away(
        teams, home_name=home_name, away_name=away_name
    )
    if not home_stats or not away_stats:
        return None

    if not _has_any_stat(home_stats) and not _has_any_stat(away_stats):
        return None

    home_xg, away_xg = _xg_from_goalkeeper_leaders(payload, home_id, away_id)
    if home_xg is not None:
        home_stats.xg = home_xg
        home_stats.xg_source = "espn"
    if away_xg is not None:
        away_stats.xg = away_xg
        away_stats.xg_source = "espn"

    fid = fixture_id or 0
    try:
        fid = int((payload.get("header") or {}).get("id") or fid)
    except (TypeError, ValueError):
        pass

    xg_source = "espn" if home_stats.xg is not None or away_stats.xg is not None else "none"
    return MatchLiveStatsBundle(
        fixture_id=fid,
        home=home_stats,
        away=away_stats,
        fetched_at=datetime.now().isoformat(timespec="seconds"),
        xg_source=xg_source,
    )


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