from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.models import Competitor, Mention, Platform, Task

EXPORT_DIR = Path("export")
EXPORT_DIR.mkdir(exist_ok=True)


def export_platforms() -> None:
    with SessionLocal() as session:
        rows = session.execute(select(Platform)).scalars().all()
    with (EXPORT_DIR / "platforms.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "platform_type", "title", "url", "audience_size", "commercial_tolerance"])
        for p in rows:
            w.writerow([p.id, p.platform_type, p.title, p.url, p.audience_size, p.commercial_tolerance])


def export_mentions() -> None:
    with SessionLocal() as session:
        rows = session.execute(select(Mention)).scalars().all()
    with (EXPORT_DIR / "mentions.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "platform_id", "source_url", "detected_intents", "trigger_hits"])
        for m in rows:
            w.writerow([m.id, m.platform_id, m.source_url, m.detected_intents, m.trigger_hits])


def export_tasks() -> None:
    with SessionLocal() as session:
        rows = session.execute(select(Task)).scalars().all()
    with (EXPORT_DIR / "tasks.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "status", "task_type", "priority", "opportunity_score", "risk_score", "utm_campaign"])
        for t in rows:
            w.writerow([t.id, t.status, t.task_type, t.priority, t.opportunity_score, t.risk_score, t.utm_campaign])


def export_competitors() -> None:
    with SessionLocal() as session:
        rows = session.execute(select(Competitor)).scalars().all()
    with (EXPORT_DIR / "competitors.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "website_url", "category", "confidence"])
        for c in rows:
            w.writerow([c.id, c.name, c.website_url, c.category, c.confidence])


if __name__ == "__main__":
    export_platforms()
    export_competitors()
    export_mentions()
    export_tasks()
    print("Exports generated in ./export")
