"""
DeepSearch — pesquisa automática de notícias validadas no X via xAI x_search.

Sem intervenção humana: usa equipas, data e liga do jogo.
"""

import json
from datetime import datetime
from pathlib import Path

from discovery.x_client import XSearchClient
from models.team_stats import MatchInput

from .types import MatchNewsReport, NewsCategory, NewsItem, TeamNewsReport
from .web_news import WebNewsClient

NEWS_PROMPT = """Pesquisa no X notícias recentes sobre a equipa de futebol "{team}" \
antes do jogo contra "{opponent}" ({league}, {date}).

Procura em contas oficiais, jornalistas credíveis e fontes verificadas:
- Lesões ou castigos de jogadores importantes
- Salários em atraso ou problemas financeiros
- Descontentamento de adeptos ou protestos
- Crise no balneário ou mudança de treinador
- Regressos positivos de jogadores

Só inclui notícias com fonte identificável no X.
Responde APENAS com JSON válido (array), sem markdown:
[
  {{
    "category": "key_player_injury|key_player_suspension|squad_player_injury|unpaid_salaries|fan_unrest|dressing_room_crisis|manager_change|positive_return|general_negative|general_positive",
    "headline": "título curto",
    "summary": "resumo em 1 frase",
    "severity": 0.0-1.0,
    "credibility": 0.0-1.0,
    "player_importance": 0.0-1.0,
    "days_ago": número,
    "source_handle": "@conta",
    "source_url": "url ou vazio",
    "validated": true
  }}
]

Se não houver notícias relevantes verificadas, responde: []"""


class DeepSearchClient:
    def __init__(self, api_key: str | None = None, use_web_fallback: bool = True):
        self.x_client = XSearchClient(api_key=api_key)
        self.web_news = WebNewsClient()
        self.use_web_fallback = use_web_fallback

    @property
    def is_live(self) -> bool:
        return self.x_client.is_live

    def _parse_category(self, raw: str) -> NewsCategory:
        try:
            return NewsCategory(raw.strip().lower())
        except ValueError:
            return NewsCategory.GENERAL_NEGATIVE

    def _parse_items(self, text: str, team: str) -> list[NewsItem]:
        items: list[NewsItem] = []
        for entry in self.x_client.parse_json_array(text):
            if not isinstance(entry, dict):
                continue
            credibility = float(entry.get("credibility", 0.5))
            if credibility < 0.4:
                continue
            items.append(
                NewsItem(
                    team=team,
                    category=self._parse_category(entry.get("category", "general_negative")),
                    headline=entry.get("headline", ""),
                    summary=entry.get("summary", ""),
                    severity=float(entry.get("severity", 0.5)),
                    credibility=credibility,
                    player_importance=float(entry.get("player_importance", 0.5)),
                    days_ago=float(entry.get("days_ago", 2)),
                    source_handle=entry.get("source_handle", ""),
                    source_url=entry.get("source_url", ""),
                    validated=bool(entry.get("validated", credibility >= 0.6)),
                )
            )
        return items

    def _search_team(
        self, team: str, opponent: str, league: str, date: str
    ) -> TeamNewsReport:
        if not self.is_live:
            return TeamNewsReport(team=team, items=[], source="offline")

        prompt = NEWS_PROMPT.format(
            team=team,
            opponent=opponent,
            league=league or "futebol",
            date=date or datetime.now().strftime("%Y-%m-%d"),
        )

        text, source = self.x_client.query(prompt, days_back=10)
        items = self._parse_items(text, team)

        return TeamNewsReport(
            team=team,
            items=items,
            source=source,
            fetched_at=datetime.now().isoformat(),
        )

    def fetch_live(self, match: MatchInput) -> MatchNewsReport:
        date = match.date or datetime.now().strftime("%Y-%m-%d")
        home = self._search_team(
            match.home.name, match.away.name, match.league, date
        )
        away = self._search_team(
            match.away.name, match.home.name, match.league, date
        )
        return MatchNewsReport(home=home, away=away, source="x_search")

    def fetch_sample(self, match_key: str) -> MatchNewsReport | None:
        path = Path(__file__).parent.parent / "data" / "sample_news.json"
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if match_key not in data:
            return None

        entry = data[match_key]

        def _items(team_name: str, raw_items: list) -> list[NewsItem]:
            result = []
            for item in raw_items:
                result.append(
                    NewsItem(
                        team=team_name,
                        category=self._parse_category(item["category"]),
                        headline=item["headline"],
                        summary=item["summary"],
                        severity=item["severity"],
                        credibility=item["credibility"],
                        player_importance=item.get("player_importance", 0.5),
                        days_ago=item.get("days_ago", 2),
                        source_handle=item.get("source_handle", ""),
                        source_url=item.get("source_url", ""),
                        validated=item.get("validated", True),
                    )
                )
            return result

        return MatchNewsReport(
            home=TeamNewsReport(
                team=entry["home_team"],
                items=_items(entry["home_team"], entry.get("home_news", [])),
                source="sample_x",
            ),
            away=TeamNewsReport(
                team=entry["away_team"],
                items=_items(entry["away_team"], entry.get("away_news", [])),
                source="sample_x",
            ),
            source="sample_x",
        )

    def fetch(
        self,
        match: MatchInput,
        match_key: str | None = None,
        force_sample: bool = False,
    ) -> MatchNewsReport:
        if self.is_live and not force_sample:
            return self.fetch_live(match)

        if self.use_web_fallback and not force_sample:
            web_report = self.web_news.fetch(match)
            if web_report.home.items or web_report.away.items:
                return web_report

        if match_key:
            sample = self.fetch_sample(match_key)
            if sample:
                return sample

        return MatchNewsReport(
            home=TeamNewsReport(team=match.home.name, source="none"),
            away=TeamNewsReport(team=match.away.name, source="none"),
            source="none",
        )