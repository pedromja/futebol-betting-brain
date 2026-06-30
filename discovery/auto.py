"""
Descoberta automática — mínima interferência humana.

Via X (x_search):
  - Valida/confirma o estádio onde o jogo se realiza
  - Pesquisa notícias que afetam cada equipa

Offline (sem API):
  - Estádio casa inferido pelo registo local (equipa → estádio)
  - País inferido pela liga
"""

from dataclasses import dataclass, field
from datetime import datetime

from discovery.venue_verifier import VenueWebVerifier, is_neutral_tournament
from discovery.web_browser import WebBrowser
from discovery.x_client import XSearchClient
from environment.venue_registry import VenueQuery, VenueRegistry
from models.team_stats import MatchInput


LEAGUE_COUNTRY: dict[str, str] = {
    "primeira liga": "PT",
    "liga portugal": "PT",
    "liga portugal 2": "PT",
    "taça de portugal": "PT",
    "premier league": "GB",
    "la liga": "ES",
    "serie a": "IT",
    "bundesliga": "DE",
    "ligue 1": "FR",
    "champions": "EU",
    "liga dos campeões": "EU",
    "europa league": "EU",
    "conference league": "EU",
    "world cup": "US",
    "fifa world cup": "US",
    "mundial": "US",
    "copa america": "US",
    "copa américa": "US",
    "euro 202": "EU",
    "uefa euro": "EU",
}


VENUE_PROMPT = """Pesquisa no X onde se vai realizar o jogo de futebol 11:
  {home} (casa) vs {away} (fora)
  Liga: {league}
  Data: {date}

Procura em contas oficiais dos clubes, jornalistas desportivos credíveis e comunicados.
Confirma o ESTÁDIO exacto, a CIDADE e o PAÍS (código ISO de 2 letras).

Responde APENAS com JSON válido, sem markdown:
{{
  "stadium": "nome oficial do estádio",
  "city": "cidade",
  "country": "PT",
  "is_home_venue": true,
  "credibility": 0.0-1.0,
  "source_handle": "@conta_validada",
  "summary": "frase curta sobre a confirmação"
}}

Se não encontrares informação fiável, responde com credibility abaixo de 0.4."""


@dataclass
class DiscoveredVenue:
    stadium: str = ""
    city: str = ""
    country: str = "PT"
    credibility: float = 0.0
    source: str = "none"
    source_handle: str = ""
    summary: str = ""
    is_home_venue: bool = True
    corrected_from_usual: bool = False
    usual_home_stadium: str = ""
    verification_sources: list[str] = field(default_factory=list)
    discovery_steps: list[str] = field(default_factory=list)


class MatchAutoDiscovery:
    def __init__(
        self,
        xai_api_key: str | None = None,
        weather_api_key: str | None = None,
    ):
        self.x_client = XSearchClient(api_key=xai_api_key)
        self.browser = WebBrowser()
        self.registry = VenueRegistry(api_key=weather_api_key)
        self.venue_verifier = VenueWebVerifier(browser=self.browser)

    @staticmethod
    def infer_country(league: str) -> str:
        if not league:
            return "PT"
        key = league.strip().lower()
        for pattern, code in LEAGUE_COUNTRY.items():
            if pattern in key:
                return code
        return "PT"

    def _discover_venue_via_x(self, match: MatchInput) -> DiscoveredVenue | None:
        if not self.x_client.is_live:
            return None

        date_str = match.date or datetime.now().strftime("%Y-%m-%d")
        prompt = VENUE_PROMPT.format(
            home=match.home.name,
            away=match.away.name,
            league=match.league or "futebol",
            date=date_str,
        )

        text, _ = self.x_client.query(prompt, days_back=21)
        data = self.x_client.parse_json_object(text)
        if not data:
            return None

        credibility = float(data.get("credibility", 0))
        if credibility < 0.35:
            return None

        return DiscoveredVenue(
            stadium=data.get("stadium", ""),
            city=data.get("city", ""),
            country=data.get("country", self.infer_country(match.league)),
            credibility=credibility,
            source="x_search",
            source_handle=data.get("source_handle", ""),
            summary=data.get("summary", ""),
            is_home_venue=bool(data.get("is_home_venue", True)),
            discovery_steps=[
                f"X Search: {data.get('summary', 'estádio confirmado')}",
                f"Credibilidade: {credibility:.0%}",
                f"Fonte: {data.get('source_handle', '—')}",
            ],
        )

    def _discover_venue_via_web(self, match: MatchInput) -> DiscoveredVenue | None:
        query = (
            f"{match.home.name} vs {match.away.name} stadium venue "
            f"{match.league} {match.date or ''}"
        )
        hits = self.browser.search(query, max_results=4)
        for hit in hits:
            blob = f"{hit.title} {hit.snippet}".lower()
            if match.home.name.lower() not in blob:
                continue
            stadium = hit.title.split(" - ")[0][:80] if hit.title else ""
            if not stadium:
                continue
            return DiscoveredVenue(
                stadium=stadium,
                city=match.home.name,
                country=self.infer_country(match.league),
                credibility=0.50,
                source="web_search",
                source_handle=hit.url[:60],
                summary=hit.snippet[:120] or "Estádio via pesquisa web",
                discovery_steps=[
                    "Pesquisa web (Bing) — gratuita",
                    f"Resultado: {hit.title[:80]}",
                ],
            )
        return None

    def _home_usual_venue(self, match: MatchInput) -> DiscoveredVenue | None:
        """Estádio habitual da equipa casa (registo local) — baseline para comparação."""
        return self._discover_venue_offline(match)

    def _discover_venue_offline(self, match: MatchInput) -> DiscoveredVenue | None:
        country = self.infer_country(match.league)
        steps: list[str] = []

        query = VenueQuery(
            team=match.home.name,
            country=country,
        )
        record, source = self.registry.resolve(query, auto_geocode=False)
        if record:
            steps.append(f"Registo local: {record.display_name} (equipa casa)")
            steps.append(f"Origem: {source}")
            return DiscoveredVenue(
                stadium=record.stadium or record.key,
                city=record.city,
                country=record.country or country,
                credibility=0.75,
                source="registry_team",
                summary=f"Estádio casa de {match.home.name}",
                discovery_steps=steps,
            )

        query2 = VenueQuery(
            stadium="",
            city=match.home.name,
            country=country,
            team=match.home.name,
        )
        record2, source2 = self.registry.resolve(query2, auto_geocode=True)
        if record2:
            steps.append(f"Geocodificado: {record2.display_name}")
            return DiscoveredVenue(
                stadium=record2.stadium or record2.key,
                city=record2.city,
                country=record2.country or country,
                credibility=0.55,
                source=source2,
                summary=f"Local inferido para {match.home.name}",
                discovery_steps=steps,
            )

        return None

    def _verification_to_discovered(self, verified) -> DiscoveredVenue:
        return DiscoveredVenue(
            stadium=verified.stadium,
            city=verified.city,
            country=verified.country,
            credibility=verified.credibility,
            source=verified.source,
            summary=verified.summary,
            is_home_venue=verified.is_home_venue,
            corrected_from_usual=verified.corrected_from_usual,
            usual_home_stadium=verified.usual_home_stadium,
            verification_sources=list(verified.verification_sources),
            discovery_steps=list(verified.discovery_steps),
        )

    def discover_venue(self, match: MatchInput) -> DiscoveredVenue:
        """Descobre o estádio com mínima intervenção humana."""
        if match.venue_stadium:
            return DiscoveredVenue(
                stadium=match.venue_stadium,
                city=match.venue_city,
                country=match.venue_country or self.infer_country(match.league),
                credibility=1.0,
                source="manual",
                summary="Introduzido manualmente",
            )

        usual = self._home_usual_venue(match)
        force_web = is_neutral_tournament(match.league)

        verified = self.venue_verifier.verify(
            match,
            usual_stadium=usual.stadium if usual else "",
            usual_city=usual.city if usual else match.home.name,
            usual_country=usual.country if usual else self.infer_country(match.league),
            require_different_from_usual=bool(usual) and not force_web,
        )
        if verified:
            return self._verification_to_discovered(verified)

        if usual and not force_web:
            usual.discovery_steps.insert(0, "Registo local — web não contradisse casa habitual")
            return usual

        x_result = self._discover_venue_via_x(match)
        if x_result and x_result.stadium:
            x_result.discovery_steps.insert(0, "Validação no X")
            return x_result

        web_result = self._discover_venue_via_web(match)
        if web_result and web_result.stadium:
            return web_result

        country = self.infer_country(match.league)
        return DiscoveredVenue(
            stadium="",
            city=match.home.name,
            country=country,
            credibility=0.3,
            source="inferred",
            summary=f"Assumido casa de {match.home.name}",
            discovery_steps=[
                "Não foi possível validar no X nem no registo",
                f"Assumido: {match.home.name} joga em casa ({country})",
            ],
        )

    def apply_venue_to_match(self, match: MatchInput) -> tuple[MatchInput, DiscoveredVenue]:
        discovered = self.discover_venue(match)
        updated = MatchInput(
            home=match.home,
            away=match.away,
            odds=match.odds,
            league=match.league,
            date=match.date,
            home_advantage=match.home_advantage,
            league_avg_goals=match.league_avg_goals,
            venue_stadium=discovered.stadium,
            venue_city=discovered.city or match.home.name,
            venue_country=discovered.country,
        )
        return updated, discovered