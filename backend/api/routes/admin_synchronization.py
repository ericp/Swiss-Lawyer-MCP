"""Configuration-protected synchronization admin endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.dependencies import get_source_synchronizer
from backend.synchronizer.models import CandidateStatus, SynchronizationReport
from backend.synchronizer.synchronizer_service import SourceSynchronizer

router = APIRouter(prefix="/v1/admin/synchronization", tags=["synchronization-admin"])


class SyncRunRequest(BaseModel):
    """Admin synchronization run request."""

    all: bool = False
    region: str | None = None
    source_id: str | None = None
    discover: bool = False


class CandidateReviewRequest(BaseModel):
    """Candidate review note."""

    note: str | None = None


@router.post("/run", response_model=SynchronizationReport)
def run_synchronization(
    request: SyncRunRequest,
    synchronizer: SourceSynchronizer = Depends(get_source_synchronizer),
) -> SynchronizationReport:
    if request.discover:
        if request.source_id:
            return synchronizer.discover_source(request.source_id)
        if request.region:
            return synchronizer.discover_region(request.region)
        return synchronizer.discover_all()
    if request.source_id:
        return synchronizer.sync_source(request.source_id)
    if request.region:
        return synchronizer.sync_region(request.region)
    return synchronizer.sync_all()


@router.get("/status")
def synchronization_status(
    synchronizer: SourceSynchronizer = Depends(get_source_synchronizer),
) -> dict[str, object]:
    return synchronizer.status()


@router.get("/runs")
def synchronization_runs(
    synchronizer: SourceSynchronizer = Depends(get_source_synchronizer),
) -> dict[str, object]:
    return synchronizer.status()


@router.get("/candidates")
def list_candidates(
    status: CandidateStatus | None = None,
    synchronizer: SourceSynchronizer = Depends(get_source_synchronizer),
) -> dict[str, object]:
    return {"candidates": [candidate.model_dump(mode="json") for candidate in synchronizer.list_candidates(status=status)]}


@router.post("/candidates/{candidate_id}/approve")
def approve_candidate(
    candidate_id: str,
    request: CandidateReviewRequest,
    synchronizer: SourceSynchronizer = Depends(get_source_synchronizer),
) -> dict[str, object]:
    candidate = synchronizer.approve_candidate(candidate_id, note=request.note)
    return {"candidate": candidate.model_dump(mode="json")}


@router.post("/candidates/{candidate_id}/reject")
def reject_candidate(
    candidate_id: str,
    request: CandidateReviewRequest,
    synchronizer: SourceSynchronizer = Depends(get_source_synchronizer),
) -> dict[str, object]:
    candidate = synchronizer.reject_candidate(candidate_id, note=request.note)
    return {"candidate": candidate.model_dump(mode="json")}
