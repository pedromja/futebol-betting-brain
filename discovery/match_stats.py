"""Fetch e parse de estatísticas ao vivo (API-Football)."""

from datetime import datetime

from discovery.api_football_client import ApiFootballClient
from discovery.match_stats_types import MatchEvent, MatchLiveStatsBundle, TeamLiveStats
from discovery.xg_estimate import enrich_bundle_xg, inspect_raw_xg_fields

_STAT_KEYS = {
    "ball possession": "possession_pct",
    "total shots": "shots_total",
    "shots on goal": "shots_on",
    "shots off goal": "shots_off",
    "blocked shots": "shots_blocked",
    "corner kicks": "corners",
    "fouls": "fouls",
    "offsides": "offsides",
    "yellow cards": "yellow_cards",
    "red cards": "red_cards",
    "goalkeeper saves": "saves",
    "total passes": "passes_total",
    "passes accurate": "passes_accurate",
    "passes %": "passes_pct",
    "expected goals": "xg",
    "expected_goals": "xg",
}

def _parse_stat_value(raw) -> int | float | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text == "-":
        return None
    if text.endswith("%"):
        try:
            return int(float(text.rstrip("%")))
        except ValueError:
            return None
    try:
        num = float(text)
        return int(num) if num == int(num) else round(num, 2)
    except ValueError:
        return None


def _team_stats_from_api(team_name: str, items: list) -> TeamLiveStats:
    stats = TeamLiveStats(team=team_name)
    for item in items or []:
        key = (item.get("type") or "").strip().lower()
        field = _STAT_KEYS.get(key)
        if not field:
            continue
        value = _parse_stat_value(item.get("value"))
        if value is not None:
            setattr(stats, field, value)
    return stats


def parse_statistics_response(
    fixture_id: int, payload: dict | None
) -> MatchLiveStatsBundle | None:
    rows = (payload or {}).get("response") or []
    if len(rows) < 2:
        return None

    home_row = rows[0]
    away_row = rows[1]
    home_name = (home_row.get("team") or {}).get("name", "")
    away_name = (away_row.get("team") or {}).get("name", "")

    return MatchLiveStatsBundle(
        fixture_id=fixture_id,
        home=_team_stats_from_api(home_name, home_row.get("statistics")),
        away=_team_stats_from_api(away_name, away_row.get("statistics")),
        fetched_at=datetime.now().isoformat(timespec="seconds"),
    )


def parse_events_response(payload: dict | None) -> list[MatchEvent]:
    events: list[MatchEvent] = []
    for item in (payload or {}).get("response") or []:
        time_info = item.get("time") or {}
        minute = int(time_info.get("elapsed") or 0)
        extra_raw = time_info.get("extra")
        extra = int(extra_raw) if extra_raw is not None else None
        team = (item.get("team") or {}).get("name", "")
        player = (item.get("player") or {}).get("name", "")
        assist = (item.get("assist") or {}).get("name", "")
        events.append(
            MatchEvent(
                minute=minute,
                extra=extra,
                team=team,
                player=player,
                assist=assist,
                type=str(item.get("type") or ""),
                detail=str(item.get("detail") or ""),
            )
        )
    events.sort(key=lambda e: (e.minute, e.extra or 0))
    return events


def fetch_match_live_stats(
    client: ApiFootballClient,
    fixture_id: int,
    *,
    include_events: bool = False,
) -> MatchLiveStatsBundle | None:
    """
    Estatísticas ao vivo (1 pedido API-Football).
    Eventos são opcionais (+1 pedido) — só pedir quando o utilizador abre o detalhe.
    """
    stats_data = client.fetch_fixture_statistics(fixture_id)
    bundle = parse_statistics_response(fixture_id, stats_data)
    if not bundle:
        return None
    if include_events:
        events_data = client.fetch_fixture_events(fixture_id)
        bundle.events = parse_events_response(events_data)
    return enrich_bundle_xg(bundle)


def inspect_fixture_xg_coverage(
    client: ApiFootballClient, fixture_id: int
) -> dict | None:
    """Fase 0 — analisa se a API devolve xG ou só remates (1 pedido)."""
    raw = client.fetch_fixture_statistics(fixture_id)
    rows = (raw or {}).get("response") or []
    if len(rows) < 2:
        return None

    home_row, away_row = rows[0], rows[1]
    home_inspect = inspect_raw_xg_fields(home_row.get("statistics"))
    away_inspect = inspect_raw_xg_fields(away_row.get("statistics"))

    bundle = parse_statistics_response(fixture_id, raw)
    if bundle:
        enrich_bundle_xg(bundle)

    return {
        "fixture_id": fixture_id,
        "home_team": (home_row.get("team") or {}).get("name", ""),
        "away_team": (away_row.get("team") or {}).get("name", ""),
        "home_api_xg": home_inspect["has_api_xg"],
        "away_api_xg": away_inspect["has_api_xg"],
        "home_xg_fields": home_inspect["xg_fields"],
        "away_xg_fields": away_inspect["xg_fields"],
        "home_xg_final": bundle.home.xg if bundle else None,
        "away_xg_final": bundle.away.xg if bundle else None,
        "home_xg_source": bundle.home.xg_source if bundle else "none",
        "away_xg_source": bundle.away.xg_source if bundle else "none",
        "bundle_xg_source": bundle.xg_source if bundle else "none",
        "home_shots_on": bundle.home.shots_on if bundle else None,
        "away_shots_on": bundle.away.shots_on if bundle else None,
    }