"""Telegram Bot API client for **internal operator notifications only**.

This module is intentionally scoped to team-internal usage:
- Sends messages only to a pre-configured operator chat/group
- Does NOT implement mass outreach, broadcast, or contact with unknown users
- Respects Telegram Bot API rate limits:
  - ~1 message/second in the same chat
  - ~30 messages/second across all chats (global)
  - HTTP 429 → honour retry_after from API response

Sending unsolicited messages to unknown users or spamming groups violates
Telegram ToS and results in account restrictions.
"""
from __future__ import annotations

import logging
import time

from app.config import settings
from app.integrations.base_client import RateLimitedClient

logger = logging.getLogger(__name__)

_TGAPI = "https://api.telegram.org/bot{token}"
_MIN_INTERVAL = 1.1  # ~1 message/second per chat safety margin


class TelegramNotifyClient(RateLimitedClient):
    """Send structured operator notifications via Telegram Bot API.

    Only sends to ``settings.telegram_operator_chat_id`` — a pre-configured
    internal chat/group for the operations team.

    Usage::

        notifier = TelegramNotifyClient()
        notifier.send_task_alert(task)
        notifier.send_text("Discovery run complete: 5 platforms, 3 tasks")
    """

    def __init__(self) -> None:
        super().__init__(timeout=settings.request_timeout_seconds, max_retries=3)
        self._token = settings.telegram_bot_token
        self._chat_id = settings.telegram_operator_chat_id
        self._last_sent_at: float = 0.0

    def _api_url(self, method: str) -> str:
        return f"{_TGAPI.format(token=self._token)}/{method}"

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_sent_at
        if elapsed < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - elapsed)
        self._last_sent_at = time.monotonic()

    def _send(self, text: str, *, parse_mode: str = "HTML") -> bool:
        """Core send; returns True on success."""
        if not self._token or not self._chat_id:
            logger.debug("Telegram not configured — skipping notification")
            return False

        self._throttle()
        resp = self.post(
            self._api_url("sendMessage"),
            json={"chat_id": self._chat_id, "text": text, "parse_mode": parse_mode},
        )

        if resp.status_code == 429:
            data = resp.json()
            wait = data.get("parameters", {}).get("retry_after", 5)
            logger.warning("Telegram 429; sleeping %d s", wait)
            time.sleep(wait)
            self._throttle()
            resp = self.post(
                self._api_url("sendMessage"),
                json={"chat_id": self._chat_id, "text": text, "parse_mode": parse_mode},
            )

        if resp.status_code != 200:
            logger.error("Telegram sendMessage failed: %d %s", resp.status_code, resp.text[:200])
            return False

        return True

    # ---------------------------------------------------------------------- #
    # Public helpers                                                          #
    # ---------------------------------------------------------------------- #

    def send_text(self, message: str) -> bool:
        """Send a plain-text notification to the operator chat."""
        return self._send(message, parse_mode="HTML")

    def send_task_alert(self, task: dict) -> bool:
        """Format and send a new-task notification.

        *task* should contain: id, task_type, priority, opportunity_score,
        risk_score, platform_url (optional), utm_campaign.
        """
        emoji_priority = {5: "🔴", 4: "🟠", 3: "🟡", 2: "🟢", 1: "⚪"}.get(task.get("priority", 3), "")
        text = (
            f"{emoji_priority} <b>Новая задача [{task.get('task_type', '')}]</b>\n"
            f"Приоритет: {task.get('priority', '')} | "
            f"Opportunity: {task.get('opportunity_score', 0):.1f} | "
            f"Risk: {task.get('risk_score', 0):.1f}\n"
        )
        if task.get("platform_url"):
            text += f"Площадка: {task['platform_url']}\n"
        if task.get("utm_campaign"):
            text += f"UTM: {task['utm_campaign']}\n"
        if task.get("message_draft"):
            text += f"\n<i>Черновик:</i>\n{task['message_draft'][:300]}"

        return self._send(text)

    def send_discovery_summary(self, result: dict) -> bool:
        """Send a one-liner summary after a discovery run."""
        text = (
            f"✅ <b>Discovery завершён</b>\n"
            f"Площадок: {result.get('platforms_seen', 0)} | "
            f"Упоминаний: {result.get('mentions_created', 0)} | "
            f"Задач: {result.get('tasks_created', 0)}"
        )
        return self._send(text)

    def send_error_alert(self, component: str, message: str) -> bool:
        """Notify operators about a collector/pipeline error."""
        text = f"⚠️ <b>Ошибка [{component}]</b>\n{message[:500]}"
        return self._send(text)
