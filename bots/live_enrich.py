"""Anexa estatísticas live (xG, cartões, cantos, remates, favorito) aos jogos para bots."""

from __future__ import annotations

from typing import Any

from bots.live_context import FAVORITE_FIELDS, attach_favorite_fields
from discovery.match_stats_types import MatchLiveStatsBundle, TeamLiveStats

LIVE_STATS_FIELDS = frozenset(
    {
        "home_xg",
        "away_xg",
        "total_xg",
        "xg_diff",
        "home_possession_pct",
        "away_possession_pct",
        "home_corners",
        "away_corners",
        "total_corners",
        "home_shots_total",
        "away_shots_total",
        "total_shots",
        "home_shots_on",
        "away_shots_on",
        "total_shots_on",
        "home_fouls",
        "away_fouls",
        "total_fouls",
        "home_saves",
        "away_saves",
        "total_saves",
        "home_passes_pct",
        "away_passes_pct",
        "home_yellow_cards",
        "away_yellow_cards",
        "total_yellow_cards",
        "home_red_cards",
        "away_red_cards",
        "total_red_cards",
        "total_cards",
        "live_stats_source",
    }
)

ENRICH_FIELDS = LIVE_STATS_FIELDS | FAVORITE_FIELDS


def _conditions_list(bot) -> list[dict]:
    conds = list(bot.conditions or [])
    for group in bot.condition_groups or []:
        conds.extend(group.get("conditions") or [])
    return conds


def bot_conditions_need_field(conditions: list[dict], fields: frozenset[str]) -> bool:
    for cond in conditions or []:
        if str(cond.get("field") or "") in fields:
            return True
    return False


def bot_conditions_need_live_stats(conditions: list[dict]) -> bool:
    return bot_conditions_need_field(conditions, LIVE_STATS_FIELDS)


def bot_conditions_need_favorite(conditions: list[dict]) -> bool:
    return bot_conditions_need_field(conditions, FAVORITE_FIELDS)


def any_bot_needs_live_enrich(bots) -> bool:
    for bot in bots:
        if bot.mode != "live" or not bot.active:
            continue
        conds = _conditions_list(bot)
        if bot_conditions_need_live_stats(conds) or bot_conditions_need_favorite(conds):
            return True
    return False


def _sum_pair(a: int | None, b: int | None) -> int | None:
    if a is not None and b is not None:
        return a + b
    return a if a is not None else b


def _attach_team_totals(
    out: dict,
    field: str,
    home_val: Any,
    away_val: Any,
    *,
    total_field: str | None = None,
) -> None:
    out[f"home_{field}"] = home_val
    out[f"away_{field}"] = away_val
    total = _sum_pair(home_val, away_val)
    if total is not None:
        out[total_field or f"total_{field}"] = total


def attach_live_stats_fields(match: dict, bundle: MatchLiveStatsBundle, *, source: str = "api-football") -> dict:
    h = bundle.home
    a = bundle.away
    home_xg = h.xg
    away_xg = a.xg
    total_xg = None
    xg_diff = None
    if home_xg is not None and away_xg is not None:
        total_xg = round(home_xg + away_xg, 2)
        xg_diff = round(home_xg - away_xg, 2)

    hy = h.yellow_cards or 0
    ay = a.yellow_cards or 0
    hr = h.red_cards or 0
    ar = a.red_cards or 0

    out = {**match}
    out["live_stats"] = bundle.to_dict()
    out["live_stats_source"] = source
    out["home_xg"] = home_xg
    out["away_xg"] = away_xg
    out["total_xg"] = total_xg
    out["xg_diff"] = xg_diff
    out["home_possession_pct"] = h.possession_pct
    out["away_possession_pct"] = a.possession_pct

    _attach_team_totals(out, "corners", h.corners, a.corners)
    _attach_team_totals(out, "shots_total", h.shots_total, a.shots_total, total_field="total_shots")
    _attach_team_totals(out, "shots_on", h.shots_on, a.shots_on, total_field="total_shots_on")
    _attach_team_totals(out, "fouls", h.fouls, a.fouls)
    _attach_team_totals(out, "saves", h.saves, a.saves)

    out["home_passes_pct"] = h.passes_pct
    out["away_passes_pct"] = a.passes_pct
    out["home_yellow_cards"] = h.yellow_cards
    out["away_yellow_cards"] = a.yellow_cards
    out["total_yellow_cards"] = hy + ay
    out["home_red_cards"] = h.red_cards
    out["away_red_cards"] = a.red_cards
    out["total_red_cards"] = hr + ar
    out["total_cards"] = hy + ay + hr + ar
    return out


def _fetch_stats_bundle(match: dict, client) -> tuple[MatchLiveStatsBundle | None, str]:
    from discovery.match_stats import fetch_match_live_stats

    fid = match.get("fixture_id")
    if fid and client and client.is_configured and not client.quota_exhausted:
        try:
            bundle = fetch_match_live_stats(client, int(fid))
            if bundle:
                return bundle, "api-football"
        except (TypeError, ValueError):
            pass

    league = str(match.get("espn_league_code") or "")
    event_id = str(match.get("espn_event_id") or "")
    if league and event_id:
        from discovery.espn_live_stats import fetch_espn_live_stats

        bundle = fetch_espn_live_stats(
            league,
            event_id,
            home_name=str(match.get("home") or ""),
            away_name=str(match.get("away") or ""),
        )
        if bundle:
            return bundle, "espn"

    return None, "none"


def enrich_live_ranked_for_bots(
    ranked: list[dict],
    *,
    bots=None,
    max_fetch: int = 12,
) -> list[dict]:
    """Enriquece ranked live: favorito (odds ESPN/API) + stats API-Football ou ESPN."""
    from bots.store import list_bots
    from discovery.api_football_client import ApiFootballClient

    active = bots if bots is not None else list_bots(active_only=True)
    if not active or not ranked:
        return ranked

    conds_all: list[dict] = []
    for bot in active:
        if bot.mode != "live" or not bot.active:
            continue
        conds_all.extend(_conditions_list(bot))

    need_stats = bot_conditions_need_live_stats(conds_all)
    need_fav = bot_conditions_need_favorite(conds_all) or bool(conds_all)

    client = ApiFootballClient() if need_stats else None
    out: list[dict] = []
    fetched = 0
    cache: dict[str, dict] = {}

    for match in ranked:
        m = attach_favorite_fields(dict(match))
        cache_key = (
            f"{m.get('fixture_id')}|{m.get('espn_event_id')}|{m.get('home')}|{m.get('away')}"
        )

        if need_stats:
            if cache_key in cache:
                m = {**m, **cache[cache_key]}
            elif fetched < max_fetch:
                bundle, source = _fetch_stats_bundle(m, client)
                fetched += 1
                if bundle:
                    m = attach_live_stats_fields(m, bundle, source=source)
                    cache[cache_key] = {k: m[k] for k in ENRICH_FIELDS if k in m}
                    if m.get("live_stats"):
                        cache[cache_key]["live_stats"] = m["live_stats"]

        out.append(m)

    return out