"""Cliente HTTP para transfermarkt-api (felipeall) — JSON sem Cloudflare directo."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_DEFAULT_BASE = "https://transfermarkt-api.fly.dev"
_MIN_INTERVAL_SEC = 1.2
_last_call = 0.0

_YOUTH_MARKERS = (" u19", " u23", " u17", " u20", " u21", " uefa", " youth")
_CLUB_PREFIXES = ("sl ", "fc ", "cs ", "sc ", "gd ", "cd ", "ac ", "as ")


def api_base_url() -> str:
    return (os.getenv("TRANSFERMARKT_API_URL") or _DEFAULT_BASE).rstrip("/")


def is_configured() -> bool:
    return bool(api_base_url())


def _throttle() -> None:
    global _last_call
    elapsed = time.monotonic() - _last_call
    if elapsed < _MIN_INTERVAL_SEC:
        time.sleep(_MIN_INTERVAL_SEC - elapsed)
    _last_call = time.monotonic()


def _get(path: str) -> dict | list | None:
    url = f"{api_base_url()}{path}"
    _throttle()
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "futebol-betting-brain/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def search_clubs(name: str, *, page: int = 1) -> dict | None:
    slug = urllib.parse.quote(name.strip())
    data = _get(f"/clubs/search/{slug}?page_number={page}")
    return data if isinstance(data, dict) else None


def club_profile(club_id: str) -> dict | None:
    data = _get(f"/clubs/{club_id}/profile")
    return data if isinstance(data, dict) else None


def club_players(club_id: str, *, season_id: str | None = None) -> dict | None:
    q = f"?season_id={season_id}" if season_id else ""
    data = _get(f"/clubs/{club_id}/players{q}")
    return data if isinstance(data, dict) else None


def player_injuries(player_id: str, *, page: int = 1) -> dict | None:
    data = _get(f"/players/{player_id}/injuries?page_number={page}")
    return data if isinstance(data, dict) else None


def pick_club_from_search(
    payload: dict | None,
    *,
    query: str = "",
    prefer_country: str = "Portugal",
) -> dict | None:
    results = (payload or {}).get("results") or []
    if not results:
        return None

    def is_senior(row: dict) -> bool:
        name = str(row.get("name") or "").lower().strip()
        if name.endswith(" b") or name.endswith(" ii"):
            return False
        return not any(marker in name for marker in _YOUTH_MARKERS)

    def is_national_team(row: dict) -> bool:
        name = str(row.get("name") or "").strip()
        country = str(row.get("country") or "").strip()
        if not name or not country:
            return False
        nl, cl = name.lower(), country.lower()
        if nl != cl:
            return False
        return not any(nl.startswith(prefix) for prefix in _CLUB_PREFIXES)

    def query_matches_name(query: str, name: str) -> bool:
        q = query.strip().lower()
        n = name.strip().lower()
        if not q or not n:
            return False
        if n == q:
            return True
        tokens = n.split()
        if q in tokens:
            return True
        return any(n.startswith(f"{prefix}{q}") for prefix in _CLUB_PREFIXES)

    q = (query or (payload or {}).get("query") or "").strip().lower()

    def score(row: dict) -> float:
        if not is_senior(row) or is_national_team(row):
            return -1.0
        name = str(row.get("name") or "").lower()
        country = str(row.get("country") or "").lower()
        s = float(int(row.get("marketValue") or 0))
        if prefer_country and prefer_country.lower() in country:
            s += 50_000_000
        if q and query_matches_name(q, name):
            s += 200_000_000
        if q and name.startswith(f"sl {q}"):
            s += 100_000_000
        if q and name.startswith(f"cs {q}"):
            s += 80_000_000
        if q and name.startswith(f"sc {q}"):
            s += 80_000_000
        if q and name.startswith(f"fc {q}"):
            s += 100_000_000
        return s

    ranked = sorted(results, key=score, reverse=True)
    if not ranked or score(ranked[0]) < 0:
        return None
    return ranked[0]


def euros_to_millions(value: int | float | None) -> float:
    if not value:
        return 0.0
    return round(float(value) / 1_000_000, 2)


def parse_player_status(status: str) -> str | None:
    text = (status or "").strip().lower()
    if not text or text == "team captain":
        return None
    if "suspend" in text or "suspension" in text or "ban" in text:
        return "suspended"
    if any(k in text for k in ("injur", "muscle", "rupture", "fracture", "ill", "knock")):
        return "injured"
    if text:
        return "injured"
    return None


def current_injury_details(player_id: str) -> tuple[int, int, str]:
    """Dias parado e jogos falhados da lesão mais recente (se aberta)."""
    payload = player_injuries(player_id)
    injuries = (payload or {}).get("injuries") or []
    if not injuries:
        return 0, 0, "unknown"
    latest = injuries[0]
    days = int(latest.get("days") or 0)
    games = int(latest.get("gamesMissed") or 0)
    injury_type = str(latest.get("injury") or "").lower()
    history = "recurrent" if days >= 60 or games >= 6 else "unknown"
    if days <= 21 and games <= 2:
        history = "crystal"
    return days, games, history