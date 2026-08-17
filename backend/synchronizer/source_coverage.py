"""Just-in-time official source coverage refresh before retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from backend.synchronizer.source_registry import SourceDefinition


RETRIEVAL_SOURCE_TYPES = {"pdf", "webpage"}


class SynchronizerProtocol(Protocol):
    """Subset of SourceSynchronizer used by just-in-time coverage refresh."""

    def validate_registry(self):
        """Return the current source registry."""

    def sync_source(self, source_id: str):
        """Synchronize one approved source and return a report."""


@dataclass(frozen=True)
class SourceCoverageRefreshResult:
    """Outcome of refreshing sources relevant to one resolved user case."""

    intent: str
    requested_region: str | None
    matched_source_ids: list[str] = field(default_factory=list)
    refreshed_source_ids: list[str] = field(default_factory=list)
    failed_source_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def refresh_attempted(self) -> bool:
        """Return whether at least one relevant source was checked."""

        return bool(self.matched_source_ids)

    @property
    def refresh_succeeded(self) -> bool:
        """Return whether at least one relevant source refreshed without failure."""

        return bool(self.refreshed_source_ids)


class SourceCoverageService:
    """Refresh only approved sources relevant to the detected intent and canton."""

    def __init__(self, *, synchronizer: SynchronizerProtocol) -> None:
        self._synchronizer = synchronizer

    def refresh_for_case(
        self,
        *,
        intent: str,
        requested_region: str | None,
    ) -> SourceCoverageRefreshResult:
        """Synchronize enabled federal and canton sources for a resolved case."""

        registry = self._synchronizer.validate_registry()
        sources = _matching_retrieval_sources(
            registry.sources,
            intent=intent,
            requested_region=requested_region,
        )
        matched_source_ids = [source.id for source in sources]
        refreshed: list[str] = []
        failed: list[str] = []
        warnings: list[str] = []

        for source in sources:
            try:
                report = self._synchronizer.sync_source(source.id)
            except Exception as error:
                failed.append(source.id)
                warnings.append(f"{source.id}: {str(error)[:200]}")
                continue

            if report.failed_count:
                failed.append(source.id)
                warnings.append(f"{source.id}: synchronization completed with failures")
            else:
                refreshed.append(source.id)

        return SourceCoverageRefreshResult(
            intent=intent,
            requested_region=requested_region,
            matched_source_ids=matched_source_ids,
            refreshed_source_ids=refreshed,
            failed_source_ids=failed,
            warnings=warnings,
        )


def _matching_retrieval_sources(
    sources: list[SourceDefinition],
    *,
    intent: str,
    requested_region: str | None,
) -> list[SourceDefinition]:
    allowed_regions = {"federal"}
    if requested_region and requested_region != "federal":
        allowed_regions.add(requested_region)
    return [
        source
        for source in sources
        if source.enabled
        and source.region in allowed_regions
        and source.source_type in RETRIEVAL_SOURCE_TYPES
        and intent in source.procedure_types
        and _source_enabled_for_retrieval(source)
    ]


def _source_enabled_for_retrieval(source: SourceDefinition) -> bool:
    value = source.metadata.get("use_for_retrieval", True)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return True
