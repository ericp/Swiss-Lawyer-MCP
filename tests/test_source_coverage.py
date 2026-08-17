from __future__ import annotations

from backend.synchronizer.source_coverage import SourceCoverageService
from backend.synchronizer.source_registry import SourceDefinition, SourceRegistry


def _source(
    source_id: str,
    *,
    region: str,
    procedure_types: list[str],
    source_type: str = "webpage",
    enabled: bool = True,
    use_for_retrieval: bool = True,
) -> SourceDefinition:
    return SourceDefinition(
        id=source_id,
        enabled=enabled,
        region=region,
        authority="Official authority",
        procedure_types=procedure_types,
        source_type=source_type,
        url=(
            f"https://www.{region}.ch/{source_id}"
            if region != "federal"
            else f"https://www.ch.ch/{source_id}"
        ),
        language="de",
        local_filename=f"{source_id}.html",
        discovery_enabled=False,
        metadata={"use_for_retrieval": use_for_retrieval},
    )


class FakeSynchronizer:
    def __init__(self, registry: SourceRegistry, *, failing_source_ids: set[str] | None = None) -> None:
        self.registry = registry
        self.failing_source_ids = failing_source_ids or set()
        self.synced_source_ids: list[str] = []

    def validate_registry(self) -> SourceRegistry:
        return self.registry

    def sync_source(self, source_id: str):
        self.synced_source_ids.append(source_id)

        class Report:
            failed_count = 1 if source_id in self.failing_source_ids else 0

        return Report()


def test_source_coverage_refreshes_only_matching_federal_and_requested_canton_sources() -> None:
    registry = SourceRegistry(
        version=1,
        sources=[
            _source("federal_work", region="federal", procedure_types=["work_permit"]),
            _source("be_work", region="be", procedure_types=["work_permit"]),
            _source("zh_work", region="zh", procedure_types=["work_permit"]),
            _source("be_citizenship", region="be", procedure_types=["citizenship"]),
        ],
    )
    synchronizer = FakeSynchronizer(registry)

    result = SourceCoverageService(synchronizer=synchronizer).refresh_for_case(
        intent="work_permit",
        requested_region="be",
    )

    assert result.matched_source_ids == ["federal_work", "be_work"]
    assert synchronizer.synced_source_ids == ["federal_work", "be_work"]
    assert result.refreshed_source_ids == ["federal_work", "be_work"]


def test_source_coverage_ignores_landing_pages_and_non_retrieval_sources() -> None:
    registry = SourceRegistry(
        version=1,
        sources=[
            _source(
                "be_portal",
                region="be",
                procedure_types=["work_permit"],
                source_type="landing_page",
                use_for_retrieval=False,
            ),
            _source(
                "be_reference",
                region="be",
                procedure_types=["work_permit"],
                use_for_retrieval=False,
            ),
            _source("be_work", region="be", procedure_types=["work_permit"]),
        ],
    )
    synchronizer = FakeSynchronizer(registry)

    result = SourceCoverageService(synchronizer=synchronizer).refresh_for_case(
        intent="work_permit",
        requested_region="be",
    )

    assert result.matched_source_ids == ["be_work"]
    assert synchronizer.synced_source_ids == ["be_work"]


def test_source_coverage_records_source_failures_without_stopping_other_sources() -> None:
    registry = SourceRegistry(
        version=1,
        sources=[
            _source("federal_work", region="federal", procedure_types=["work_permit"]),
            _source("be_work", region="be", procedure_types=["work_permit"]),
        ],
    )
    synchronizer = FakeSynchronizer(registry, failing_source_ids={"federal_work"})

    result = SourceCoverageService(synchronizer=synchronizer).refresh_for_case(
        intent="work_permit",
        requested_region="be",
    )

    assert result.failed_source_ids == ["federal_work"]
    assert result.refreshed_source_ids == ["be_work"]
    assert synchronizer.synced_source_ids == ["federal_work", "be_work"]
