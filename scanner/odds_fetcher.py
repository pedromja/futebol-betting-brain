"""Obtém odds automaticamente via X Search."""

from discovery.fixture_scanner import UpcomingFixture
from discovery.x_client import XSearchClient

ODDS_PROMPT = """Pesquisa no X as odds ATUAIS de apostas para o jogo de futebol:
  {home} vs {away} ({league})

Procura mercados: 1X2, Over/Under 2.5, BTTS.
Fontes: casas de apostas, contas de odds, jornalistas credíveis.

Responde APENAS JSON, sem markdown:
{{
  "home_win": 0.0,
  "draw": 0.0,
  "away_win": 0.0,
  "over_25": 0.0,
  "under_25": 0.0,
  "btts_yes": 0.0,
  "btts_no": 0.0,
  "credibility": 0.0-1.0
}}

Se não encontrares odds fiáveis, credibility < 0.4."""


class OddsFetcher:
    def __init__(self, xai_api_key: str | None = None):
        self.x_client = XSearchClient(api_key=xai_api_key)

    def fetch(self, fixture: UpcomingFixture) -> dict | None:
        if fixture.odds_hint:
            return fixture.odds_hint

        if not self.x_client.is_live:
            return None

        prompt = ODDS_PROMPT.format(
            home=fixture.home,
            away=fixture.away,
            league=fixture.league,
        )
        text, _ = self.x_client.query(prompt, days_back=3)
        data = self.x_client.parse_json_object(text)
        if not data:
            return None

        cred = float(data.get("credibility", 0))
        if cred < 0.4:
            return None

        required = [
            "home_win", "draw", "away_win",
            "over_25", "under_25", "btts_yes", "btts_no",
        ]
        for key in required:
            if key not in data or float(data[key]) < 1.01:
                return None

        return {k: float(data[k]) for k in required}