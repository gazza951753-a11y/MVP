"""Generic HTTP forum / thread collector.

Scans configured seed URLs (forum threads, Q&A boards, comment sections) for
trigger-matching posts.  Returns mentions with extracted text and source URLs.

Ethics & safety:
- Uses a polite 1.5 s delay between requests.
- Stops on 403 / 429 / CAPTCHA and records an investigate_access signal.
- Does NOT use headless browser by default; falls back gracefully if JS content
  is not available in the static HTML.
- Does NOT collect author personal data beyond what is publicly visible in the
  post header (handle/nickname only).
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import CollectResult, Collector
from app.config import settings
from app.processing.classify_rules import detect_intents
from app.processing.dedupe import make_fingerprint
from app.processing.normalize import canonicalize_url

logger = logging.getLogger(__name__)

# Operators configure these seed URLs in config/DB; this is the baseline set
_SEED_FORUM_URLS: list[str] = [
    # Example: student Q&A boards and popular ru-student communities
    # Replace / extend with actual URLs relevant to the product
    "https://www.sql.ru/forum/education",  # placeholder – operators update
]

_MIN_DELAY = 1.5  # seconds between requests
_CAPTCHA_SIGNALS = ("captcha", "cf-challenge", "access denied", "blocked", "security check")


class ForumsCollector(Collector):
    """Scrape forum thread pages and extract posts with detected intents."""

    name = "forums"

    def __init__(self, seed_urls: list[str] | None = None) -> None:
        self._seed_urls = seed_urls or _SEED_FORUM_URLS
        self._client = httpx.Client(
            timeout=httpx.Timeout(connect=5.0, read=settings.request_timeout_seconds, write=5.0, pool=5.0),
            headers={"User-Agent": "Mozilla/5.0 (compatible; StudyAssistBot/1.0; research)"},
            follow_redirects=True,
        )

    def collect(self) -> CollectResult:
        platforms: list[dict] = []
        mentions: list[dict] = []

        for url in self._seed_urls:
            p, m, blocked = self._process_page(url)
            platforms.extend(p)
            mentions.extend(m)
            if blocked:
                logger.warning("Stopped forum collection at %s", url)
                platforms.append(self._blocked_platform(url))
                break
            time.sleep(_MIN_DELAY)

        self._client.close()
        return CollectResult(platforms=platforms, mentions=mentions)

    # ---------------------------------------------------------------------- #
    # Internal helpers                                                        #
    # ---------------------------------------------------------------------- #

    def _process_page(self, url: str) -> tuple[list[dict], list[dict], bool]:
        """Return (platforms, mentions, should_stop)."""
        try:
            resp = self._client.get(url)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning("Network error fetching %s: %s", url, exc)
            return [], [], False

        if resp.status_code in (429, 403):
            return [], [], True

        if resp.status_code != 200:
            logger.warning("Unexpected HTTP %d for %s", resp.status_code, url)
            return [], [], False

        html = resp.text
        if any(sig in html.lower() for sig in _CAPTCHA_SIGNALS):
            logger.warning("CAPTCHA/block signal at %s", url)
            return [], [], True

        platform = self._infer_platform(url, html)
        mentions = self._extract_mentions(html, url, platform["url"])
        return [platform], mentions, False

    def _infer_platform(self, url: str, html: str) -> dict:
        canonical = canonicalize_url(url)
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else canonical
        return {
            "platform_type": "forum_thread",
            "title": title[:200],
            "url": canonical,
            "language": "ru",
            "geo": "RU",
            "risk_flags": {"ban_risk": False},
            "tags": ["forum", "student"],
            "commercial_tolerance": 1,
            "discovery_source": f"{self.name}:seed",
        }

    def _extract_mentions(self, html: str, page_url: str, platform_url: str) -> list[dict]:
        """Extract posts from common forum HTML patterns."""
        soup = BeautifulSoup(html, "html.parser")
        mentions: list[dict] = []

        # Generic post-like containers (covers many forum engines)
        post_selectors = [
            "div.post-content",
            "div.message-body",
            "td.posttxt",
            "div.post_message",
            "article",
        ]

        posts: list = []
        for sel in post_selectors:
            posts = soup.select(sel)
            if posts:
                break

        # Fallback: all <p> tags with enough text
        if not posts:
            posts = [p for p in soup.find_all("p") if len(p.get_text(strip=True)) > 40]

        now = datetime.now(timezone.utc)

        for post in posts[:50]:  # cap at 50 posts per page
            text = post.get_text(separator=" ", strip=True)
            if len(text) < 20:
                continue

            intents, _ = detect_intents(text)
            if not intents:
                continue  # only store trigger-matching posts

            # Try to find a permalink anchor nearby
            anchor = post.find_parent("div", {"id": re.compile(r"post|msg|reply", re.I)})
            post_id = anchor.get("id", "") if anchor else ""
            source_url = canonicalize_url(f"{page_url}#{post_id}" if post_id else page_url)

            fingerprint = make_fingerprint(text, source_url)
            mentions.append(
                {
                    "platform_url": platform_url,
                    "mention_type": "post",
                    "source_url": source_url,
                    "author_handle": None,
                    "published_at": now,
                    "text": text[:1000],
                    "raw_payload": {"page_url": page_url, "collector": self.name},
                }
            )

        return mentions

    @staticmethod
    def _blocked_platform(url: str) -> dict:
        return {
            "platform_type": "forum_thread",
            "title": f"[ACCESS BLOCKED] {url[:80]}",
            "url": canonicalize_url(url),
            "risk_flags": {"captcha_detected": True, "ban_risk": False},
            "tags": ["investigate"],
            "commercial_tolerance": 0,
            "discovery_source": "forums:blocked",
        }
