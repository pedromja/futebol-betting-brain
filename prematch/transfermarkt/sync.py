"""Sincroniza cache JSONL a partir da transfermarkt-api."""

from __future__ import annotations

from datetime import datetime, timezone

from config.data_paths import TM_INJURIES, TM_SQUADS, ensure_data_dir
from prematch.transfermarkt import api_client
from prematch.transfermarkt.cache import _read_jsonl, _write_jsonl, append_jsonl
from prematch.transfermarkt.match_names import normalize_team, resolve_team_name


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _upsert_team_row(path, team: str, row: dict) -> None:
    rows = _read_jsonl(path)
    out: list[dict] = []
    replaced = False
    for existing in rows:
        if str(existing.get("team") or "").strip().lower() == team.lower():
            if not replaced:
                out.append(row)
                replaced = True
        else:
            out.append(existing)
    if not replaced:
        out.append(row)
    _write_jsonl(path, out)


def _replacement_value(players: list[dict], absent: dict, position: str) -> float:
    pos = (position or "").lower()
    candidates = [
        api_client.euros_to_millions(p.get("marketValue"))
        for p in players
        if p.get("name") != absent.get("name")
        and (not pos or pos.split("-")[0] in str(p.get("position") or "").lower())
    ]
    candidates = [c for c in candidates if c > 0]
    if not candidates:
        candidates = [
            api_client.euros_to_millions(p.get("marketValue"))
            for p in players
            if p.get("name") != absent.get("name")
        ]
        candidates = [c for c in candidates if c > 0]
    return max(candidates) if candidates else 0.0


def sync_team_from_api(
    team_name: str,
    *,
    prefer_country: str = "Portugal",
    fetch_injury_history: bool = True,
    national: bool = False,
) -> dict:
    """
    Pesquisa clube na API, actualiza squads.jsonl + injuries.jsonl.
    Devolve resumo {ok, team, club_id, market_value_m, absences, error}.
    """
    ensure_data_dir()
    label = normalize_team(team_name)
    if not label:
        return {"ok": False, "team": team_name, "error": "nome vazio"}

    if not api_client.is_configured():
        return {"ok": False, "team": label, "error": "TRANSFERMARKT_API_URL não configurada"}

    search = api_client.search_clubs(label)
    if national:
        club = api_client.pick_national_team_from_search(search, query=label)
    else:
        club = api_client.pick_club_from_search(
            search, query=label, prefer_country=prefer_country
        )
        if not club:
            club = api_client.pick_national_team_from_search(search, query=label)
    if not club:
        return {"ok": False, "team": label, "error": "equipa não encontrada na API"}

    club_id = str(club.get("id") or "")
    players_payload = api_client.club_players(club_id)
    players = (players_payload or {}).get("players") or []
    profile = api_client.club_profile(club_id)

    market_eur = int(club.get("marketValue") or 0)
    if profile and profile.get("currentMarketValue"):
        market_eur = int(profile["currentMarketValue"])
    market_m = api_client.euros_to_millions(market_eur)

    canonical = resolve_team_name(str(club.get("name") or label), {label})
    player_rows = []
    for p in players:
        player_rows.append(
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "position": p.get("position"),
                "market_value_m": api_client.euros_to_millions(p.get("marketValue")),
                "status": p.get("status") or "",
            }
        )

    squad_row = {
        "team": canonical,
        "market_value_m": market_m,
        "tm_club_id": club_id,
        "tm_url": club.get("url"),
        "country": club.get("country"),
        "players": player_rows,
        "updated_at": _now(),
        "source": "transfermarkt-api",
    }
    _upsert_team_row(TM_SQUADS, canonical, squad_row)

    absences: list[dict] = []
    for p in players:
        status_raw = str(p.get("status") or "")
        kind = api_client.parse_player_status(status_raw)
        if not kind:
            continue
        pid = str(p.get("id") or "")
        days, games, history = (0, 0, "unknown")
        if fetch_injury_history and pid and kind == "injured":
            days, games, history = api_client.current_injury_details(pid)
        absences.append(
            {
                "name": p.get("name"),
                "status": kind,
                "days_out": days,
                "games_missed": games,
                "market_value_m": api_client.euros_to_millions(p.get("marketValue")),
                "replacement_value_m": _replacement_value(players, p, str(p.get("position") or "")),
                "injury_history": history,
                "expected_return": status_raw,
                "tm_player_id": pid,
            }
        )

    injury_row = {
        "team": canonical,
        "absences": absences,
        "updated_at": _now(),
        "source": "transfermarkt-api",
    }
    _upsert_team_row(TM_INJURIES, canonical, injury_row)

    return {
        "ok": True,
        "team": canonical,
        "club_id": club_id,
        "market_value_m": market_m,
        "players": len(players),
        "absences": len(absences),
        "api_base": api_client.api_base_url(),
    }


def sync_teams_from_api(
    teams: list[str],
    *,
    prefer_country: str = "Portugal",
) -> dict:
    results = []
    for name in teams:
        name = (name or "").strip()
        if not name:
            continue
        results.append(sync_team_from_api(name, prefer_country=prefer_country))
    ok = sum(1 for r in results if r.get("ok"))
    return {
        "synced": ok,
        "total": len(results),
        "results": results,
        "api_base": api_client.api_base_url(),
    }


def log_sync_event(summary: dict) -> None:
    from config.data_paths import TRANSFERMARKT_DIR

    path = TRANSFERMARKT_DIR / "sync_log.jsonl"
    append_jsonl(
        path,
        {"at": _now(), **summary},
    )