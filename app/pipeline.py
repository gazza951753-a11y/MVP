from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select

from app.collectors.base import Collector
from app.collectors.sources.mock_seed import MockSeedCollector
from app.collectors.sources.russian_web import RussianWebCollector
from app.config import settings
from app.db.base import SessionLocal
from app.db.models import Mention, Platform, Task
from app.observability.metrics import crawler_requests_total, tasks_created_total
from app.processing.classify_rules import detect_intents
from app.processing.dedupe import make_fingerprint
from app.processing.normalize import canonicalize_url
from app.processing.scoring import compute_confidence, compute_opportunity, compute_risk
from app.tasks.creator import build_task_payload


def clear_runtime_data() -> dict:
    with SessionLocal() as session:
        tasks_deleted = session.execute(delete(Task)).rowcount or 0
        mentions_deleted = session.execute(delete(Mention)).rowcount or 0
        platforms_deleted = session.execute(delete(Platform)).rowcount or 0
        session.commit()
    return {
        "tasks_deleted": tasks_deleted,
        "mentions_deleted": mentions_deleted,
        "platforms_deleted": platforms_deleted,
    }


def _upsert_platform(session, data: dict) -> Platform:
    canonical_url = canonicalize_url(data["url"])
    existing = session.execute(select(Platform).where(Platform.url == canonical_url)).scalar_one_or_none()
    if existing:
        for key, value in data.items():
            if hasattr(existing, key) and value is not None:
                setattr(existing, key, value)
        existing.url = canonical_url
        existing.updated_at = datetime.utcnow()
        return existing

    platform = Platform(**{**data, "url": canonical_url})
    session.add(platform)
    return platform


def _build_features(platform: Platform, intents: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    opportunity_features = {
        "relevance": 80 if intents else 40,
        "demand": 85 if "need_help" in intents or "urgent" in intents else 55,
        "freshness": 70,
        "audience": min((platform.audience_size or 0) / 300, 100),
        "admin_reachability": 70 if platform.handle else 40,
        "competitor_presence": 50,
        "content_fit": 75 if platform.language == "ru" else 45,
    }
    risk_features = {
        "rule_strictness": 65 if (platform.rules_text and "запрещ" in platform.rules_text.lower()) else 35,
        "moderation_risk": 45,
        "spam_sensitivity": 50,
        "automation_barrier": 20,
        "reputation_risk": 25,
    }
    return opportunity_features, risk_features


def _get_collectors() -> list[Collector]:
    collectors: list[Collector] = [RussianWebCollector()]
    if settings.use_mock_collector:
        collectors.append(MockSeedCollector())
    return collectors


def run_discovery() -> dict:
    collectors = _get_collectors()

    total_platforms_seen = 0
    total_mentions_seen = 0
    created_mentions = 0
    created_tasks = 0

    with SessionLocal() as session:
        platform_map: dict[str, Platform] = {}

        for collector in collectors:
            crawler_requests_total.labels(source=collector.name).inc()
            result = collector.collect()
            total_platforms_seen += len(result.platforms)
            total_mentions_seen += len(result.mentions)

            for pdata in result.platforms:
                platform = _upsert_platform(session, pdata)
                platform_map[platform.url] = platform

            session.flush()

            for m in result.mentions:
                platform_url = canonicalize_url(m["platform_url"])
                platform = platform_map.get(platform_url)
                if not platform:
                    platform = session.execute(select(Platform).where(Platform.url == platform_url)).scalar_one_or_none()
                    if not platform:
                        continue

                mention_text = m.get("text") or ""
                intents, trigger_hits = detect_intents(mention_text)
                fingerprint = make_fingerprint(mention_text, m["source_url"])

                exists = session.execute(select(Mention).where(Mention.fingerprint == fingerprint)).scalar_one_or_none()
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
                created_mentions += 1

                opp_features, risk_features = _build_features(platform, intents)
                opportunity = compute_opportunity(opp_features)
                risk = compute_risk(risk_features)
                _ = compute_confidence(trigger_hits)

                task_payload = build_task_payload(platform.platform_type, intents, opportunity, risk)
                task = Task(platform_id=platform.id, mention_id=mention.id, **task_payload)
                session.add(task)
                session.flush()
                mention.created_task_id = task.id
                created_tasks += 1
                tasks_created_total.labels(task_type=task.task_type).inc()

        session.commit()

    warning = None
    if total_platforms_seen == 0:
        warning = "Нет внешних результатов. Проверьте интернет/блокировки поисковиков и повторите запуск."

    return {
        "collectors": [c.name for c in collectors],
        "platforms_seen": total_platforms_seen,
        "mentions_seen": total_mentions_seen,
        "mentions_created": created_mentions,
        "tasks_created": created_tasks,
        "warning": warning,
    }
