"""Repository layer for synchronization audit data."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.memory.models import (
    SourceCandidateORM,
    SynchronizationEventORM,
    SynchronizationRunORM,
    SynchronizedSourceORM,
    utc_now,
)
from backend.synchronizer.identifiers import document_id_for_source
from backend.synchronizer.models import (
    CandidateRecord,
    CandidateStatus,
    SyncEventType,
    SyncRunStatus,
    SyncSourceStatus,
)
from backend.synchronizer.source_registry import SourceDefinition


class SynchronizerRepository:
    """Persist synchronization source state, runs, events, and candidates."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert_source(self, source: SourceDefinition, *, local_path: str) -> SynchronizedSourceORM:
        existing = self.get_source_by_key(source.id)
        document_id = document_id_for_source(source.id, source.url)
        if existing is None:
            row = SynchronizedSourceORM(
                source_key=source.id,
                region=source.region,
                authority=source.authority,
                source_type=source.source_type,
                canonical_url=source.url,
                local_path=local_path,
                language=source.language,
                enabled=source.enabled,
                document_id=document_id,
                consecutive_failures=0,
                status=(
                    SyncSourceStatus.MANUALLY_SEEDED.value
                    if source.source_type == "local_only"
                    else SyncSourceStatus.NEVER_SYNCED.value
                ),
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            self._session.add(row)
            self._session.flush()
            return row

        existing.region = source.region
        existing.authority = source.authority
        existing.source_type = source.source_type
        existing.canonical_url = source.url
        existing.local_path = local_path
        existing.language = source.language
        existing.enabled = source.enabled
        existing.document_id = document_id
        existing.updated_at = utc_now()
        if not source.enabled:
            existing.status = SyncSourceStatus.DISABLED.value
        self._session.flush()
        return existing

    def get_source_by_key(self, source_key: str) -> SynchronizedSourceORM | None:
        return self._session.scalar(
            select(SynchronizedSourceORM).where(SynchronizedSourceORM.source_key == source_key)
        )

    def list_sources(self) -> list[SynchronizedSourceORM]:
        return list(self._session.scalars(select(SynchronizedSourceORM)))

    def start_run(self, requested_scope: str) -> SynchronizationRunORM:
        run = SynchronizationRunORM(
            requested_scope=requested_scope,
            status=SyncRunStatus.RUNNING.value,
            checked_count=0,
            unchanged_count=0,
            updated_count=0,
            failed_count=0,
            discovered_candidate_count=0,
            started_at=utc_now(),
        )
        self._session.add(run)
        self._session.flush()
        return run

    def finish_run(
        self,
        run: SynchronizationRunORM,
        *,
        status: SyncRunStatus,
        error_summary: str | None = None,
    ) -> SynchronizationRunORM:
        run.status = status.value
        run.completed_at = utc_now()
        run.error_summary = error_summary
        self._session.flush()
        return run

    def add_event(
        self,
        *,
        run_id: str,
        source_id: str | None,
        event_type: SyncEventType,
        message: str,
        old_sha256: str | None = None,
        new_sha256: str | None = None,
    ) -> SynchronizationEventORM:
        event = SynchronizationEventORM(
            run_id=run_id,
            source_id=source_id,
            event_type=event_type.value,
            message=message,
            old_sha256=old_sha256,
            new_sha256=new_sha256,
            created_at=utc_now(),
        )
        self._session.add(event)
        self._session.flush()
        return event

    def mark_unchanged(
        self,
        row: SynchronizedSourceORM,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> None:
        row.status = SyncSourceStatus.UNCHANGED.value
        row.last_checked_at = utc_now()
        row.etag = etag or row.etag
        row.last_modified = last_modified or row.last_modified
        row.consecutive_failures = 0
        row.last_error = None

    def mark_updated(
        self,
        row: SynchronizedSourceORM,
        *,
        sha256: str,
        content_length: int,
        etag: str | None,
        last_modified: str | None,
    ) -> None:
        now = utc_now()
        row.status = SyncSourceStatus.UPDATED.value
        row.content_sha256 = sha256
        row.content_length = content_length
        row.etag = etag
        row.last_modified = last_modified
        row.last_checked_at = now
        row.last_changed_at = now
        row.last_successful_sync_at = now
        row.consecutive_failures = 0
        row.last_error = None

    def mark_unavailable(self, row: SynchronizedSourceORM, *, message: str) -> None:
        row.status = SyncSourceStatus.UNAVAILABLE.value
        row.last_checked_at = utc_now()
        row.consecutive_failures += 1
        row.last_error = message

    def mark_failed(self, row: SynchronizedSourceORM, *, message: str) -> None:
        row.status = SyncSourceStatus.FAILED.value
        row.last_checked_at = utc_now()
        row.consecutive_failures += 1
        row.last_error = message

    def list_runs(self, *, limit: int = 20) -> list[SynchronizationRunORM]:
        statement = (
            select(SynchronizationRunORM)
            .order_by(SynchronizationRunORM.started_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(statement))

    def add_candidate(
        self,
        *,
        discovered_from_source_id: str,
        region: str,
        candidate_url: str,
        canonical_url: str,
        detected_title: str | None,
        detected_content_type: str | None,
        inferred_procedure_types: list[str],
        relevance_score: float | None,
        discovery_reason: str,
    ) -> SourceCandidateORM:
        existing = self._session.scalar(
            select(SourceCandidateORM).where(
                SourceCandidateORM.canonical_url == canonical_url,
                SourceCandidateORM.region == region,
            )
        )
        if existing is not None:
            return existing

        candidate = SourceCandidateORM(
            discovered_from_source_id=discovered_from_source_id,
            region=region,
            candidate_url=candidate_url,
            canonical_url=canonical_url,
            detected_title=detected_title,
            detected_content_type=detected_content_type,
            inferred_procedure_types_json=inferred_procedure_types,
            relevance_score=relevance_score,
            discovery_reason=discovery_reason,
            status=CandidateStatus.PENDING.value,
            discovered_at=utc_now(),
        )
        self._session.add(candidate)
        self._session.flush()
        return candidate

    def list_candidates(self, *, status: CandidateStatus | None = None) -> list[SourceCandidateORM]:
        statement = select(SourceCandidateORM)
        if status is not None:
            statement = statement.where(SourceCandidateORM.status == status.value)
        return list(self._session.scalars(statement.order_by(SourceCandidateORM.discovered_at.desc())))

    def get_candidate(self, candidate_id: str) -> SourceCandidateORM | None:
        return self._session.get(SourceCandidateORM, candidate_id)

    def approve_candidate(self, candidate_id: str, *, note: str | None = None) -> SourceCandidateORM:
        candidate = self._require_candidate(candidate_id)
        candidate.status = CandidateStatus.APPROVED.value
        candidate.reviewed_at = utc_now()
        candidate.review_note = note
        self._session.flush()
        return candidate

    def reject_candidate(self, candidate_id: str, *, note: str | None = None) -> SourceCandidateORM:
        candidate = self._require_candidate(candidate_id)
        candidate.status = CandidateStatus.REJECTED.value
        candidate.reviewed_at = utc_now()
        candidate.review_note = note
        self._session.flush()
        return candidate

    def _require_candidate(self, candidate_id: str) -> SourceCandidateORM:
        candidate = self.get_candidate(candidate_id)
        if candidate is None:
            raise ValueError("Candidate not found")
        return candidate


def candidate_to_model(candidate: SourceCandidateORM) -> CandidateRecord:
    """Convert a candidate ORM row to Pydantic."""

    return CandidateRecord(
        id=candidate.id,
        discovered_from_source_id=candidate.discovered_from_source_id,
        region=candidate.region,
        candidate_url=candidate.candidate_url,
        canonical_url=candidate.canonical_url,
        detected_title=candidate.detected_title,
        detected_content_type=candidate.detected_content_type,
        inferred_procedure_types=list(candidate.inferred_procedure_types_json or []),
        relevance_score=candidate.relevance_score,
        discovery_reason=candidate.discovery_reason,
        status=CandidateStatus(candidate.status),
        discovered_at=candidate.discovered_at,
        reviewed_at=candidate.reviewed_at,
        review_note=candidate.review_note,
    )
