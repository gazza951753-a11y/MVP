"""Real Telegram channel post collector.

Fetches public channel preview pages at ``https://t.me/s/<channel>`` — Telegram
serves these as static HTML without any login or API key required.

Parsed from each page:
- Channel title, description, subscriber count (from <meta> tags)
- Up to 30 most recent posts (text + timestamp + permalink)

Trigger-matching posts become Mention records; the channel itself becomes a
Platform record.

Rate limiting: 1.5 s between requests (Telegram is lenient with crawlers for
public preview pages but we stay polite).
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import CollectResult, Collector
from app.processing.classify_rules import detect_intents
from app.processing.normalize import canonicalize_url

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed list of Russian student/academic Telegram channels to monitor.
# Operators can update this list in Settings → Источники.
# All channels listed here are public and indexed on t.me.
# ---------------------------------------------------------------------------
_DEFAULT_CHANNELS: list[str] = [
    "studizba",           # студенческая биржа
    "student_helper_ru",  # помощь студентам
    "diplomchik_help",    # дипломные работы
    "kursovik_help",      # курсовые
    "nauka_pomoshch",     # научные работы
    "antiplagiat_help",   # антиплагиат
    "vkr_diplom",         # ВКР и дипломы
    "referat_kursovaya",  # рефераты и курсовые
    "student_rf",         # студенты РФ
    "ucheba_legko",       # учёба легко
]


def _load_channels_from_settings() -> list[str]:
    """Read operator-configured channel list from settings.json if present."""
    try:
        raw = os.environ.get("APPDATA") or str(Path.home() / ".config")
        p = Path(raw) / "StudyAssist" / "settings.json"
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            raw_channels = data.get("tg_channels", "")
            if raw_channels:
                channels = [c.strip().lstrip("@") for c in raw_channels.splitlines() if c.strip()]
                if channels:
                    return channels
    except Exception as exc:
        logger.debug("Could not load channels from settings: %s", exc)
    return _DEFAULT_CHANNELS

_PREVIEW_URL = "https://t.me/s/{channel}"
_MIN_DELAY = 1.5  # seconds between requests


class TgChannelCollector(Collector):
    """Scan public Telegram channel preview pages for trigger-matching posts."""

    name = "tg_channel"

    def __init__(self, channels: list[str] | None = None) -> None:
        self._channels = channels or _load_channels_from_settings()
        self._client = httpx.Client(
            timeout=httpx.Timeout(connect=8.0, read=20.0, write=5.0, pool=5.0),
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "ru-RU,ru;q=0.9",
            },
            follow_redirects=True,
        )

    def collect(self) -> CollectResult:
        platforms: list[dict] = []
        mentions: list[dict] = []

        for channel in self._channels:
            plat, posts = self._scan_channel(channel)
            if plat:
                platforms.append(plat)
                mentions.extend(posts)
            time.sleep(_MIN_DELAY)

        self._client.close()
        logger.info(
            "TgChannelCollector: %d channels → %d platforms, %d trigger mentions",
            len(self._channels), len(platforms), len(mentions),
        )
        return CollectResult(platforms=platforms, mentions=mentions)

    # ---------------------------------------------------------------------- #
    # Internal                                                                 #
    # ---------------------------------------------------------------------- #

    def _scan_channel(self, channel: str) -> tuple[dict | None, list[dict]]:
        """Fetch preview page and return (platform_dict, mention_list)."""
        url = _PREVIEW_URL.format(channel=channel)
        try:
            resp = self._client.get(url)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning("Network error fetching t.me/s/%s: %s", channel, exc)
            return None, []

        if resp.status_code == 404:
            logger.debug("Channel @%s not found (404)", channel)
            return None, []

        if resp.status_code != 200:
            logger.warning("t.me/s/%s returned HTTP %d", channel, resp.status_code)
            return None, []

        return self._parse(resp.text, channel)

    def _parse(self, html: str, channel: str) -> tuple[dict | None, list[dict]]:
        soup = BeautifulSoup(html, "html.parser")

        # ---- channel metadata -------------------------------------------- #
        title_el = soup.select_one("meta[property='og:title']")
        desc_el = soup.select_one("meta[property='og:description']")
        title = title_el["content"] if title_el else f"@{channel}"
        description = desc_el["content"] if desc_el else ""

        # subscriber count lives inside .tgme_page_extra or similar
        extra_el = soup.select_one(".tgme_page_extra")
        audience = _parse_number(extra_el.get_text() if extra_el else "")

        channel_url = canonicalize_url(f"https://t.me/{channel}")

        platform: dict = {
            "platform_type": "telegram_channel",
            "title": str(title)[:200],
            "url": channel_url,
            "handle": f"@{channel}",
            "description": str(description)[:500],
            "audience_size": audience,
            "language": "ru",
            "geo": "RU",
            "commercial_tolerance": 3,
            "risk_flags": {"ban_risk": False},
            "tags": ["student", "telegram"],
            "discovery_source": f"{self.name}:t.me/s/{channel}",
        }

        # ---- posts --------------------------------------------------------- #
        mentions: list[dict] = []
        messages = soup.select(".tgme_widget_message")

        for msg in messages[:30]:  # cap at 30 posts per channel
            text_el = msg.select_one(".tgme_widget_message_text")
            if not text_el:
                continue
            text = text_el.get_text(separator=" ", strip=True)
            if len(text) < 15:
                continue

            intents, _ = detect_intents(text)
            if not intents:
                continue  # only store posts that match our triggers

            # permalink
            link_el = msg.select_one("a.tgme_widget_message_date")
            post_url = link_el["href"] if link_el else channel_url

            # timestamp
            time_el = msg.select_one("time[datetime]")
            published_at: datetime | None = None
            if time_el:
                try:
                    published_at = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
                except ValueError:
                    published_at = datetime.now(timezone.utc)

            mentions.append({
                "platform_url": channel_url,
                "mention_type": "post",
                "source_url": canonicalize_url(str(post_url)),
                "author_handle": None,
                "published_at": published_at or datetime.now(timezone.utc),
                "text": text[:1000],
                "raw_payload": {"channel": channel, "collector": self.name},
            })

        logger.debug(
            "t.me/s/%s: parsed %d posts, %d matched triggers",
            channel, len(messages), len(mentions),
        )
        return platform, mentions


def _parse_number(text: str) -> int | None:
    """Extract first integer from a string like '12 400 subscribers'."""
    import re
    digits = re.sub(r"[^\d]", "", text.replace("\xa0", "").replace(" ", ""))
    return int(digits) if digits else None
