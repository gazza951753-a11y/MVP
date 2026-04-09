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
        if "dzen.ru" in host or "pikabu.ru" in host or "habr.com" in host:
            return "forum_thread"
        return "web_page"

    def collect(self) -> CollectResult:
        platforms: list[dict] = []
        mentions: list[dict] = []

        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for query in settings.discovery_queries:
                resp = client.get(
                    "https://duckduckgo.com/html/",
                    params={"q": query, "kl": "ru-ru"},
                    headers={"User-Agent": "Mozilla/5.0 (StudyAssistIntelBot/0.2)"},
                )
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                result_items = soup.select(".result")
                for item in result_items[:20]:
                    a = item.select_one("a.result__a")
                    snippet = item.select_one(".result__snippet")
                    if not a or not a.get("href"):
                        continue

                    source_url = self._extract_real_url(a["href"])
                    title = a.get_text(" ", strip=True) or "Без названия"
                    text = snippet.get_text(" ", strip=True) if snippet else ""
                    ptype = self._platform_type(source_url)

                    platforms.append(
                        {
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
                            "discovery_source": f"duckduckgo:{query[:80]}",
                        }
                    )

                    mentions.append(
                        {
                            "platform_url": source_url,
                            "mention_type": "search_result",
                            "source_url": source_url,
                            "author_handle": None,
                            "published_at": None,
                            "text": f"{title}. {text}",
                            "raw_payload": {"query": query, "engine": "duckduckgo"},
                        }
                    )

        return CollectResult(platforms=platforms, mentions=mentions)
