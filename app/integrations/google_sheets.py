"""Google Sheets integration client.

Uses the Sheets REST API v4 with a service-account JSON key for auth.
Rate limits:
- Read requests: 300 per minute per project
- Write requests: 300 per minute per project
- HTTP 429 → exponential backoff (as recommended by Google documentation)

We use a simple token-bucket: ≤4 rps steady state, with exponential backoff on 429.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from app.config import settings
from app.integrations.base_client import RateLimitedClient

logger = logging.getLogger(__name__)

_SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
_AUTH_URL = "https://oauth2.googleapis.com/token"
_MIN_INTERVAL = 0.25  # 4 rps


class GoogleSheetsClient(RateLimitedClient):
    """Append rows and read ranges from a Google Spreadsheet.

    Authentication uses a service-account JSON key.  The path or raw JSON is
    provided via ``settings.google_service_account_json``.

    Usage::

        client = GoogleSheetsClient()
        client.append_rows("Platforms!A:Z", [["id", "url", "score"], [...]])
        data = client.read_range("Tasks!A1:H100")
    """

    def __init__(self) -> None:
        super().__init__(timeout=settings.request_timeout_seconds, max_retries=settings.max_retries)
        self._spreadsheet_id = settings.google_spreadsheet_id
        self._sa_json = settings.google_service_account_json
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._last_request_at: float = 0.0

    # ---------------------------------------------------------------------- #
    # Auth                                                                    #
    # ---------------------------------------------------------------------- #

    def _load_sa_credentials(self) -> dict | None:
        if not self._sa_json:
            return None
        raw = self._sa_json.strip()
        if raw.startswith("{"):
            return json.loads(raw)
        path = Path(raw)
        if path.exists():
            return json.loads(path.read_text())
        logger.warning("google_service_account_json is set but not valid JSON or path")
        return None

    def _get_access_token(self) -> str | None:
        if self._access_token and time.monotonic() < self._token_expires_at - 60:
            return self._access_token

        creds = self._load_sa_credentials()
        if not creds:
            return None

        try:
            import jwt  # PyJWT

            now = int(time.time())
            claim = {
                "iss": creds["client_email"],
                "scope": "https://www.googleapis.com/auth/spreadsheets",
                "aud": _AUTH_URL,
                "iat": now,
                "exp": now + 3600,
            }
            signed = jwt.encode(claim, creds["private_key"], algorithm="RS256")
        except Exception as exc:
            logger.error("Failed to sign Google JWT: %s", exc)
            return None

        resp = self.post(
            _AUTH_URL,
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": signed},
        )
        if resp.status_code != 200:
            logger.error("Google token request failed: %d", resp.status_code)
            return None

        token_data = resp.json()
        self._access_token = token_data["access_token"]
        self._token_expires_at = time.monotonic() + token_data.get("expires_in", 3600)
        return self._access_token

    def _build_headers(self) -> dict[str, str]:
        token = self._get_access_token()
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        self._last_request_at = time.monotonic()

    def _call(self, method: str, path: str, **kwargs: Any) -> dict | None:
        if not self._spreadsheet_id or not self._sa_json:
            logger.warning("Google Sheets not configured — skipping %s", path)
            return None

        url = f"{_SHEETS_API}/{self._spreadsheet_id}{path}"
        self._throttle()
        resp = self.request_with_backoff(method, url, **kwargs)

        if resp.status_code == 429:
            logger.warning("Google Sheets 429; backing off")
            time.sleep(5.0)
            self._throttle()
            resp = self.request_with_backoff(method, url, **kwargs)

        if resp.status_code not in (200, 201):
            logger.error("Sheets %s %s failed: %d %s", method, path, resp.status_code, resp.text[:200])
            return None

        return resp.json()

    # ---------------------------------------------------------------------- #
    # Public methods                                                          #
    # ---------------------------------------------------------------------- #

    def read_range(self, range_: str) -> list[list[str]]:
        """Return values from *range_* (e.g. ``"Sheet1!A1:Z100"``)."""
        data = self._call("GET", f"/values/{range_}")
        if data is None:
            return []
        return data.get("values", [])

    def append_rows(self, range_: str, values: list[list[Any]]) -> dict | None:
        """Append *values* rows below existing data in *range_*."""
        return self._call(
            "POST",
            f"/values/{range_}:append",
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            json={"values": values},
        )

    def clear_range(self, range_: str) -> dict | None:
        return self._call("POST", f"/values/{range_}:clear")

    def export_platforms(self, platforms: list[dict]) -> None:
        """Write platform rows to ``Platforms`` sheet (overwrite)."""
        sheet = "Platforms!A1"
        header = ["id", "platform_type", "title", "url", "audience_size", "commercial_tolerance",
                  "opportunity_score", "risk_score"]
        rows = [header] + [
            [
                str(p.get("id", "")),
                p.get("platform_type", ""),
                p.get("title", ""),
                p.get("url", ""),
                p.get("audience_size", ""),
                p.get("commercial_tolerance", ""),
                p.get("opportunity_score", ""),
                p.get("risk_score", ""),
            ]
            for p in platforms
        ]
        self.clear_range(sheet)
        self.append_rows(sheet, rows)

    def export_tasks(self, tasks: list[dict]) -> None:
        """Write task rows to ``Tasks`` sheet."""
        sheet = "Tasks!A1"
        header = ["id", "task_type", "status", "priority", "opportunity_score", "risk_score", "utm_campaign"]
        rows = [header] + [
            [
                str(t.get("id", "")),
                t.get("task_type", ""),
                t.get("status", ""),
                t.get("priority", ""),
                t.get("opportunity_score", ""),
                t.get("risk_score", ""),
                t.get("utm_campaign", ""),
            ]
            for t in tasks
        ]
        self.clear_range(sheet)
        self.append_rows(sheet, rows)
