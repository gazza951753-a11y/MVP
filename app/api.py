from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.models import Mention, Platform, Task
from app.pipeline import run_discovery

router = APIRouter(prefix="/api", tags=["api"])


class TaskStatusUpdate(BaseModel):
    status: str


@router.get("/platforms")
def get_platforms(limit: int = 100) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(select(Platform).order_by(Platform.created_at.desc()).limit(limit)).scalars().all()
    return [
        {
            "id": str(p.id),
            "title": p.title,
            "platform_type": p.platform_type,
            "url": p.url,
            "audience_size": p.audience_size,
            "commercial_tolerance": p.commercial_tolerance,
        }
        for p in rows
    ]


@router.get("/mentions")
def get_mentions(limit: int = 100) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(select(Mention).order_by(Mention.collected_at.desc()).limit(limit)).scalars().all()
    return [
        {
            "id": str(m.id),
            "platform_id": str(m.platform_id),
            "source_url": m.source_url,
            "text": m.text,
            "detected_intents": m.detected_intents,
            "trigger_hits": m.trigger_hits,
        }
        for m in rows
    ]


@router.get("/tasks")
def get_tasks(limit: int = 100) -> list[dict]:
    with SessionLocal() as session:
        rows = session.execute(select(Task).order_by(Task.created_at.desc()).limit(limit)).scalars().all()
    return [
        {
            "id": str(t.id),
            "task_type": t.task_type,
            "status": t.status,
            "priority": t.priority,
            "opportunity_score": t.opportunity_score,
            "risk_score": t.risk_score,
            "recommended_action": t.recommended_action,
            "message_draft": t.message_draft,
            "utm_campaign": t.utm_campaign,
            "platform_id": str(t.platform_id),
            "mention_id": str(t.mention_id) if t.mention_id else None,
        }
        for t in rows
    ]


@router.post("/run/discovery")
def run_discovery_api() -> dict:
    return run_discovery()


@router.patch("/tasks/{task_id}/status")
def update_task_status(task_id: UUID, payload: TaskStatusUpdate) -> dict:
    with SessionLocal() as session:
        task = session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="task_not_found")
        task.status = payload.status
        session.add(task)
        session.commit()
        session.refresh(task)
    return {"id": str(task.id), "status": task.status}
