"""Cliente ClubElo — ratings objectivos sem chave API."""

from __future__ import annotations

import csv
import io
import time
import urllib.error
import urllib.parse
import urllib.request

from discovery.rate_limiter import MinIntervalLimiter
from discovery.response_cache import get as cache_get
from discovery.response_cache import set as cache_set
from prematch.auditors.types import ClubEloInsight
from prematch.transfermarkt.match_names import normalize_team

_BASE = "http://api.clubelo.com"
_TTL = 86400
_LIMITER = MinIntervalLimiter(0.8)

# Nomes aceites pela API ClubElo (curtos)
_CLUBELO_NAMES: dict[str, str] = {
    "benfica": "Benfica",
    "sl benfica": "Benfica",
    "fc porto": "Porto",
    "porto": "Porto",
    "sporting": "Sporting",
    "sporting cp": "Sporting",
    "sc braga": "Braga",
    "braga": "Braga",
    "maritimo": "Maritimo",
    "marítimo": "Maritimo",
    "cs maritimo": "Maritimo",
    "cs marítimo": "Maritimo",
    "estoril": "Estoril",
    "gil vicente": "Gil Vicente",
    "rio ave": "Rio Ave",
    "famalicao": "Famalicao",
    "boavista": "Boavista",
    "arouca": "Arouca",
    "moreirense": "Moreirense",
    "casa pia": "Casa Pia",
    "vizela": "Vizela",
    "farense": "Farense",
    "nacional": "Nacional",
    "chaves": "Chaves",
    "portimonense": "Portimonense",
    "santa clara": "Santa Clara",
    "tondela": "Tondela",
    "avs": "AVS",
    "alverca": "Alverca",
}


def clubelo_query_name(team_name: str) -> str:
    key = normalize_team(team_name).lower()
    if key in _CLUBELO_NAMES:
        return _CLUBELO_NAMES[key]
    # Fallback: primeira palavra significativa
    parts = [p for p in key.replace("fc ", "").replace("sc ", "").split() if p]
    if not parts:
        return team_name.strip()
    return parts[-1].title()


def _parse_csv(text: str) -> ClubEloInsight | None:
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if len(lines) < 2:
        return None
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    rows = list(reader)
    if not rows:
        return None
    row = rows[-1]
    try:
        elo = float(row.get("Elo") or 0)
    except (TypeError, ValueError):
        return None
    if elo <= 0:
        return None
    rank_raw = row.get("Rank")
    rank = int(rank_raw) if rank_raw and str(rank_raw).isdigit() else None
    club = str(row.get("Club") or "").strip()
    return ClubEloInsight(team=club, elo=elo, rank=rank)


def fetch_elo(team_name: str) -> ClubEloInsight | None:
    query = clubelo_query_name(team_name)
    cache_key = query.lower()
    cached = cache_get("clubelo", cache_key, _TTL)
    if isinstance(cached, dict) and cached.get("elo"):
        return ClubEloInsight(
            team=cached.get("team") or team_name,
            elo=float(cached["elo"]),
            rank=cached.get("rank"),
        )

    slug = urllib.parse.quote(query)
    url = f"{_BASE}/{slug}"
    _LIMITER.wait()
    req = urllib.request.Request(url, headers={"User-Agent": "futebol-betting-brain/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None

    insight = _parse_csv(text)
    if not insight:
        return None
    insight.team = team_name
    cache_set(
        "clubelo",
        cache_key,
        {"team": team_name, "elo": insight.elo, "rank": insight.rank, "at": time.time()},
    )
    return insight


def fetch_pair(home: str, away: str) -> tuple[ClubEloInsight | None, ClubEloInsight | None]:
    return fetch_elo(home), fetch_elo(away)