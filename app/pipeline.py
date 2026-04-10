"""ETL pipeline: discovery and trigger-scan modes.

Modes
-----
discovery   Run all registered collectors; upsert platforms; score and task.
trigger_scan  Re-scan "active" platforms for new mentions (hot-path, frequent).

Design choices
--------------
- Single DB transaction per collector run (atomic: either all mentions/tasks
  for a batch commit, or none).
- Duplicate detection via ``fingerprint`` before any DB write.
- All HTTP errors (429, blocked) are recorded in the ``logs`` table and
  increment Prometheus counters for alerting.
- Blocking events (CAPTCHA, 403) create an ``investigate_access`` task so an
  operator can decide the next step — no automatic retry bypass.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.collectors.base import CollectResult, Collector
from app.collectors.sources.forums import ForumsCollector
from app.collectors.sources.mock_seed import MockSeedCollector
from app.collectors.sources.tg_catalog import TgCatalogCollector
from app.collectors.sources.tg_channel import TgChannelCollector
from app.collectors.sources.vk_public import VkPublicCollector
from app.db.base import SessionLocal
from app.db.models import Log, Mention, Platform, Task
from app.observability.metrics import (
    crawler_blocked_total,
    crawler_http_429_total,
    crawler_latency_seconds,
    crawler_requests_total,
    tasks_created_total,
)
from app.processing.classify_rules import detect_intents
from app.processing.dedupe import make_fingerprint
from app.processing.normalize import canonicalize_url
from app.processing.scoring import compute_confidence, compute_opportunity, compute_risk
from app.tasks.creator import build_task_payload

logger = logging.getLogger(__name__)

_DISCOVERY_COLLECTORS: list[type[Collector]] = [
    TgChannelCollector,   # public Telegram previews — no auth needed
    VkPublicCollector,    # VK groups — needs vk_access_token in .env
    ForumsCollector,      # forum pages — slow, use last
]

_utcnow = lambda: datetime.now(timezone.utc)  # noqa: E731


# --------------------------------------------------------------------------- #
# DB helpers                                                                   #
# --------------------------------------------------------------------------- #

def _db_log(
    session: Any,
    *,
    run_id: uuid.UUID,
    component: str,
    level: str,
    event: str,
    message: str,
    url: str | None = None,
    http_status: int | None = None,
    error_code: str | None = None,
    payload: dict | None = None,
) -> None:
    """Insert a structured log row; silently skips on error to keep pipeline alive."""
    try:
        log = Log(
            run_id=run_id,
            component=component,
            level=level,
            event=event,
            url=url,
            http_status=http_status,
            error_code=error_code,
            message=message,
            payload=payload,
        )
        session.add(log)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to write log row: %s", exc)


def _upsert_platform(session: Any, data: dict) -> Platform:
    """Insert platform or update existing row (matched by canonical URL).

    Works with both PostgreSQL (ON CONFLICT DO UPDATE) and SQLite
    (SELECT + INSERT/UPDATE pattern).
    """
    canonical_url = canonicalize_url(data["url"])
    safe_data = {k: v for k, v in data.items() if k != "url" and v is not None}

    dialect = session.bind.dialect.name  # type: ignore[union-attr]

    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(Platform)
            .values(url=canonical_url, **safe_data)
            .on_conflict_do_update(
                index_elements=["url"],
                set_={
                    "title": safe_data.get("title"),
                    "audience_size": safe_data.get("audience_size"),
                    "activity_last_seen_at": safe_data.get("activity_last_seen_at"),
                    "updated_at": _utcnow(),
                },
            )
            .returning(Platform)
        )
        return session.execute(stmt).scalar_one()

    # SQLite / generic: SELECT then INSERT or UPDATE
    existing = session.execute(
        select(Platform).where(Platform.url == canonical_url)
    ).scalar_one_or_none()

    if existing:
        for key, value in safe_data.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        existing.updated_at = _utcnow()
        return existing

    platform = Platform(url=canonical_url, **safe_data)
    session.add(platform)
    return platform


def _build_features(platform: Platform, intents: list[str], trigger_hits: dict) -> tuple[dict, dict]:
    """Build feature vectors for opportunity and risk scoring."""
    # Weighted confidence from trigger hits as demand signal
    demand_signal = min(100.0, sum(trigger_hits.values()) * 80) if trigger_hits else 40.0

    opportunity_features = {
        "relevance": 85 if intents else 35,
        "demand": demand_signal,
        "freshness": 75,
        "audience": min((platform.audience_size or 0) / 250, 100),
        "admin_reachability": 70 if platform.handle else 35,
        "competitor_presence": 55,
        "content_fit": 80 if (platform.language or "").lower() == "ru" else 40,
    }

    has_strict_rules = bool(
        platform.rules_text and any(kw in platform.rules_text.lower() for kw in ("запрещ", "не допускается", "no ads"))
    )
    captcha_blocked = bool((platform.risk_flags or {}).get("captcha_detected"))

    risk_features = {
        "rule_strictness": 75 if has_strict_rules else 30,
        "moderation_risk": 45,
        "spam_sensitivity": 55,
        "automation_barrier": 80 if captcha_blocked else 20,
        "reputation_risk": 30,
    }

    return opportunity_features, risk_features


# --------------------------------------------------------------------------- #
# Pipeline entry points                                                        #
# --------------------------------------------------------------------------- #

def _run_collector(collector: Collector, run_id: uuid.UUID) -> CollectResult:
    """Run a single collector, recording metrics and returning CollectResult."""
    start = time.monotonic()
    crawler_requests_total.labels(source=collector.name).inc()
    try:
        result = collector.collect()
    except Exception as exc:  # noqa: BLE001
        logger.error("Collector %s raised: %s", collector.name, exc, exc_info=True)
        crawler_blocked_total.labels(source=collector.name).inc()
        return CollectResult(platforms=[], mentions=[])
    finally:
        crawler_latency_seconds.labels(source=collector.name).observe(time.monotonic() - start)
    return result


def _process_result(session: Any, result: CollectResult, run_id: uuid.UUID) -> tuple[int, int, int]:
    """Process a CollectResult: upsert platforms, create mentions + tasks.

    Returns (platforms_seen, mentions_created, tasks_created).
    """
    platform_map: dict[str, Platform] = {}

    for pdata in result.platforms:
        try:
            platform = _upsert_platform(session, pdata)
            platform_map[canonicalize_url(pdata["url"])] = platform
        except Exception as exc:
            logger.warning("Failed to upsert platform %s: %s", pdata.get("url"), exc)

    session.flush()

    # Handle CAPTCHA-blocked platform signal
    for pdata in result.platforms:
        if (pdata.get("risk_flags") or {}).get("captcha_detected"):
            canonical = canonicalize_url(pdata["url"])
            platform = platform_map.get(canonical)
            if platform:
                task_payload = {
                    "task_type": "investigate_access",
                    "status": "new",
                    "priority": 4,
                    "opportunity_score": 0.0,
                    "risk_score": 80.0,
                    "recommended_action": "Доступ заблокирован/CAPTCHA. Проверьте и решите: перейти на API, снизить частоту или исключить источник.",
                    "message_draft": None,
                    "utm_campaign": None,
                }
                task = Task(platform_id=platform.id, **task_payload)
                session.add(task)
                session.flush()
                tasks_created_total.labels(task_type="investigate_access").inc()
                crawler_blocked_total.labels(source="pipeline").inc()
                _db_log(
                    session,
                    run_id=run_id,
                    component="pipeline",
                    level="WARN",
                    event="captcha_detected",
                    url=pdata["url"],
                    error_code="captcha",
                    message=f"CAPTCHA/block detected for {pdata['url']}; task created",
                )

    mentions_created = 0
    tasks_created = 0

    for m in result.mentions:
        platform_url = canonicalize_url(m.get("platform_url", ""))
        platform = platform_map.get(platform_url)
        if not platform:
            logger.debug("Platform not found for mention URL %s", platform_url)
            continue

        mention_text = m.get("text") or ""
        intents, trigger_hits = detect_intents(mention_text)
        fingerprint = make_fingerprint(mention_text, m["source_url"])

        exists = (
            session.execute(select(Mention).where(Mention.fingerprint == fingerprint)).scalar_one_or_none()
        )
        if exists:
            continue

        mention = Mention(
            platform_id=platform.id,
            mention_type=m.get("mention_type", "post"),
            source_url=canonicalize_url(m["source_url"]),
            author_handle=m.get("author_handle"),
            published_at=m.get("published_at"),
            text=mention_text,
            raw_payload=m.get("raw_payload", {}),
            fingerprint=fingerprint,
            detected_intents=intents,
            trigger_hits=trigger_hits,
        )
        session.add(mention)
        session.flush()
        mentions_created += 1

        opp_features, risk_features = _build_features(platform, intents, trigger_hits)
        opportunity = compute_opportunity(opp_features)
        risk = compute_risk(risk_features)
        compute_confidence(trigger_hits)

        task_payload = build_task_payload(platform.platform_type, intents, opportunity, risk)
        task = Task(platform_id=platform.id, mention_id=mention.id, **task_payload)
        session.add(task)
        session.flush()
        mention.created_task_id = task.id
        tasks_created += 1
        tasks_created_total.labels(task_type=task.task_type).inc()

    return len(result.platforms), mentions_created, tasks_created


def run_discovery() -> dict:
    """Full nightly discovery: all collectors → DB → tasks."""
    run_id = uuid.uuid4()
    totals = {"platforms_seen": 0, "mentions_created": 0, "tasks_created": 0}

    for collector_cls in _DISCOVERY_COLLECTORS:
        collector = collector_cls()
        result = _run_collector(collector, run_id)

        try:
            with SessionLocal() as session:
                p, m, t = _process_result(session, result, run_id)
                _db_log(
                    session,
                    run_id=run_id,
                    component=collector.name,
                    level="INFO",
                    event="collector_done",
                    message=f"platforms={p} mentions={m} tasks={t}",
                )
                session.commit()
        except Exception as exc:
            logger.error("Pipeline commit failed for %s: %s", collector.name, exc, exc_info=True)
            continue

        totals["platforms_seen"] += p
        totals["mentions_created"] += m
        totals["tasks_created"] += t

    return {**totals, "run_id": str(run_id)}


def run_trigger_scan() -> dict:
    """Frequent hot-path scan: real Telegram channel posts + mock seed."""
    run_id = uuid.uuid4()
    totals = {"platforms_seen": 0, "mentions_created": 0, "tasks_created": 0}

    for collector_cls in [TgChannelCollector, MockSeedCollector]:
        collector = collector_cls()
        result = _run_collector(collector, run_id)
        try:
            with SessionLocal() as session:
                p, m, t = _process_result(session, result, run_id)
                session.commit()
        except Exception as exc:
            logger.error("Trigger scan commit failed for %s: %s", collector.name, exc, exc_info=True)
            continue

        totals["platforms_seen"] += p
        totals["mentions_created"] += m
        totals["tasks_created"] += t

    return {**totals, "run_id": str(run_id)}
