"""Pydantic models and enums for synchronization."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SyncSourceStatus(str, Enum):
    NEVER_SYNCED = "never_synced"
    UNCHANGED = "unchanged"
    UPDATED = "updated"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"
    MANUALLY_SEEDED = "manually_seeded"


class SyncRunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class SyncEventType(str, Enum):
    CHECK_STARTED = "check_started"
    UNCHANGED = "unchanged"
    DOWNLOADED = "downloaded"
    VALIDATED = "validated"
    INDEXED = "indexed"
    UPDATED = "updated"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"
    CANDIDATE_DISCOVERED = "candidate_discovered"
    CANDIDATE_APPROVED = "candidate_approved"
    CANDIDATE_REJECTED = "candidate_rejected"


class CandidateStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    INVALID = "invalid"


class ChangeStatus(str, Enum):
    UNCHANGED = "unchanged"
    CHANGED = "changed"
    NEW = "new"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class SynchronizationReport(BaseModel):
    """Summary returned by synchronization commands."""

    run_id: str
    requested_scope: str
    status: SyncRunStatus
    checked_count: int = 0
    unchanged_count: int = 0
    updated_count: int = 0
    failed_count: int = 0
    discovered_candidate_count: int = 0
    events: list[str] = Field(default_factory=list)


class CandidateRecord(BaseModel):
    """Candidate source awaiting review."""

    id: str
    discovered_from_source_id: str
    region: str
    candidate_url: str
    canonical_url: str
    detected_title: str | None = None
    detected_content_type: str | None = None
    inferred_procedure_types: list[str] = Field(default_factory=list)
    relevance_score: float | None = None
    discovery_reason: str
    status: CandidateStatus
    discovered_at: datetime
    reviewed_at: datetime | None = None
    review_note: str | None = None


class NormalizedWebDocument(BaseModel):
    """Persisted normalized webpage document."""

    document_id: str
    source_id: str
    title: str | None = None
    official_url: str
    region: str
    authority: str
    language: str
    retrieved_at: datetime
    content_sha256: str
    content: str
    sections: list[str]
    metadata: dict[str, Any] = Field(default_factory=dict)
