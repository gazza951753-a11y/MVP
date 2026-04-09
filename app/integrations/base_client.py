from __future__ import annotations

import time

import httpx


class RateLimitedClient:
    def __init__(self, timeout: float = 15.0):
        self.client = httpx.Client(timeout=timeout)

    def request_with_backoff(self, method: str, url: str, **kwargs) -> httpx.Response:
        backoff = 1.0
        for attempt in range(5):
            response = self.client.request(method, url, **kwargs)
            if response.status_code != 429:
                return response
            retry_after = response.headers.get("Retry-After")
            wait = float(retry_after) if retry_after and retry_after.isdigit() else backoff
            time.sleep(wait)
            backoff = min(backoff * 2, 30)
        return response
