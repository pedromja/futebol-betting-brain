"""
Notícias via pesquisa web gratuita (Bing) — alternativa ao X.
Heurística por palavras-chave; credibilidade mais baixa que X validado.
"""

import re
from datetime import datetime

from discovery.response_cache import get as cache_get
from discovery.response_cache import set as cache_set
from discovery.web_browser import WebBrowser
from models.team_stats import MatchInput

from .types import MatchNewsReport, NewsCategory, NewsItem, TeamNewsReport

_NEWS_TTL = 14400

KEYWORD_RULES: list[tuple[str, NewsCategory, float]] = [
    (r"\binjur(y|ies|ed)|lesão|lesionado|ruptura|hamstring", NewsCategory.KEY_PLAYER_INJURY, 0.75),
    (r"\bsuspend(ed|sion)|suspenso|cartão vermelho", NewsCategory.KEY_PLAYER_SUSPENSION, 0.72),
    (r"\bsack(ed|ing)|despedido|manager change|novo treinador", NewsCategory.MANAGER_CHANGE, 0.70),
    (r"\bcrisis|crise|balneário|dressing room", NewsCategory.DRESSING_ROOM_CRISIS, 0.65),
    (r"\bunpaid|salários|wage", NewsCategory.UNPAID_SALARIES, 0.68),
    (r"\bprotest|adeptos|fan unrest", NewsCategory.FAN_UNREST, 0.60),
    (r"\breturn|regress|fit again|recuperado", NewsCategory.POSITIVE_RETURN, 0.55),
]


class WebNewsClient:
    def __init__(self, browser: WebBrowser | None = None):
        self.browser = browser or WebBrowser()
        self._session: dict[str, TeamNewsReport] = {}

    def _classify(self, text: str) -> tuple[NewsCategory, float]:
        lower = text.lower()
        for pattern, category, severity in KEYWORD_RULES:
            if re.search(pattern, lower, re.I):
                return category, severity
        if re.search(r"\bwin|vitória|boost|confiança", lower, re.I):
            return NewsCategory.GENERAL_POSITIVE, 0.35
        return NewsCategory.GENERAL_NEGATIVE, 0.30

    def _search_team(self, team: str, opponent: str, league: str) -> TeamNewsReport:
        cache_key = f"{team.lower()}|{opponent.lower()}"
        if cache_key in self._session:
            return self._session[cache_key]

        cached = cache_get("team_news", cache_key, _NEWS_TTL)
        if cached and isinstance(cached, dict):
            items: list[NewsItem] = []
            for raw in cached.get("items", []):
                cat = raw.get("category", "general_negative")
                if isinstance(cat, str):
                    try:
                        cat = NewsCategory(cat)
                    except ValueError:
                        cat = NewsCategory.GENERAL_NEGATIVE
                items.append(NewsItem(**{**raw, "category": cat}))
            report = TeamNewsReport(
                team=team,
                items=items,
                source=cached.get("source", "web_search"),
                fetched_at=cached.get("fetched_at", ""),
            )
            self._session[cache_key] = report
            return report

        query = f"{team} football injury suspension news"
        hits = self.browser.search(query, max_results=3)
        items: list[NewsItem] = []

        for hit in hits:
            blob = f"{hit.title} {hit.snippet}"
            if team.lower() not in blob.lower():
                continue
            category, severity = self._classify(blob)
            if category in (NewsCategory.GENERAL_NEGATIVE, NewsCategory.GENERAL_POSITIVE):
                if severity < 0.4:
                    continue
            items.append(
                NewsItem(
                    team=team,
                    category=category,
                    headline=hit.title[:120],
                    summary=hit.snippet[:200] or hit.title[:200],
                    severity=severity,
                    credibility=0.55,
                    player_importance=0.55,
                    days_ago=2.0,
                    source_handle="web_search",
                    source_url=hit.url,
                    validated=False,
                )
            )

        report = TeamNewsReport(
            team=team,
            items=items[:3],
            source="web_search",
            fetched_at=datetime.now().isoformat(),
        )
        self._session[cache_key] = report
        cache_set(
            "team_news",
            cache_key,
            {
                "items": [
                    {
                        **item.__dict__,
                        "category": item.category.value,
                    }
                    for item in report.items
                ],
                "source": report.source,
                "fetched_at": report.fetched_at,
            },
        )
        return report

    def fetch(self, match: MatchInput) -> MatchNewsReport:
        home = self._search_team(match.home.name, match.away.name, match.league)
        away = self._search_team(match.away.name, match.home.name, match.league)
        return MatchNewsReport(home=home, away=away, source="web_search")