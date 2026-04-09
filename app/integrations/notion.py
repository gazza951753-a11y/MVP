"""Notion integration client.

Rate limits (official docs):
- Average ~3 requests/second per integration
- HTTP 429 with ``Retry-After`` header → must respect it
- Recommended pattern: request queue / throttling

We enforce 350 ms minimum between calls (~2.8 rps) and honour ``Retry-After``.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings
from app.integrations.base_client import RateLimitedClient

logger = logging.getLogger(__name__)

_NOTION_VERSION = "2022-06-28"
_BASE_URL = "https://api.notion.com/v1"
_MIN_INTERVAL = 0.35  # 350 ms ≈ 2.85 rps safety margin


class NotionClient(RateLimitedClient):
    """Client for Notion API.

    Usage::

        client = NotionClient()
        client.create_page(database_id="...", properties={...})
        pages = client.query_database(database_id="...", filter_={...})
    """

    def __init__(self) -> None:
        super().__init__(timeout=settings.request_timeout_seconds, max_retries=settings.max_retries)
        self._token = settings.notion_token
        self._last_request_at: float = 0.0

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        self._last_request_at = time.monotonic()

    def _call(self, method: str, path: str, **kwargs: Any) -> dict | None:
        if not self._token:
            logger.warning("Notion token not configured — skipping %s %s", method, path)
            return None

        url = f"{_BASE_URL}{path}"
        self._throttle()
        resp = self.request_with_backoff(method, url, **kwargs)

        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After", "2"))
            logger.warning("Notion 429; sleeping %.1f s", wait)
            time.sleep(wait)
            self._throttle()
            resp = self.request_with_backoff(method, url, **kwargs)

        if resp.status_code not in (200, 201):
            logger.error("Notion %s %s failed: %d %s", method, path, resp.status_code, resp.text[:300])
            return None

        return resp.json()

    # ---------------------------------------------------------------------- #
    # Public methods                                                           #
    # ---------------------------------------------------------------------- #

    def create_page(self, database_id: str, properties: dict, *, children: list | None = None) -> dict | None:
        """Create a page inside *database_id* with the given *properties*."""
        body: dict[str, Any] = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }
        if children:
            body["children"] = children
        return self._call("POST", "/pages", json=body)

    def update_page(self, page_id: str, properties: dict) -> dict | None:
        return self._call("PATCH", f"/pages/{page_id}", json={"properties": properties})

    def query_database(
        self,
        database_id: str,
        *,
        filter_: dict | None = None,
        sorts: list | None = None,
        page_size: int = 100,
    ) -> list[dict]:
        """Return all pages from a database, handling pagination."""
        results: list[dict] = []
        body: dict[str, Any] = {"page_size": min(page_size, 100)}
        if filter_:
            body["filter"] = filter_
        if sorts:
            body["sorts"] = sorts

        start_cursor: str | None = None

        while True:
            if start_cursor:
                body["start_cursor"] = start_cursor

            data = self._call("POST", f"/databases/{database_id}/query", json=body)
            if data is None:
                break

            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            start_cursor = data.get("next_cursor")

        return results

    def upsert_task(self, task: dict) -> dict | None:
        """Push task to Notion Tasks DB (create or update by task_id property)."""
        db_id = settings.notion_tasks_db_id
        if not db_id:
            logger.warning("notion_tasks_db_id not configured")
            return None

        task_id = str(task.get("id", ""))

        # Check for existing page
        existing = self.query_database(
            db_id,
            filter_={"property": "task_id", "rich_text": {"equals": task_id}},
            page_size=1,
        )

        def _props(t: dict) -> dict:
            return {
                "task_id": {"rich_text": [{"text": {"content": str(t.get("id", ""))}}]},
                "Status": {"select": {"name": t.get("status", "new")}},
                "Type": {"select": {"name": t.get("task_type", "watch_only")}},
                "Priority": {"number": t.get("priority", 3)},
                "Opportunity": {"number": t.get("opportunity_score", 0)},
                "Risk": {"number": t.get("risk_score", 0)},
                "UTM": {"rich_text": [{"text": {"content": t.get("utm_campaign", "")}}]},
                "Platform URL": {"url": t.get("platform_url") or None},
            }

        if existing:
            return self.update_page(existing[0]["id"], _props(task))
        return self.create_page(db_id, _props(task))
