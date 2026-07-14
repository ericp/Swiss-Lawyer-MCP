"""SQLAlchemy ORM models for user memory and procedure progress."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.memory.database import Base


def uuid_str() -> str:
    """Return a UUID string for primary keys."""

    return str(uuid4())


def utc_now() -> datetime:
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc)


class UserORM(Base):
    """User record without authentication details."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    external_user_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    profile_facts: Mapped[list[UserProfileFactORM]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    procedures: Mapped[list[ProcedureORM]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class UserProfileFactORM(Base):
    """Flexible user profile fact keyed by field name."""

    __tablename__ = "user_profile_facts"
    __table_args__ = (
        UniqueConstraint("user_id", "field_name", name="uq_user_profile_facts_user_field"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value_json: Mapped[object] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    user: Mapped[UserORM] = relationship(back_populates="profile_facts")


class ProcedureORM(Base):
    """Saved procedure workflow and progress."""

    __tablename__ = "procedures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intent: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    current_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[UserORM] = relationship(back_populates="procedures")
    interactions: Mapped[list[ProcedureInteractionORM]] = relationship(
        back_populates="procedure",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ProcedureInteractionORM(Base):
    """Concise interaction summary for a procedure."""

    __tablename__ = "procedure_interactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    procedure_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("procedures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    interaction_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    structured_payload_json: Mapped[object | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    procedure: Mapped[ProcedureORM] = relationship(back_populates="interactions")


class SynchronizedSourceORM(Base):
    """Synchronization state for one approved or seeded source."""

    __tablename__ = "synchronized_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    authority: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    local_path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    document_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_successful_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="never_synced", index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    events: Mapped[list[SynchronizationEventORM]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SynchronizationRunORM(Base):
    """One synchronizer run summary."""

    __tablename__ = "synchronization_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_scope: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="running", index=True)
    checked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discovered_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    events: Mapped[list[SynchronizationEventORM]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class SynchronizationEventORM(Base):
    """Detailed synchronization event."""

    __tablename__ = "synchronization_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("synchronization_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("synchronized_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    old_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    run: Mapped[SynchronizationRunORM] = relationship(back_populates="events")
    source: Mapped[SynchronizedSourceORM | None] = relationship(back_populates="events")


class SourceCandidateORM(Base):
    """Discovered source candidate awaiting review."""

    __tablename__ = "source_candidates"
    __table_args__ = (
        UniqueConstraint("canonical_url", "region", name="uq_source_candidates_url_region"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    discovered_from_source_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    candidate_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    detected_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    inferred_procedure_types_json: Mapped[object] = mapped_column(JSON, nullable=False, default=list)
    relevance_score: Mapped[float | None] = mapped_column(nullable=True)
    discovery_reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
