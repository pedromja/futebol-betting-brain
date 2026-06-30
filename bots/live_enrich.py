"""Anexa estatísticas live (xG, cartões) aos jogos para avaliação de bots."""

from __future__ import annotations

from typing import Any

from discovery.match_stats_types import MatchLiveStatsBundle

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
        "home_yellow_cards",
        "away_yellow_cards",
        "total_yellow_cards",
        "home_red_cards",
        "away_red_cards",
        "total_red_cards",
        "total_cards",
    }
)


def bot_conditions_need_live_stats(conditions: list[dict]) -> bool:
    for cond in conditions or []:
        if str(cond.get("field") or "") in LIVE_STATS_FIELDS:
            return True
    return False


def any_bot_needs_live_stats(bots) -> bool:
    for bot in bots:
        if bot.mode != "live" or not bot.active:
            continue
        if bot_conditions_need_live_stats(bot.conditions):
            return True
    return False


def attach_live_stats_fields(match: dict, bundle: MatchLiveStatsBundle) -> dict:
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
    out["home_xg"] = home_xg
    out["away_xg"] = away_xg
    out["total_xg"] = total_xg
    out["xg_diff"] = xg_diff
    out["home_possession_pct"] = h.possession_pct
    out["away_possession_pct"] = a.possession_pct
    out["home_corners"] = h.corners
    out["away_corners"] = a.corners
    if h.corners is not None and a.corners is not None:
        out["total_corners"] = h.corners + a.corners
    out["home_yellow_cards"] = h.yellow_cards
    out["away_yellow_cards"] = a.yellow_cards
    out["total_yellow_cards"] = hy + ay
    out["home_red_cards"] = h.red_cards
    out["away_red_cards"] = a.red_cards
    out["total_red_cards"] = hr + ar
    out["total_cards"] = hy + ay + hr + ar
    return out


def enrich_live_ranked_for_bots(
    ranked: list[dict],
    *,
    bots=None,
    max_fetch: int = 12,
) -> list[dict]:
    """Busca stats API-Football só quando bots activos precisam de xG/cartões."""
    from bots.store import list_bots
    from discovery.api_football_client import ApiFootballClient
    from discovery.match_stats import fetch_match_live_stats

    active = bots if bots is not None else list_bots(active_only=True)
    if not any_bot_needs_live_stats(active):
        return ranked

    client = ApiFootballClient()
    if not client.is_configured:
        return ranked

    out: list[dict] = []
    fetched = 0
    cache: dict[int, dict] = {}

    for match in ranked:
        m = dict(match)
        fid = m.get("fixture_id")
        if not fid:
            out.append(m)
            continue
        try:
            fid_int = int(fid)
        except (TypeError, ValueError):
            out.append(m)
            continue

        if fid_int in cache:
            out.append({**m, **cache[fid_int]})
            continue

        if fetched >= max_fetch:
            out.append(m)
            continue

        bundle = fetch_match_live_stats(client, fid_int)
        fetched += 1
        if not bundle:
            out.append(m)
            continue

        enriched = attach_live_stats_fields(m, bundle)
        cache[fid_int] = {k: enriched[k] for k in LIVE_STATS_FIELDS if k in enriched}
        cache[fid_int]["live_stats"] = enriched.get("live_stats")
        out.append(enriched)

    return out