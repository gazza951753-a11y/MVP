"""Base HTTP client with rate-limit-aware exponential backoff.

Implements RFC-compliant handling of:
- HTTP 429 (Too Many Requests) with optional ``Retry-After`` header
- 5xx transient errors
- Network-level failures (timeout, connection error)

All sub-classes inherit ``request_with_backoff`` and can override
``_build_headers`` to add auth tokens.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_BACKOFF = 60.0
_JITTER_FACTOR = 0.25  # ±25 % jitter


class RateLimitedClient:
    def __init__(self, timeout: float = 15.0, max_retries: int = 5):
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(timeout=timeout)

    # ---------------------------------------------------------------------- #
    # Override in sub-classes                                                  #
    # ---------------------------------------------------------------------- #

    def _build_headers(self) -> dict[str, str]:
        return {}

    # ---------------------------------------------------------------------- #
    # Core request logic                                                       #
    # ---------------------------------------------------------------------- #

    def request_with_backoff(
        self,
        method: str,
        url: str,
        *,
        raise_on_error: bool = False,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute *method* request, retrying on retryable status codes.

        Args:
            method: HTTP verb (``"GET"``, ``"POST"``, …).
            url: Target URL.
            raise_on_error: If ``True`` raise ``httpx.HTTPStatusError`` when
                all retries are exhausted on a retryable status.
            **kwargs: Forwarded to ``httpx.Client.request``.

        Returns:
            The last received ``httpx.Response``.
        """
        headers = {**self._build_headers(), **kwargs.pop("headers", {})}
        backoff = 1.0
        response: httpx.Response | None = None

        for attempt in range(self.max_retries):
            try:
                response = self._client.request(method, url, headers=headers, **kwargs)
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                logger.warning("Network error on attempt %d/%d for %s: %s", attempt + 1, self.max_retries, url, exc)
                if attempt == self.max_retries - 1:
                    raise
                self._sleep_backoff(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF)
                continue

            if response.status_code not in _RETRYABLE_STATUS:
                return response

            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait = float(retry_after)
            else:
                wait = backoff

            logger.warning(
                "HTTP %d on attempt %d/%d for %s — sleeping %.1fs",
                response.status_code,
                attempt + 1,
                self.max_retries,
                url,
                wait,
            )

            if attempt < self.max_retries - 1:
                self._sleep_backoff(wait)
                backoff = min(backoff * 2, _MAX_BACKOFF)

        if raise_on_error and response is not None and response.status_code in _RETRYABLE_STATUS:
            response.raise_for_status()

        return response  # type: ignore[return-value]

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request_with_backoff("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request_with_backoff("POST", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request_with_backoff("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request_with_backoff("DELETE", url, **kwargs)

    # ---------------------------------------------------------------------- #
    # Helpers                                                                  #
    # ---------------------------------------------------------------------- #

    @staticmethod
    def _sleep_backoff(base_seconds: float) -> None:
        jitter = base_seconds * _JITTER_FACTOR * (random.random() * 2 - 1)
        time.sleep(max(0.1, base_seconds + jitter))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RateLimitedClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
