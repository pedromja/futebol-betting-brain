"""
Estimativa interna de xG quando o provedor não devolve expected goals.

Heurística simples (não substitui modelos Opta/StatsBomb):
  xG ≈ 0.10 × remates à baliza + 0.05 × remates fora + 0.03 × bloqueados
  + pequeno bónus de cantos (bolas paradas).

Usar apenas para UI e sinais fracos no motor — marcar sempre como "estimated".
"""

from __future__ import annotations

from discovery.match_stats_types import MatchLiveStatsBundle, TeamLiveStats

XG_PER_SHOT_ON = 0.10
XG_PER_SHOT_OFF = 0.05
XG_PER_SHOT_BLOCKED = 0.03
XG_PER_CORNER_CAP = 12
XG_PER_CORNER = 0.02

# Proporções típicas quando só existe "Total Shots"
_DEFAULT_ON_SHARE = 0.35
_DEFAULT_OFF_SHARE = 0.45


def _shot_components(stats: TeamLiveStats) -> tuple[int, int, int]:
    on = stats.shots_on or 0
    off = stats.shots_off or 0
    blocked = stats.shots_blocked or 0
    total = stats.shots_total

    if on == 0 and off == 0 and blocked == 0 and total:
        on = max(0, round(total * _DEFAULT_ON_SHARE))
        off = max(0, round(total * _DEFAULT_OFF_SHARE))
        blocked = max(0, total - on - off)

    return on, off, blocked


def estimate_team_xg(stats: TeamLiveStats) -> float | None:
    """Devolve xG estimado ou None se não há dados de remates."""
    on, off, blocked = _shot_components(stats)
    if on == 0 and off == 0 and blocked == 0:
        return None

    xg = (
        XG_PER_SHOT_ON * on
        + XG_PER_SHOT_OFF * off
        + XG_PER_SHOT_BLOCKED * blocked
    )
    corners = stats.corners or 0
    if corners > 0:
        xg += XG_PER_CORNER * min(corners, XG_PER_CORNER_CAP)

    return round(max(0.0, xg), 2)


def enrich_bundle_xg(bundle: MatchLiveStatsBundle) -> MatchLiveStatsBundle:
    """
    Preenche xG em falta com estimativa interna.
    Mantém valores da API quando já existem.
    """
    for team_stats in (bundle.home, bundle.away):
        if team_stats.xg is not None:
            team_stats.xg_source = "api"
            continue
        estimated = estimate_team_xg(team_stats)
        if estimated is not None:
            team_stats.xg = estimated
            team_stats.xg_source = "estimated"

    sources = {bundle.home.xg_source, bundle.away.xg_source}
    if "api" in sources and "estimated" in sources:
        bundle.xg_source = "mixed"
    elif sources == {"api"}:
        bundle.xg_source = "api"
    elif "estimated" in sources:
        bundle.xg_source = "estimated"
    else:
        bundle.xg_source = "none"

    return bundle


def inspect_raw_xg_fields(statistics: list) -> dict:
    """Extrai campos relacionados com xG da resposta bruta da API-Football."""
    hits: list[dict] = []
    for item in statistics or []:
        name = (item.get("type") or "").strip()
        lower = name.lower()
        if "expected" in lower or lower in ("xg", "xgot"):
            hits.append({"type": name, "value": item.get("value")})
    return {"xg_fields": hits, "has_api_xg": bool(hits)}