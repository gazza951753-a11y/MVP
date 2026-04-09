"""Telegram channel/group catalog collector.

Discovery strategy:
1. Query a configurable list of seed search URLs (e.g. tgstat.ru search).
2. Parse channel cards from HTML (title, description, subscriber count, URL).
3. Return CollectResult with platform dicts (no auth required for public pages).

Rate limiting & ethics:
- Enforces minimum 2 s delay between requests to the catalog site.
- Detects 429 / CAPTCHA signals and stops collection, returning a partial result
  so the caller can create an ``investigate_access`` task.
- Does NOT log in, bypass CAPTCHA, or use credentials on third-party sites.
"""
from __future__ import annotations

import logging
import re
import time
from urllib.parse import urljoin, urlparse

import httpx

from app.collectors.base import CollectResult, Collector
from app.config import settings
from app.processing.normalize import canonicalize_url

logger = logging.getLogger(__name__)

# Public search endpoints — operators can extend via config/DB
_SEED_SEARCH_URLS: list[str] = [
    "https://tgstat.ru/search?q=%D0%BA%D1%83%D1%80%D1%81%D0%BE%D0%B2%D0%B0%D1%8F&category=education",
    "https://tgstat.ru/search?q=%D0%B4%D0%B8%D0%BF%D0%BB%D0%BE%D0%BC&category=education",
    "https://tgstat.ru/search?q=%D0%B0%D0%BD%D1%82%D0%B8%D0%BF%D0%BB%D0%B0%D0%B3%D0%B8%D0%B0%D1%82",
]

_CHANNEL_CARD_RE = re.compile(
    r'href="(/channel/@?[\w]+)"[^>]*>.*?<div[^>]*class="[^"]*peer-title[^"]*"[^>]*>(.*?)</div>'
    r'.*?<div[^>]*class="[^"]*members-count[^"]*"[^>]*>([\d\s,]+)',
    re.DOTALL,
)
_HANDLE_RE = re.compile(r"t\.me/(@?[\w]+)", re.IGNORECASE)
_DESCRIPTION_RE = re.compile(r'<div[^>]*class="[^"]*channel-description[^"]*"[^>]*>(.*?)</div>', re.DOTALL)
_MIN_REQUEST_DELAY = 2.0  # seconds between requests


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_subscriber_count(raw: str) -> int | None:
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


class TgCatalogCollector(Collector):
    """Scrape public Telegram catalog pages to discover channels/groups.

    Stops gracefully on CAPTCHA or access-denial signals.
    """

    name = "tg_catalog"

    def __init__(self, search_urls: list[str] | None = None, max_pages: int | None = None) -> None:
        self._search_urls = search_urls or _SEED_SEARCH_URLS
        self._max_pages = max_pages or settings.discovery_max_pages
        self._client = httpx.Client(
            timeout=settings.request_timeout_seconds,
            headers={"User-Agent": "Mozilla/5.0 (compatible; StudyAssistBot/1.0; research)"},
            follow_redirects=True,
        )

    def collect(self) -> CollectResult:
        platforms: list[dict] = []
        blocked = False

        for search_url in self._search_urls[: self._max_pages]:
            result, should_stop = self._fetch_catalog_page(search_url)
            platforms.extend(result)
            if should_stop:
                blocked = True
                logger.warning("Catalog collection stopped early due to access restriction at %s", search_url)
                break
            time.sleep(_MIN_REQUEST_DELAY)

        if blocked:
            # Signal caller to create investigate_access task via empty mentions
            platforms.append(
                {
                    "platform_type": "telegram_catalog",
                    "title": "[ACCESS BLOCKED — investigate_access required]",
                    "url": "https://tgstat.ru/blocked",
                    "discovery_source": f"{self.name}:blocked",
                    "risk_flags": {"captcha_detected": True, "ban_risk": False},
                    "tags": ["investigate"],
                    "commercial_tolerance": 0,
                }
            )

        self._client.close()
        return CollectResult(platforms=platforms, mentions=[])

    def _fetch_catalog_page(self, url: str) -> tuple[list[dict], bool]:
        """Return (platforms, should_stop)."""
        try:
            resp = self._client.get(url)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning("Network error fetching %s: %s", url, exc)
            return [], False

        if resp.status_code == 429:
            logger.warning("Rate-limited (429) by catalog at %s", url)
            return [], True  # stop

        if resp.status_code in (403, 503):
            logger.warning("Access denied (%d) by catalog at %s", resp.status_code, url)
            return [], True  # likely CAPTCHA / block

        if resp.status_code != 200:
            logger.warning("Unexpected status %d for %s", resp.status_code, url)
            return [], False

        html = resp.text

        # Heuristic CAPTCHA detection
        if any(kw in html.lower() for kw in ("captcha", "cf-challenge", "blocked", "security check")):
            logger.warning("CAPTCHA/challenge detected at %s", url)
            return [], True

        return self._parse_channels(html, base_url=url), False

    def _parse_channels(self, html: str, base_url: str) -> list[dict]:
        platforms: list[dict] = []
        base_domain = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"

        for match in _CHANNEL_CARD_RE.finditer(html):
            relative_path, raw_title, raw_subs = match.groups()
            title = _strip_html(raw_title)
            audience = _parse_subscriber_count(raw_subs)

            # Extract t.me handle from the catalog link
            catalog_link = urljoin(base_domain, relative_path)
            handle_match = _HANDLE_RE.search(relative_path)
            handle = handle_match.group(1) if handle_match else None
            tg_url = f"https://t.me/{handle.lstrip('@')}" if handle else catalog_link

            if not title:
                continue

            platforms.append(
                {
                    "platform_type": "telegram_channel",
                    "title": title,
                    "url": canonicalize_url(tg_url),
                    "handle": f"@{handle.lstrip('@')}" if handle else None,
                    "audience_size": audience,
                    "language": "ru",
                    "geo": "RU",
                    "risk_flags": {"ban_risk": False},
                    "tags": ["student", "education"],
                    "commercial_tolerance": 2,
                    "discovery_source": f"{self.name}:{base_url[:60]}",
                }
            )

        return platforms
