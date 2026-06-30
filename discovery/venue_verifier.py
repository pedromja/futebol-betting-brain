"""Verifica estádio real do jogo via web — corrige casa habitual em torneios neutros."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from discovery.web_browser import WebBrowser, WebSearchHit
from models.team_stats import MatchInput

# Ligas/torneios onde a equipa "casa" raramente joga no seu estádio habitual
NEUTRAL_TOURNAMENT_HINTS = (
    "world cup",
    "mundial",
    "fifa",
    "euro 20",
    "uefa euro",
    "european championship",
    "copa america",
    "copa américa",
    "gold cup",
    "nations league",
    "olympic",
    "olímpi",
    "confederations cup",
    "international friendly",
    "amistoso internacional",
)

STADIUM_SUFFIX = (
    "stadium",
    "arena",
    "field",
    "park",
    "bowl",
    "centre",
    "center",
    "coliseum",
    "dome",
    "estádio",
    "estadio",
    "estadio",
)

COUNTRY_FROM_TEXT: list[tuple[str, str]] = [
    (r"\b(united states|usa|u\.s\.a\.|u\.s\.)\b", "US"),
    (r"\b(mexico|méxico|mexico city|cdmx|guadalajara|monterrey)\b", "MX"),
    (r"\b(canada|toronto|vancouver|montreal)\b", "CA"),
    (r"\b(brazil|brasil)\b", "BR"),
    (r"\b(portugal)\b", "PT"),
    (r"\b(spain|españa|espanha)\b", "ES"),
    (r"\b(france|frança)\b", "FR"),
    (r"\b(germany|deutschland|alemanha)\b", "DE"),
    (r"\b(italy|italia|itália)\b", "IT"),
    (r"\b(england|uk|united kingdom)\b", "GB"),
]

US_STATE_ABBR = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN",
    "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV",
    "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN",
    "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
)


@dataclass
class ParsedVenue:
    stadium: str
    city: str = ""
    country: str = ""
    source_engine: str = ""
    source_url: str = ""
    raw_snippet: str = ""


@dataclass
class VenueVerification:
    stadium: str
    city: str
    country: str
    credibility: float
    source: str
    summary: str
    is_home_venue: bool = False
    corrected_from_usual: bool = False
    usual_home_stadium: str = ""
    verification_sources: list[str] = field(default_factory=list)
    discovery_steps: list[str] = field(default_factory=list)


def is_neutral_tournament(league: str) -> bool:
    key = (league or "").strip().lower()
    return any(hint in key for hint in NEUTRAL_TOURNAMENT_HINTS)


def _normalize_key(text: str) -> str:
    t = text.strip().lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    for suffix in STADIUM_SUFFIX:
        t = re.sub(rf"\b{suffix}\b", "", t)
    return t.strip()


def venues_differ(usual_stadium: str, usual_city: str, found_stadium: str, found_city: str) -> bool:
    """True se o estádio encontrado não coincide com o habitual da equipa casa."""
    if not found_stadium:
        return False
    if not usual_stadium and not usual_city:
        return bool(found_stadium)

    u_st = _normalize_key(usual_stadium)
    f_st = _normalize_key(found_stadium)
    u_ci = _normalize_key(usual_city)
    f_ci = _normalize_key(found_city)

    if u_st and f_st and (u_st == f_st or u_st in f_st or f_st in u_st):
        if not f_ci or not u_ci or u_ci == f_ci or u_ci in f_ci or f_ci in u_ci:
            return False

    if u_ci and f_ci and u_ci == f_ci and not f_st:
        return False

    return True


def _infer_country_from_text(text: str, fallback: str = "PT") -> str:
    blob = text.lower()
    for abbr in US_STATE_ABBR:
        if re.search(rf",\s*{abbr}\b", text, re.I):
            return "US"
    if re.search(r"\b(houston|dallas|miami|atlanta|los angeles|new york|seattle|denver)\b", blob):
        return "US"
    for pattern, code in COUNTRY_FROM_TEXT:
        if re.search(pattern, blob, re.I):
            return code
    return fallback


def _clean_stadium_name(raw: str) -> str:
    name = raw.strip()
    name = re.sub(r"^[\-\|\:\s]+", "", name)
    name = re.sub(r"\s+", " ", name)
    if len(name) < 4:
        return ""
    if len(name) > 80:
        name = name[:80].rsplit(" ", 1)[0]
    return name


def _stadium_plausible(stadium: str, home: str = "", away: str = "") -> bool:
    s = stadium.lower().strip()
    if len(s) < 4 or len(s.split()) > 5:
        return False
    h, a = home.lower().strip(), away.lower().strip()
    if h and a and h in s and a in s:
        return False
    if " vs " in s or " vs." in s:
        return False
    return True


def extract_venue_from_text(
    text: str,
    *,
    fallback_country: str = "PT",
    home: str = "",
    away: str = "",
) -> ParsedVenue | None:
    """Extrai estádio/cidade de título ou snippet de pesquisa."""
    if not text or len(text) < 8:
        return None

    blob = " ".join(text.split())
    suffix_pat = r"(?:Stadium|Arena|Field|Park|Bowl|Coliseum|Dome|Centre|Center|Estádio|Estadio)"

    patterns: list[tuple[str, int, int]] = [
        (rf"\bat\s+([A-Za-z0-9][\w\s\.'&\-]{{1,40}}{suffix_pat})\b", 1, 0),
        (rf"(?:venue|stadium|estádio|estadio)\s*[:\-]\s*([A-Za-z0-9][\w\s\.'&\-]{{2,55}}{suffix_pat})", 1, 0),
        (rf"([A-Za-z][\w\s\.'&\-]{{2,45}}{suffix_pat})\s*[,–\-]\s*([A-Za-z][\w\s\.'\-]{{2,35}})", 1, 2),
        (rf"(?:played|plays|held|hosted)\s+(?:at|in)\s+([A-Za-z][\w\s\.'&\-]{{2,55}}{suffix_pat})", 1, 0),
        (rf"\b([A-Za-z][\w\s\.'&\-]{{2,45}}{suffix_pat})\b", 1, 0),
    ]

    for pat, st_g, city_g in patterns:
        m = re.search(pat, blob, re.I)
        if not m:
            continue
        stadium = _clean_stadium_name(m.group(st_g))
        if not stadium or not _stadium_plausible(stadium, home, away):
            continue
        city = _clean_stadium_name(m.group(city_g)) if city_g and city_g <= m.lastindex else ""
        country = _infer_country_from_text(blob, fallback_country)
        return ParsedVenue(stadium=stadium, city=city, country=country, raw_snippet=blob[:160])

    return None


def _hit_matches_fixture(hit: WebSearchHit, home: str, away: str) -> bool:
    blob = f"{hit.title} {hit.snippet}".lower()
    home_l = home.lower()
    away_l = away.lower()
    if home_l not in blob:
        return False
    if away_l and away_l not in blob:
        # aceita se mencionar "vs" e uma das equipas + stadium keywords
        if not any(k in blob for k in ("stadium", "venue", "arena", "estádio", "estadio", "at ")):
            return False
    return True


def _parse_hit(
    hit: WebSearchHit,
    engine: str,
    fallback_country: str,
    *,
    home: str = "",
    away: str = "",
) -> ParsedVenue | None:
    for chunk in (f"{hit.title}. {hit.snippet}", hit.snippet, hit.title):
        parsed = extract_venue_from_text(
            chunk, fallback_country=fallback_country, home=home, away=away
        )
        if parsed:
            parsed.source_engine = engine
            parsed.source_url = hit.url
            return parsed
    return None


class VenueWebVerifier:
    """Pesquisa web multi-fonte e confirma estádio quando 2 fontes concordam."""

    def __init__(self, browser: WebBrowser | None = None):
        self.browser = browser or WebBrowser()

    def _gather_from_engine(
        self,
        engine: str,
        queries: list[str],
        *,
        home: str,
        away: str,
        fallback_country: str,
    ) -> list[ParsedVenue]:
        out: list[ParsedVenue] = []
        for query in queries:
            if engine == "bing":
                hits = self.browser.search(query, max_results=6)
            else:
                hits = self.browser.search_duckduckgo(query, max_results=6)
            for hit in hits:
                if not _hit_matches_fixture(hit, home, away):
                    continue
                parsed = _parse_hit(
                    hit, engine, fallback_country, home=home, away=away
                )
                if parsed:
                    out.append(parsed)
        return out

    def verify(
        self,
        match: MatchInput,
        *,
        usual_stadium: str = "",
        usual_city: str = "",
        usual_country: str = "PT",
        min_sources: int = 2,
        require_different_from_usual: bool = True,
    ) -> VenueVerification | None:
        """
        Pesquisa o encontro na web. Se >= min_sources fontes distintas apontarem
        para um estádio diferente do habitual da casa, devolve correção.
        """
        home = match.home.name
        away = match.away.name
        league = match.league or ""
        date = match.date or ""
        fallback = usual_country or "PT"

        queries = [
            f'"{home}" vs "{away}" stadium venue {league} {date}'.strip(),
            f"{home} {away} match location stadium {date}".strip(),
        ]
        if is_neutral_tournament(league):
            queries.append(f"{home} vs {away} World Cup stadium city {date}".strip())

        by_engine: dict[str, list[ParsedVenue]] = {
            "bing": self._gather_from_engine("bing", queries[:2], home=home, away=away, fallback_country=fallback),
            "duckduckgo": self._gather_from_engine(
                "duckduckgo",
                [f"{home} vs {away} stadium {league} {date}".strip()],
                home=home,
                away=away,
                fallback_country=fallback,
            ),
        }

        active_engines = [name for name, rows in by_engine.items() if rows]
        if len(active_engines) < min_sources:
            return None

        stadium_meta: dict[str, ParsedVenue] = {}
        engine_by_stadium: dict[str, set[str]] = {}

        for engine_name, parsed_list in by_engine.items():
            seen_stadiums: set[str] = set()
            for pv in parsed_list:
                key = _normalize_key(pv.stadium)
                if not key or key in seen_stadiums:
                    continue
                seen_stadiums.add(key)
                engine_by_stadium.setdefault(key, set()).add(engine_name)
                if key not in stadium_meta or (pv.city and not stadium_meta[key].city):
                    stadium_meta[key] = pv

        best_key = ""
        best_engines: set[str] = set()
        for key, eng_set in engine_by_stadium.items():
            if len(eng_set) >= min_sources and len(eng_set) > len(best_engines):
                best_key = key
                best_engines = eng_set

        if not best_key or len(best_engines) < min_sources:
            return None

        chosen = stadium_meta[best_key]
        differs = venues_differ(usual_stadium, usual_city, chosen.stadium, chosen.city)
        if require_different_from_usual and not differs:
            return None
        if not differs and not usual_stadium and not usual_city:
            differs = False

        country = chosen.country or _infer_country_from_text(chosen.raw_snippet, fallback)
        city = chosen.city or chosen.stadium
        sources = sorted(best_engines)
        corrected = differs and bool(usual_stadium or usual_city)

        steps = [
            "Verificação web multi-fonte (clima/altitude)",
        ]
        if usual_stadium or usual_city:
            steps.append(f"Casa habitual: {usual_stadium or usual_city}")
        steps.extend(
            [
                f"Estádio do jogo: {chosen.stadium} ({city}, {country})",
                f"Fontes: {', '.join(sources)} ({len(best_engines)} motores)",
            ]
        )

        if corrected:
            summary = (
                f"Estádio real confirmado por {len(best_engines)} fontes web "
                f"(≠ casa habitual {usual_stadium or usual_city})"
            )
        else:
            summary = f"Estádio confirmado por {len(best_engines)} fontes web"

        return VenueVerification(
            stadium=chosen.stadium,
            city=city,
            country=country,
            credibility=0.55 + 0.15 * len(best_engines),
            source="web_multi_source",
            summary=summary,
            is_home_venue=not corrected,
            corrected_from_usual=corrected,
            usual_home_stadium=usual_stadium or usual_city,
            verification_sources=sources,
            discovery_steps=steps,
        )