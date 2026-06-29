"""
Cliente HTTP simples — pesquisa e leitura de páginas web (stdlib).
Cache + limitador para evitar bottlenecks das APIs gratuitas.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser

from discovery.rate_limiter import MinIntervalLimiter
from discovery.response_cache import get as cache_get
from discovery.response_cache import set as cache_set

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; FutebolBettingBrain/1.0; +https://local)"
)

_BING_LIMITER = MinIntervalLimiter(2.0)


@dataclass
class WebSearchHit:
    title: str
    url: str
    snippet: str = ""


class _BingResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hits: list[WebSearchHit] = []
        self._capture: str | None = None
        self._buf = ""
        self._current = WebSearchHit("", "")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: v for k, v in attrs if v}
        cls = attr.get("class", "")
        if tag == "a" and "tilk" in cls:
            self._capture = "title"
            self._buf = ""
            self._current = WebSearchHit("", "")
            href = attr.get("href", "")
            if href.startswith("http"):
                self._current.url = href
        elif tag == "p" and "b_lineclamp" in cls:
            self._capture = "snippet"
            self._buf = ""

    def handle_endtag(self, tag: str) -> None:
        if self._capture == "title" and tag == "a":
            self._current.title = self._buf.strip()
            self._capture = None
        elif self._capture == "snippet" and tag == "p":
            self._current.snippet = self._buf.strip()
            if self._current.title or self._current.url:
                self.hits.append(self._current)
            self._current = WebSearchHit("", "")
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buf += data


class WebBrowser:
    def __init__(self, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 25):
        self.user_agent = user_agent
        self.timeout = timeout

    def fetch(self, url: str) -> str:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.user_agent, "Accept-Language": "en-US,pt-PT;q=0.9"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def fetch_json(
        self,
        url: str,
        *,
        cache_ns: str = "",
        cache_ttl: int = 600,
    ) -> dict | list | None:
        if cache_ns:
            cached = cache_get(cache_ns, url, cache_ttl)
            if cached is not None:
                return cached

        try:
            raw = self.fetch(url)
            data = json.loads(raw)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return None

        if cache_ns and data is not None:
            cache_set(cache_ns, url, data)
        return data

    def search(
        self,
        query: str,
        max_results: int = 8,
        *,
        cache_ttl: int = 3600,
    ) -> list[WebSearchHit]:
        cached = cache_get("bing_search", query, cache_ttl)
        if cached is not None:
            return [
                WebSearchHit(**h) if isinstance(h, dict) else h
                for h in cached
            ]

        _BING_LIMITER.wait()
        q = urllib.parse.quote(query)
        url = f"https://www.bing.com/search?q={q}&setlang=en-us&count={max_results}"
        try:
            html = self.fetch(url)
        except (urllib.error.URLError, TimeoutError):
            return []

        parser = _BingResultParser()
        parser.feed(html)
        hits = [h for h in parser.hits if h.url.startswith("http")][:max_results]
        cache_set(
            "bing_search",
            query,
            [{"title": h.title, "url": h.url, "snippet": h.snippet} for h in hits],
        )
        return hits

    @staticmethod
    def extract_vs_pairs(text: str) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        patterns = [
            r"([A-ZÀ-Ú][A-Za-zÀ-ú0-9\s\.'\-]{2,40})\s+vs\.?\s+([A-ZÀ-Ú][A-Za-zÀ-ú0-9\s\.'\-]{2,40})",
            r"([A-ZÀ-Ú][A-Za-zÀ-ú0-9\s\.'\-]{2,40})\s+at\s+([A-ZÀ-Ú][A-Za-zÀ-ú0-9\s\.'\-]{2,40})",
        ]
        for pat in patterns:
            for home, away in re.findall(pat, text):
                home, away = home.strip(), away.strip()
                if len(home) >= 3 and len(away) >= 3:
                    pairs.append((home, away))
        return pairs