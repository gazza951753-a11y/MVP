from __future__ import annotations

from datetime import datetime
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import CollectResult, Collector
from app.config import settings


class RussianWebCollector(Collector):
    name = "russian_web"

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    @staticmethod
    def _extract_real_url(raw: str) -> str:
        parsed = urlparse(raw)
        if "duckduckgo.com" in parsed.netloc and parsed.path == "/l/":
            query = parse_qs(parsed.query)
            if "uddg" in query:
                return query["uddg"][0]
        return raw

    @staticmethod
    def _platform_type(url: str) -> str:
        host = urlparse(url).netloc.lower()
        if "t.me" in host:
            return "telegram_channel"
        if "vk.com" in host:
            return "vk_group"
        if "dzen.ru" in host or "pikabu.ru" in host or "habr.com" in host or "forum" in host:
            return "forum_thread"
        return "web_page"

    def _parse_duckduckgo(self, html: str, query: str) -> tuple[list[dict], list[dict]]:
        platforms: list[dict] = []
        mentions: list[dict] = []

        soup = BeautifulSoup(html, "html.parser")
        result_items = soup.select(".result")
        for item in result_items[:25]:
            a = item.select_one("a.result__a")
            snippet = item.select_one(".result__snippet")
            if not a or not a.get("href"):
                continue
            source_url = self._extract_real_url(a["href"])
            title = a.get_text(" ", strip=True) or "Без названия"
            text = snippet.get_text(" ", strip=True) if snippet else ""
            p, m = self._build_records(source_url, title, text, query, "duckduckgo")
            platforms.append(p)
            mentions.append(m)
        return platforms, mentions

    def _parse_bing(self, html: str, query: str) -> tuple[list[dict], list[dict]]:
        platforms: list[dict] = []
        mentions: list[dict] = []

        soup = BeautifulSoup(html, "html.parser")
        result_items = soup.select("li.b_algo")
        for item in result_items[:25]:
            a = item.select_one("h2 a")
            snippet = item.select_one(".b_caption p")
            if not a or not a.get("href"):
                continue
            source_url = a["href"]
            title = a.get_text(" ", strip=True) or "Без названия"
            text = snippet.get_text(" ", strip=True) if snippet else ""
            p, m = self._build_records(source_url, title, text, query, "bing")
            platforms.append(p)
            mentions.append(m)
        return platforms, mentions

    def _build_records(self, source_url: str, title: str, text: str, query: str, engine: str) -> tuple[dict, dict]:
        ptype = self._platform_type(source_url)
        platform = {
            "platform_type": ptype,
            "title": title[:300],
            "url": source_url,
            "description": text[:1000],
            "language": "ru",
            "geo": "RU",
            "audience_size": None,
            "activity_last_seen_at": datetime.utcnow(),
            "rules_text": None,
            "commercial_tolerance": 0,
            "risk_flags": {"unvalidated": True},
            "tags": ["ru", "student_help"],
            "discovery_source": f"{engine}:{query[:80]}",
        }
        mention = {
            "platform_url": source_url,
            "mention_type": "search_result",
            "source_url": source_url,
            "author_handle": None,
            "published_at": None,
            "text": f"{title}. {text}",
            "raw_payload": {"query": query, "engine": engine},
        }
        return platform, mention

    def collect(self) -> CollectResult:
        platforms: list[dict] = []
        mentions: list[dict] = []

        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for query in settings.discovery_queries:
                # 1) DuckDuckGo
                try:
                    ddg = client.get(
                        "https://duckduckgo.com/html/",
                        params={"q": query, "kl": "ru-ru"},
                        headers={"User-Agent": "Mozilla/5.0 (StudyAssistIntelBot/0.3)"},
                    )
                    if ddg.status_code == 200:
                        p, m = self._parse_duckduckgo(ddg.text, query)
                        platforms.extend(p)
                        mentions.extend(m)
                except Exception:
                    pass

                # 2) Bing fallback
                try:
                    bing = client.get(
                        "https://www.bing.com/search",
                        params={"q": query, "setlang": "ru"},
                        headers={"User-Agent": "Mozilla/5.0 (StudyAssistIntelBot/0.3)"},
                    )
                    if bing.status_code == 200:
                        p, m = self._parse_bing(bing.text, query)
                        platforms.extend(p)
                        mentions.extend(m)
                except Exception:
                    pass

        return CollectResult(platforms=platforms, mentions=mentions)
