from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Competitor(Base, TimestampMixin):
    __tablename__ = "competitors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    website_url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), default="student_help_service")
    geo: Mapped[str | None] = mapped_column(String(8))
    pricing_model: Mapped[str | None] = mapped_column(String(64))
    offer_summary: Mapped[str | None] = mapped_column(Text)
    discovered_from: Mapped[str] = mapped_column(String(64), default="seed")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)


class Platform(Base, TimestampMixin):
    __tablename__ = "platforms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    handle: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(8))
    geo: Mapped[str | None] = mapped_column(String(8))
    audience_size: Mapped[int | None] = mapped_column(Integer)
    activity_last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rules_text: Mapped[str | None] = mapped_column(Text)
    commercial_tolerance: Mapped[int] = mapped_column(Integer, default=0)
    risk_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    discovery_source: Mapped[str] = mapped_column(String(128), default="manual")

    mentions: Mapped[list[Mention]] = relationship(back_populates="platform")


class Mention(Base):
    __tablename__ = "mentions"
    __table_args__ = (UniqueConstraint("source_url", "fingerprint", name="uq_mention_source_fingerprint"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platforms.id"), nullable=False)
    competitor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("competitors.id"))
    mention_type: Mapped[str] = mapped_column(String(32), default="post")
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    author_handle: Mapped[str | None] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    text: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    detected_intents: Mapped[list[str]] = mapped_column(JSON, default=list)
    trigger_hits: Mapped[dict] = mapped_column(JSON, default=dict)
    created_task_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tasks.id"))

    platform: Mapped[Platform] = relationship(back_populates="mentions")


class Trigger(Base):
    __tablename__ = "triggers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    regex_patterns: Mapped[list[str]] = mapped_column(JSON, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    negative_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class AdminContact(Base):
    __tablename__ = "admin_contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platforms.id"), nullable=False)
    contact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    contact_value: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="operator")
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="new")
    platform_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platforms.id"), nullable=False)
    mention_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("mentions.id"))
    priority: Mapped[int] = mapped_column(Integer, default=3)
    opportunity_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_action: Mapped[str | None] = mapped_column(Text)
    message_draft: Mapped[str | None] = mapped_column(Text)
    utm_campaign: Mapped[str | None] = mapped_column(String(255))
    operator_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewer_verdict: Mapped[str | None] = mapped_column(String(32))


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    component: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    http_status: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
