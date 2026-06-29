"""
Registo de estádios — resolve local do jogo e geocodifica automaticamente.

Sempre que a meteorologia é necessária:
  1. Procura o estádio/local no venue_coords.json
  2. Se não existir, geocodifica via OpenWeatherMap Geocoding API
  3. Grava o novo estádio no registo para uso futuro
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

_REGISTRY_PATH = Path(__file__).parent.parent / "data" / "venue_coords.json"
_GEO_BASE = "https://api.openweathermap.org/geo/1.0"


@dataclass
class VenueQuery:
    stadium: str = ""
    city: str = ""
    country: str = "PT"
    team: str = ""


@dataclass
class VenueRecord:
    key: str
    lat: float
    lon: float
    altitude_m: float = 0.0
    city: str = ""
    country: str = ""
    team: str = ""
    stadium: str = ""
    source: str = "registry"
    aliases: list[str] = field(default_factory=list)
    added_at: str = ""

    @property
    def display_name(self) -> str:
        if self.stadium:
            return f"{self.stadium} ({self.city})" if self.city else self.stadium
        return self.city or self.key


class VenueRegistry:
    def __init__(self, api_key: str | None = None, path: Path | None = None):
        self.api_key = api_key or os.getenv("OPENWEATHERMAP_API_KEY", "")
        self.path = path or _REGISTRY_PATH

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _normalize(self, text: str) -> str:
        return text.strip().lower()

    def _entry_to_record(self, key: str, entry: dict) -> VenueRecord:
        return VenueRecord(
            key=key,
            lat=entry["lat"],
            lon=entry["lon"],
            altitude_m=entry.get("altitude_m", 0),
            city=entry.get("city", ""),
            country=entry.get("country", ""),
            team=entry.get("team", ""),
            stadium=entry.get("stadium", key if entry.get("type") == "stadium" else ""),
            source=entry.get("source", "registry"),
            aliases=entry.get("aliases", []),
            added_at=entry.get("added_at", ""),
        )

    def _find_in_registry(self, query: VenueQuery) -> VenueRecord | None:
        data = self._load()
        candidates = [
            query.stadium,
            query.city,
            query.team,
        ]
        normalized = {self._normalize(c) for c in candidates if c}

        for key, entry in data.items():
            key_norm = self._normalize(key)
            if key_norm in normalized:
                return self._entry_to_record(key, entry)

            for alias in entry.get("aliases", []):
                if self._normalize(alias) in normalized:
                    return self._entry_to_record(key, entry)

            if query.team and self._normalize(entry.get("team", "")) == self._normalize(query.team):
                if entry.get("type") == "stadium" or entry.get("stadium"):
                    return self._entry_to_record(key, entry)

            if query.stadium and self._normalize(entry.get("stadium", "")) == self._normalize(query.stadium):
                return self._entry_to_record(key, entry)

        return None

    def _geocode_queries(self, query: VenueQuery) -> list[str]:
        country = query.country or "PT"
        searches: list[str] = []

        if query.stadium and query.city:
            searches.append(f"{query.stadium}, {query.city}, {country}")
        if query.stadium:
            searches.append(f"{query.stadium}, {country}")
        if query.team and query.city:
            searches.append(f"{query.team} stadium, {query.city}, {country}")
        if query.team:
            searches.append(f"{query.team} stadium, {country}")
        if query.city:
            searches.append(f"{query.city}, {country}")

        seen: set[str] = set()
        unique: list[str] = []
        for s in searches:
            norm = s.lower()
            if norm not in seen:
                seen.add(norm)
                unique.append(s)
        return unique

    def _geocode(self, search: str) -> dict | None:
        if not self.api_key:
            return None

        params = urllib.parse.urlencode({
            "q": search,
            "limit": 1,
            "appid": self.api_key,
        })
        url = f"{_GEO_BASE}/direct?{params}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                results = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return None

        if not results:
            return None
        return results[0]

    def _register_geocoded(
        self, query: VenueQuery, geo: dict, search_used: str
    ) -> VenueRecord:
        name = geo.get("local_names", {}).get("pt") or geo.get("name", query.city)
        stadium_name = query.stadium or (
            f"Estádio {query.team}" if query.team and not query.city else ""
        )
        key = query.stadium or (f"{query.team} - {name}" if query.team else name)

        record_entry = {
            "lat": geo["lat"],
            "lon": geo["lon"],
            "altitude_m": 0,
            "city": name,
            "country": geo.get("country", query.country),
            "team": query.team,
            "stadium": stadium_name or "",
            "type": "stadium" if query.stadium or query.team else "city",
            "source": "openweathermap_geocoding",
            "geocode_query": search_used,
            "aliases": [a for a in [query.city, query.team, name] if a],
            "added_at": datetime.now().isoformat(timespec="seconds"),
        }

        data = self._load()
        if key not in data:
            data[key] = record_entry
            self._save(data)

        return self._entry_to_record(key, record_entry)

    def resolve(
        self,
        query: VenueQuery,
        auto_geocode: bool = True,
    ) -> tuple[VenueRecord | None, str]:
        """
        Resolve o local do jogo. Retorna (registo, origem).
        Origem: registry | geocoded | not_found
        """
        existing = self._find_in_registry(query)
        if existing:
            return existing, "registry"

        if not auto_geocode or not self.api_key:
            return None, "not_found"

        for search in self._geocode_queries(query):
            geo = self._geocode(search)
            if geo:
                record = self._register_geocoded(query, geo, search)
                return record, "geocoded"

        return None, "not_found"

    def list_stadiums(self) -> list[str]:
        data = self._load()
        return sorted(data.keys())