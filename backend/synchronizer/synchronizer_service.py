"""Official source synchronization service."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from urllib.parse import urlparse

from backend.ingestion.vector_store import ChromaChunkStore
from backend.memory.database import SessionFactory
from backend.memory.models import SynchronizationRunORM, SynchronizedSourceORM
from backend.synchronizer.discovery import discover_candidates_from_html
from backend.synchronizer.document_processor import (
    DocumentValidationError,
    EmbedderProtocol,
    chunks_for_pdf,
    content_hash_for_local_file,
    process_webpage,
    validate_pdf_file,
)
from backend.synchronizer.hashing import sha256_bytes, sha256_file
from backend.synchronizer.http_client import HttpClientError, HttpFetchResult, SyncHttpClient
from backend.synchronizer.models import (
    CandidateRecord,
    CandidateStatus,
    ChangeStatus,
    SynchronizationReport,
    SyncEventType,
    SyncRunStatus,
    SyncSourceStatus,
)
from backend.synchronizer.repository import SynchronizerRepository, candidate_to_model
from backend.synchronizer.source_registry import (
    SourceDefinition,
    SourceRegistry,
    load_source_registry,
    write_source_registry,
)
from backend.utils.config import SynchronizerSettings

logger = logging.getLogger(__name__)


class SourceSynchronizer:
    """Synchronize approved official sources and discover candidate sources."""

    def __init__(
        self,
        *,
        settings: SynchronizerSettings,
        session_factory: SessionFactory,
        http_client: SyncHttpClient,
        chunk_store: ChromaChunkStore | None = None,
        embedder: EmbedderProtocol | None = None,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._http_client = http_client
        self._chunk_store = chunk_store
        self._embedder = embedder

    def validate_registry(self) -> SourceRegistry:
        """Load and validate the configured source registry."""

        return load_source_registry(self._settings.source_registry_path)

    def sync_all(self) -> SynchronizationReport:
        return self._sync(scope="all")

    def sync_region(self, region: str) -> SynchronizationReport:
        return self._sync(scope=f"region:{region}", region=region)

    def sync_source(self, source_id: str) -> SynchronizationReport:
        return self._sync(scope=f"source:{source_id}", source_id=source_id)

    def discover_all(self) -> SynchronizationReport:
        return self._discover(scope="discover:all")

    def discover_region(self, region: str) -> SynchronizationReport:
        return self._discover(scope=f"discover:region:{region}", region=region)

    def discover_source(self, source_id: str) -> SynchronizationReport:
        return self._discover(scope=f"discover:source:{source_id}", source_id=source_id)

    def list_candidates(self, *, status: CandidateStatus | None = None) -> list[CandidateRecord]:
        with self._session_factory() as session:
            repository = SynchronizerRepository(session)
            return [
                candidate_to_model(candidate)
                for candidate in repository.list_candidates(status=status)
            ]

    def approve_candidate(self, candidate_id: str, *, note: str | None = None) -> CandidateRecord:
        with self._session_factory() as session, session.begin():
            repository = SynchronizerRepository(session)
            candidate = repository.approve_candidate(candidate_id, note=note)
            registry = load_source_registry(self._settings.source_registry_path)
            source = _source_from_candidate(candidate)
            registry.sources.append(source)
            write_source_registry(self._settings.source_registry_path, registry)
            return candidate_to_model(candidate)

    def reject_candidate(self, candidate_id: str, *, note: str | None = None) -> CandidateRecord:
        with self._session_factory() as session, session.begin():
            candidate = SynchronizerRepository(session).reject_candidate(candidate_id, note=note)
            return candidate_to_model(candidate)

    def status(self) -> dict[str, object]:
        with self._session_factory() as session:
            repository = SynchronizerRepository(session)
            runs = repository.list_runs(limit=5)
            sources = repository.list_sources()
            return {
                "source_count": len(sources),
                "last_runs": [
                    {
                        "id": run.id,
                        "status": run.status,
                        "requested_scope": run.requested_scope,
                        "started_at": run.started_at.isoformat(),
                        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                    }
                    for run in runs
                ],
            }

    def _sync(
        self,
        *,
        scope: str,
        region: str | None = None,
        source_id: str | None = None,
    ) -> SynchronizationReport:
        registry = self.validate_registry()
        sources = _filter_sources(registry.sources, region=region, source_id=source_id)
        with self._session_factory() as session, session.begin():
            repository = SynchronizerRepository(session)
            run = repository.start_run(scope)
            event_messages: list[str] = []
            for source in sources:
                row = repository.upsert_source(
                    source,
                    local_path=str(self._local_path_for_source(source)),
                )
                run.checked_count += 1
                try:
                    message = self._sync_one_source(repository, run, row, source)
                    event_messages.append(message)
                    if row.status == SyncSourceStatus.UNCHANGED.value:
                        run.unchanged_count += 1
                    elif row.status in {
                        SyncSourceStatus.UPDATED.value,
                        SyncSourceStatus.MANUALLY_SEEDED.value,
                    }:
                        run.updated_count += 1
                    elif row.status in {
                        SyncSourceStatus.FAILED.value,
                        SyncSourceStatus.UNAVAILABLE.value,
                    }:
                        run.failed_count += 1
                except Exception as error:
                    sanitized = _sanitize_error(error)
                    repository.mark_failed(row, message=sanitized)
                    repository.add_event(
                        run_id=run.id,
                        source_id=row.id,
                        event_type=SyncEventType.FAILED,
                        message=sanitized,
                    )
                    run.failed_count += 1
                    event_messages.append(f"{source.id}: failed")
                    logger.warning(
                        "source_sync_failed",
                        extra={"run_id": run.id, "source_id": source.id, "region": source.region},
                    )

            final_status = (
                SyncRunStatus.COMPLETED_WITH_ERRORS
                if run.failed_count
                else SyncRunStatus.COMPLETED
            )
            repository.finish_run(run, status=final_status)
            return _report_from_run(run, events=event_messages)

    def _sync_one_source(
        self,
        repository: SynchronizerRepository,
        run: SynchronizationRunORM,
        row: SynchronizedSourceORM,
        source: SourceDefinition,
    ) -> str:
        repository.add_event(
            run_id=run.id,
            source_id=row.id,
            event_type=SyncEventType.CHECK_STARTED,
            message=f"Checking {source.id}",
        )
        if source.source_type == "local_only":
            self._mark_local_seed(repository, row, source)
            return f"{source.id}: manually seeded"
        if not source.enabled:
            row.status = SyncSourceStatus.DISABLED.value
            return f"{source.id}: disabled"

        result = self._http_client.get(
            source.url,
            region=source.region,
            etag=row.etag,
            last_modified=row.last_modified,
        )
        if result.status_code == 304:
            repository.mark_unchanged(row)
            repository.add_event(
                run_id=run.id,
                source_id=row.id,
                event_type=SyncEventType.UNCHANGED,
                message="Remote source returned HTTP 304.",
            )
            return f"{source.id}: unchanged"
        if result.status_code in {404, 410}:
            repository.mark_unavailable(row, message=f"HTTP {result.status_code}")
            repository.add_event(
                run_id=run.id,
                source_id=row.id,
                event_type=SyncEventType.UNAVAILABLE,
                message="Source unavailable; last valid indexed version retained.",
            )
            return f"{source.id}: unavailable"
        if result.status_code >= 400:
            raise HttpClientError(f"HTTP {result.status_code}")

        new_sha = sha256_bytes(result.content)
        if row.content_sha256 and row.content_sha256 == new_sha:
            repository.mark_unchanged(
                row,
                etag=result.headers.get("etag"),
                last_modified=result.headers.get("last-modified"),
            )
            repository.add_event(
                run_id=run.id,
                source_id=row.id,
                event_type=SyncEventType.UNCHANGED,
                message="Content hash unchanged.",
            )
            return f"{source.id}: unchanged"

        if source.source_type == "pdf":
            self._replace_pdf(repository, run, row, source, result, new_sha)
        elif source.source_type in {"webpage", "landing_page"}:
            self._replace_webpage(repository, run, row, source, result, new_sha)
        else:
            raise ValueError(f"Unsupported remote source type: {source.source_type}")

        repository.mark_updated(
            row,
            sha256=new_sha if source.source_type == "pdf" else row.content_sha256 or new_sha,
            content_length=result.content_length or len(result.content),
            etag=result.headers.get("etag"),
            last_modified=result.headers.get("last-modified"),
        )
        repository.add_event(
            run_id=run.id,
            source_id=row.id,
            event_type=SyncEventType.UPDATED,
            message="Source synchronized successfully.",
            old_sha256=row.content_sha256,
            new_sha256=new_sha,
        )
        return f"{source.id}: updated"

    def _replace_pdf(
        self,
        repository: SynchronizerRepository,
        run: SynchronizationRunORM,
        row: SynchronizedSourceORM,
        source: SourceDefinition,
        result: HttpFetchResult,
        content_sha256: str,
    ) -> None:
        self._settings.temporary_download_path.mkdir(parents=True, exist_ok=True)
        temp_path = self._settings.temporary_download_path / f"{source.id}.download"
        temp_path.write_bytes(result.content)
        try:
            validate_pdf_file(temp_path, content_type=result.content_type)
            repository.add_event(
                run_id=run.id,
                source_id=row.id,
                event_type=SyncEventType.VALIDATED,
                message="PDF validation passed.",
            )
            document_id, chunks = chunks_for_pdf(
                temp_path,
                source=source,
                canonical_url=result.final_url,
                content_sha256=content_sha256,
                chunk_size_words=self._settings.chunk_size_words,
                overlap_words=self._settings.chunk_overlap_words,
            )
            row.document_id = document_id
            self._replace_chunks(document_id=document_id, chunks=chunks)
            destination = self._local_path_for_source(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(temp_path), destination)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _replace_webpage(
        self,
        repository: SynchronizerRepository,
        run: SynchronizationRunORM,
        row: SynchronizedSourceORM,
        source: SourceDefinition,
        result: HttpFetchResult,
        _content_sha256: str,
    ) -> None:
        document_id, normalized_sha, chunks, output_path = process_webpage(
            result.content,
            source=source,
            canonical_url=result.final_url,
            documents_root=self._settings.synchronized_document_path,
            chunk_size_words=self._settings.chunk_size_words,
            overlap_words=self._settings.chunk_overlap_words,
        )
        row.document_id = document_id
        row.content_sha256 = normalized_sha
        row.local_path = str(output_path)
        repository.add_event(
            run_id=run.id,
            source_id=row.id,
            event_type=SyncEventType.VALIDATED,
            message="Webpage content normalized.",
        )
        self._replace_chunks(document_id=document_id, chunks=chunks)

    def _replace_chunks(self, *, document_id: str, chunks: list) -> None:
        if not chunks:
            raise DocumentValidationError("Document produced no chunks")
        if self._embedder is None or self._chunk_store is None:
            raise RuntimeError("Embedding and ChromaDB services are required for indexing")
        embeddings = self._embedder.embed_texts([chunk.text for chunk in chunks])
        self._chunk_store.replace_document(
            document_id=document_id,
            chunks=chunks,
            embeddings=embeddings,
        )

    def _mark_local_seed(
        self,
        repository: SynchronizerRepository,
        row: SynchronizedSourceORM,
        source: SourceDefinition,
    ) -> None:
        local_path = self._local_path_for_source(source)
        if local_path.exists():
            row.content_sha256 = content_hash_for_local_file(local_path)
            row.content_length = local_path.stat().st_size
        row.status = SyncSourceStatus.MANUALLY_SEEDED.value
        row.enabled = source.enabled

    def _discover(
        self,
        *,
        scope: str,
        region: str | None = None,
        source_id: str | None = None,
    ) -> SynchronizationReport:
        registry = self.validate_registry()
        sources = [
            source
            for source in _filter_sources(registry.sources, region=region, source_id=source_id)
            if source.enabled and (source.discovery_enabled or source.source_type == "landing_page")
        ]
        with self._session_factory() as session, session.begin():
            repository = SynchronizerRepository(session)
            run = repository.start_run(scope)
            event_messages: list[str] = []
            for source in sources:
                row = repository.upsert_source(
                    source,
                    local_path=str(self._local_path_for_source(source)),
                )
                run.checked_count += 1
                try:
                    result = self._http_client.get(source.url, region=source.region)
                    if result.status_code >= 400:
                        raise HttpClientError(f"HTTP {result.status_code}")
                    html = result.content.decode("utf-8", errors="replace")
                    for candidate in discover_candidates_from_html(html, source=source):
                        repository.add_candidate(
                            discovered_from_source_id=source.id,
                            region=source.region,
                            candidate_url=candidate.url,
                            canonical_url=candidate.canonical_url,
                            detected_title=candidate.title,
                            detected_content_type=candidate.detected_content_type,
                            inferred_procedure_types=candidate.inferred_procedure_types,
                            relevance_score=candidate.relevance_score,
                            discovery_reason=candidate.discovery_reason,
                        )
                        run.discovered_candidate_count += 1
                        repository.add_event(
                            run_id=run.id,
                            source_id=row.id,
                            event_type=SyncEventType.CANDIDATE_DISCOVERED,
                            message=f"Candidate discovered: {candidate.canonical_url}",
                        )
                    event_messages.append(f"{source.id}: discovered")
                except Exception as error:
                    run.failed_count += 1
                    sanitized = _sanitize_error(error)
                    repository.add_event(
                        run_id=run.id,
                        source_id=row.id,
                        event_type=SyncEventType.FAILED,
                        message=sanitized,
                    )
                    event_messages.append(f"{source.id}: discovery failed")
            repository.finish_run(
                run,
                status=(
                    SyncRunStatus.COMPLETED_WITH_ERRORS
                    if run.failed_count
                    else SyncRunStatus.COMPLETED
                ),
            )
            return _report_from_run(run, events=event_messages)

    def _local_path_for_source(self, source: SourceDefinition) -> Path:
        if source.source_type == "webpage" or source.source_type == "landing_page":
            return self._settings.synchronized_document_path / source.region / f"{source.id}.json"
        return self._settings.synchronized_pdf_path / source.region / source.local_filename


def classify_change(
    *,
    previous_sha256: str | None,
    previous_etag: str | None,
    previous_last_modified: str | None,
    response_status: int,
    response_headers: dict[str, str],
    new_sha256: str | None,
) -> ChangeStatus:
    """Classify source change state using conditional headers and SHA-256."""

    if response_status == 304:
        return ChangeStatus.UNCHANGED
    if response_status in {404, 410}:
        return ChangeStatus.UNAVAILABLE
    if response_status >= 400:
        return ChangeStatus.FAILED
    if previous_sha256 is None:
        return ChangeStatus.NEW
    if new_sha256 is not None and previous_sha256 == new_sha256:
        return ChangeStatus.UNCHANGED
    if previous_etag and response_headers.get("etag") == previous_etag and new_sha256 == previous_sha256:
        return ChangeStatus.UNCHANGED
    if (
        previous_last_modified
        and response_headers.get("last-modified") == previous_last_modified
        and new_sha256 == previous_sha256
    ):
        return ChangeStatus.UNCHANGED
    return ChangeStatus.CHANGED


def _filter_sources(
    sources: list[SourceDefinition],
    *,
    region: str | None,
    source_id: str | None,
) -> list[SourceDefinition]:
    return [
        source
        for source in sources
        if (region is None or source.region == region)
        and (source_id is None or source.id == source_id)
    ]


def _source_from_candidate(candidate) -> SourceDefinition:
    path_name = Path(urlparse(candidate.canonical_url).path).name or f"{candidate.id}.html"
    source_type = "pdf" if path_name.lower().endswith(".pdf") else "webpage"
    safe_name = path_name.replace("/", "_")
    if source_type == "webpage" and not safe_name.endswith(".html"):
        safe_name = f"{candidate.id}.html"
    return SourceDefinition(
        id=f"candidate_{candidate.id}",
        enabled=True,
        region=candidate.region,
        authority="Approved discovered official source",
        procedure_types=list(candidate.inferred_procedure_types_json or ["immigration"]),
        source_type=source_type,
        url=candidate.canonical_url,
        language="unknown",
        local_filename=safe_name,
        discovery_enabled=False,
        title=candidate.detected_title,
        notes="Approved from synchronizer candidate review queue.",
    )


def _report_from_run(run: SynchronizationRunORM, *, events: list[str]) -> SynchronizationReport:
    return SynchronizationReport(
        run_id=run.id,
        requested_scope=run.requested_scope,
        status=SyncRunStatus(run.status),
        checked_count=run.checked_count,
        unchanged_count=run.unchanged_count,
        updated_count=run.updated_count,
        failed_count=run.failed_count,
        discovered_candidate_count=run.discovered_candidate_count,
        events=events,
    )


def _sanitize_error(error: Exception) -> str:
    message = str(error) or error.__class__.__name__
    return message[:500]
