"""Airtable integration client.

Rate limits (official docs):
- 5 requests/second per base
- 50 requests/second across all bases per personal access token
- HTTP 429 → wait 30 seconds before retrying

We honour ``Retry-After`` and default to 30 s when the header is absent.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.config import settings
from app.integrations.base_client import RateLimitedClient

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.airtable.com/v0"
_AIRTABLE_429_DEFAULT_WAIT = 30.0


class AirtableClient(RateLimitedClient):
    """Client for Airtable REST API v0.

    Usage::

        client = AirtableClient()
        records = client.list_records("Tasks")
        client.create_record("Tasks", {"Status": "new", "URL": "https://..."})
    """

    def __init__(self) -> None:
        super().__init__(timeout=settings.request_timeout_seconds, max_retries=settings.max_retries)
        self._pat = settings.airtable_pat
        self._base_id = settings.airtable_base_id
        self._last_request_at: float = 0.0
        self._min_interval = 0.21  # ~5 rps safety margin

    def _build_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._pat}", "Content-Type": "application/json"}

    def _throttle(self) -> None:
        """Enforce minimum inter-request gap to stay under 5 rps."""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_at = time.monotonic()

    def _table_url(self, table_name: str) -> str:
        return f"{_BASE_URL}/{self._base_id}/{table_name}"

    # ---------------------------------------------------------------------- #
    # Public methods                                                           #
    # ---------------------------------------------------------------------- #

    def list_records(
        self,
        table_name: str,
        *,
        filter_formula: str | None = None,
        max_records: int = 100,
    ) -> list[dict]:
        """Return records from *table_name*, handling pagination automatically."""
        if not self._pat or not self._base_id:
            logger.warning("Airtable PAT or base_id not configured — skipping list_records")
            return []

        records: list[dict] = []
        offset: str | None = None
        url = self._table_url(table_name)

        while True:
            params: dict[str, Any] = {"pageSize": min(100, max_records - len(records))}
            if filter_formula:
                params["filterByFormula"] = filter_formula
            if offset:
                params["offset"] = offset

            self._throttle()
            resp = self.get(url, params=params)

            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After") or _AIRTABLE_429_DEFAULT_WAIT)
                logger.warning("Airtable 429; sleeping %.0f s", wait)
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()
            records.extend(data.get("records", []))

            offset = data.get("offset")
            if not offset or len(records) >= max_records:
                break

        return records[:max_records]

    def create_record(self, table_name: str, fields: dict) -> dict | None:
        """Create a single record; returns created record dict or None on error."""
        if not self._pat or not self._base_id:
            logger.warning("Airtable not configured — skipping create_record")
            return None

        self._throttle()
        resp = self.post(self._table_url(table_name), json={"fields": fields})

        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After") or _AIRTABLE_429_DEFAULT_WAIT)
            logger.warning("Airtable 429 on create; sleeping %.0f s then retrying once", wait)
            time.sleep(wait)
            self._throttle()
            resp = self.post(self._table_url(table_name), json={"fields": fields})

        if resp.status_code not in (200, 201):
            logger.error("Airtable create_record failed: %d %s", resp.status_code, resp.text[:200])
            return None

        return resp.json()

    def update_record(self, table_name: str, record_id: str, fields: dict) -> dict | None:
        """PATCH a single record by Airtable record ID."""
        if not self._pat or not self._base_id:
            logger.warning("Airtable not configured — skipping update_record")
            return None

        url = f"{self._table_url(table_name)}/{record_id}"
        self._throttle()
        resp = self.patch(url, json={"fields": fields})

        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After") or _AIRTABLE_429_DEFAULT_WAIT)
            time.sleep(wait)
            self._throttle()
            resp = self.patch(url, json={"fields": fields})

        if resp.status_code != 200:
            logger.error("Airtable update_record failed: %d %s", resp.status_code, resp.text[:200])
            return None

        return resp.json()

    def upsert_task(self, task: dict) -> dict | None:
        """Push a task dict to Airtable Tasks table (create or update by task_id)."""
        table = settings.airtable_tasks_table
        task_id = str(task.get("id", ""))

        existing = self.list_records(table, filter_formula=f"{{task_id}}='{task_id}'", max_records=1)
        fields = {
            "task_id": task_id,
            "task_type": task.get("task_type", ""),
            "status": task.get("status", "new"),
            "priority": task.get("priority", 3),
            "opportunity_score": task.get("opportunity_score", 0),
            "risk_score": task.get("risk_score", 0),
            "utm_campaign": task.get("utm_campaign", ""),
            "platform_url": task.get("platform_url", ""),
            "message_draft": task.get("message_draft", ""),
        }

        if existing:
            return self.update_record(table, existing[0]["id"], fields)
        return self.create_record(table, fields)
