"""VK (ВКонтакте) public pages / communities collector.

Uses the official VK API (groups.search + wall.get) with a service access token.
No user authentication or private data is accessed.

Rate limits: VK API recommends ≤3 requests/second per token; excessive calls
return error code 6 ("too many requests").  We enforce 400 ms between calls.

API docs: https://dev.vk.com/api/api-requests
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.collectors.base import CollectResult, Collector
from app.config import settings
from app.processing.normalize import canonicalize_url

logger = logging.getLogger(__name__)

_VK_API_BASE = "https://api.vk.com/method"
_MIN_INTERVAL = 0.4  # ~2.5 rps safety margin

_SEARCH_QUERIES = [
    "курсовые работы",
    "помощь студентам",
    "антиплагиат диплом",
    "ВКР оформление",
    "учебные работы на заказ",
]


class VkPublicCollector(Collector):
    """Discover VK public groups related to student-help / academic services."""

    name = "vk_public"

    def __init__(self, queries: list[str] | None = None) -> None:
        self._token = settings.vk_access_token
        self._v = settings.vk_api_version
        self._queries = queries or _SEARCH_QUERIES
        self._last_request_at: float = 0.0
        self._client = httpx.Client(timeout=settings.request_timeout_seconds, follow_redirects=True)

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        self._last_request_at = time.monotonic()

    def _call(self, method: str, params: dict[str, Any]) -> dict | None:
        if not self._token:
            logger.warning("vk_access_token not configured — VK collector is a no-op")
            return None

        self._throttle()
        params = {**params, "access_token": self._token, "v": self._v}
        try:
            resp = self._client.get(f"{_VK_API_BASE}/{method}", params=params)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning("VK network error [%s]: %s", method, exc)
            return None

        if resp.status_code == 429:
            logger.warning("VK API 429; sleeping 5 s")
            time.sleep(5.0)
            return None

        if resp.status_code != 200:
            logger.warning("VK API %s returned HTTP %d", method, resp.status_code)
            return None

        data = resp.json()
        if "error" in data:
            code = data["error"].get("error_code")
            msg = data["error"].get("error_msg", "")
            if code == 6:  # too many requests
                logger.warning("VK error 6 (too many requests); sleeping 1 s")
                time.sleep(1.0)
            else:
                logger.warning("VK API error %s: %d %s", method, code, msg)
            return None

        return data.get("response")

    def _search_groups(self, query: str) -> list[dict]:
        """Search for public groups matching *query*."""
        resp = self._call(
            "groups.search",
            {"q": query, "type": "group,page", "count": 20, "sort": 6},  # sort=6 → by members
        )
        if not resp:
            return []
        return resp.get("items", [])

    def _group_to_platform(self, group: dict) -> dict:
        screen_name = group.get("screen_name", "")
        url = canonicalize_url(f"https://vk.com/{screen_name}" if screen_name else f"https://vk.com/club{group['id']}")
        return {
            "platform_type": "vk_group",
            "title": group.get("name", ""),
            "url": url,
            "handle": screen_name or None,
            "description": group.get("description", "")[:500] if group.get("description") else None,
            "audience_size": group.get("members_count"),
            "language": "ru",
            "geo": "RU",
            "risk_flags": {"ban_risk": False, "verified": bool(group.get("verified"))},
            "tags": ["student", "vk"],
            "commercial_tolerance": 2,
            "discovery_source": f"{self.name}:groups.search",
        }

    def collect(self) -> CollectResult:
        if not self._token:
            logger.info("VK token not set; returning empty CollectResult")
            self._client.close()
            return CollectResult(platforms=[], mentions=[])

        seen_ids: set[int] = set()
        platforms: list[dict] = []

        for query in self._queries:
            groups = self._search_groups(query)
            for g in groups:
                gid = g.get("id")
                if gid and gid not in seen_ids:
                    seen_ids.add(gid)
                    platforms.append(self._group_to_platform(g))

        self._client.close()
        logger.info("VK collector found %d unique groups", len(platforms))
        return CollectResult(platforms=platforms, mentions=[])
