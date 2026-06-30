"""Table Stakes Auditor — classificação e «o que está em jogo» (football-data.org)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from discovery.rate_limiter import MinIntervalLimiter
from discovery.response_cache import get as cache_get
from discovery.response_cache import set as cache_set
from prematch.auditors.types import AuditorVote, TableStakesInsight
from prematch.transfermarkt.match_names import normalize_team, team_key

FD_BASE = "https://api.football-data.org/v4"
_TTL = 43200
_LIMITER = MinIntervalLimiter(6.5)

_LEAGUE_TO_FD: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pat, re.IGNORECASE), code)
    for pat, code in (
        (r"primeira\s*liga|liga\s*portugal|portugal\s*1", "PPL"),
        (r"premier\s*league|england", "PL"),
        (r"la\s*liga|spain|laliga", "PD"),
        (r"serie\s*a|italy", "SA"),
        (r"bundesliga|germany", "BL1"),
        (r"eredivisie|netherlands|holland", "DED"),
        (r"champions\s*league", "CL"),
        (r"europa\s*league", "EL"),
        (r"conference\s*league", "ECL"),
        (r"ligue\s*1|france", "FL1"),
    )
)


def league_to_fd_code(league: str) -> str | None:
    blob = (league or "").strip()
    if not blob:
        return None
    for pattern, code in _LEAGUE_TO_FD:
        if pattern.search(blob):
            return code
    return None


def _fd_request(path: str, api_key: str, params: dict | None = None) -> dict | None:
    if not api_key:
        return None
    q = f"?{urllib.parse.urlencode(params)}" if params else ""
    url = f"{FD_BASE}{path}{q}"
    cached = cache_get("football_data", url, _TTL)
    if cached is not None:
        return cached

    _LIMITER.wait()
    req = urllib.request.Request(
        url,
        headers={"X-Auth-Token": api_key},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None

    if data:
        cache_set("football_data", url, data)
    return data


def _classify_stakes(position: int, total: int, points: int, leader_pts: int) -> tuple[str, str]:
    if total <= 0:
        return "midtable", "Meio da tabela"
    rel = position / total
    gap_leader = leader_pts - points

    if position <= 2 and gap_leader <= 6:
        return "title", f"{position}.º — luta pelo título ({points} pts)"
    if position <= max(4, total // 5):
        return "europe", f"{position}.º — zona europeia ({points} pts)"
    if position >= total - 2 or rel >= 0.82:
        return "relegation", f"{position}.º — pressão de descida ({points} pts)"
    if gap_leader <= 3 and position <= 4:
        return "title", f"{position}.º — a um passo do líder"
    return "midtable", f"{position}.º — meio da tabela ({points} pts)"


def _match_team_row(team_name: str, rows: list[dict]) -> dict | None:
    needle = team_key(team_name)
    for row in rows:
        t = row.get("team") or {}
        for field in ("name", "shortName", "tla"):
            label = str(t.get(field) or "")
            lk = team_key(label)
            if lk == needle or needle in lk or lk in needle:
                return row
    return None


def fetch_standings(
    league: str,
    *,
    api_key: str | None = None,
) -> list[dict] | None:
    code = league_to_fd_code(league)
    if not code:
        return None
    key = api_key or os.getenv("FOOTBALL_DATA_API_KEY", "")
    data = _fd_request(f"/competitions/{code}/standings")
    if not data:
        return None
    standings = (data.get("standings") or [])
    if not standings:
        return None
    table = standings[0].get("table") or []
    return table if table else None


def compute_team_stakes(
    team_name: str,
    table: list[dict],
) -> TableStakesInsight | None:
    row = _match_team_row(team_name, table)
    if not row:
        return None
    position = int(row.get("position") or 0)
    points = int(row.get("points") or 0)
    total = len(table)
    leader_pts = max(int(r.get("points") or 0) for r in table) if table else points
    motivation, label = _classify_stakes(position, total, points, leader_pts)
    return TableStakesInsight(
        team=normalize_team(team_name),
        position=position,
        total_teams=total,
        points=points,
        motivation=motivation,
        label=label,
    )


def _stakes_side(home: TableStakesInsight, away: TableStakesInsight) -> str:
    weight = {"title": 3, "europe": 2, "relegation": 3, "midtable": 0}
    hw = weight.get(home.motivation, 0)
    aw = weight.get(away.motivation, 0)
    if hw > aw + 1:
        return "home"
    if aw > hw + 1:
        return "away"
    if home.motivation == "relegation" and away.motivation == "midtable":
        return "home"
    if away.motivation == "relegation" and home.motivation == "midtable":
        return "away"
    return "neutral"


def audit_table_stakes(
    home: str,
    away: str,
    league: str,
    *,
    api_key: str | None = None,
) -> tuple[AuditorVote | None, dict | None]:
    table = fetch_standings(league, api_key=api_key)
    if not table:
        return None, None

    home_stakes = compute_team_stakes(home, table)
    away_stakes = compute_team_stakes(away, table)
    if not home_stakes or not away_stakes:
        return None, None

    side = _stakes_side(home_stakes, away_stakes)
    if side == "neutral":
        label = f"Contexto: {home_stakes.label} · {away_stakes.label}"
    elif side == "home":
        label = f"Casa com mais em jogo — {home_stakes.label}"
    else:
        label = f"Fora com mais em jogo — {away_stakes.label}"

    vote = AuditorVote(
        auditor_id="table_stakes",
        category="table",
        side=side,
        label=label,
    )
    payload = {
        "home": home_stakes.to_dict(),
        "away": away_stakes.to_dict(),
    }
    return vote, payload