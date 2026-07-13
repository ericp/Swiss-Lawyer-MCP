"""Procedure API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.dependencies import get_memory_service, get_orchestrator
from backend.api.schemas import (
    MemoryDeletionResponse,
    ProcedureDetailResponse,
    ProcedureListResponse,
    ProcedurePatchRequest,
    ProcedureQueryRequest,
    ProcedureQueryResponse,
)
from backend.memory.memory_service import MemoryService
from backend.models.memory import SavedProcedure
from backend.models.planner import WorkflowStatus
from backend.orchestration.procedure_orchestrator import (
    ProcedureNotFoundError,
    ProcedureOrchestrator,
    ProcedureOwnershipError,
    UserNotFoundError,
)

router = APIRouter(prefix="/v1", tags=["procedures"])


@router.post("/procedures/query", response_model=ProcedureQueryResponse)
def query_procedure(
    request: ProcedureQueryRequest,
    orchestrator: ProcedureOrchestrator = Depends(get_orchestrator),
) -> ProcedureQueryResponse:
    """Run the clarification-first end-to-end procedure workflow."""

    return orchestrator.handle_query(request)


@router.get("/users/{user_id}/procedures", response_model=ProcedureListResponse)
def list_user_procedures(
    user_id: str,
    status: WorkflowStatus | None = None,
    intent: str | None = None,
    active_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ProcedureListResponse:
    """List a user's saved procedures."""

    _require_user(memory_service, user_id)
    procedures = memory_service.list_procedures(
        user_id=user_id,
        intent=intent,
        status=status,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )
    return ProcedureListResponse(
        procedures=[
            _detail_response(memory_service, procedure)
            for procedure in procedures
        ]
    )


@router.get("/procedures/{procedure_id}", response_model=ProcedureDetailResponse)
def get_procedure(
    procedure_id: str,
    user_id: str = Query(min_length=1),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ProcedureDetailResponse:
    """Read one saved procedure with recent interaction summaries."""

    procedure = _require_owned_procedure(memory_service, user_id, procedure_id)
    return _detail_response(memory_service, procedure)


@router.patch("/procedures/{procedure_id}", response_model=ProcedureDetailResponse)
def patch_procedure(
    procedure_id: str,
    request: ProcedurePatchRequest,
    memory_service: MemoryService = Depends(get_memory_service),
) -> ProcedureDetailResponse:
    """Apply controlled procedure progress updates."""

    procedure = _require_owned_procedure(memory_service, request.user_id, procedure_id)
    if request.confirmed_profile_facts:
        memory_service.save_confirmed_profile_facts(
            user_id=request.user_id,
            facts=request.confirmed_profile_facts,
            source="user_confirmed",
        )
        memory_service.record_interaction(
            procedure_id=procedure_id,
            interaction_type="user_information_added",
            summary="Confirmed profile information was added.",
            structured_payload={
                "fields": sorted(request.confirmed_profile_facts),
            },
        )
    if request.status is not None:
        procedure = memory_service.update_procedure_status(
            procedure_id=procedure_id,
            status=request.status,
        )
    if request.current_step is not None:
        procedure = memory_service.update_current_step(
            procedure_id=procedure_id,
            current_step=request.current_step,
        )
        memory_service.record_interaction(
            procedure_id=procedure_id,
            interaction_type="plan_updated",
            summary=f"Current step updated to {request.current_step}.",
            structured_payload={"current_step": request.current_step},
        )
    if request.progress_note:
        memory_service.record_interaction(
            procedure_id=procedure_id,
            interaction_type="plan_updated",
            summary=request.progress_note,
        )
    return _detail_response(memory_service, procedure)


@router.delete("/users/{user_id}/memory", response_model=MemoryDeletionResponse)
def delete_user_memory(
    user_id: str,
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryDeletionResponse:
    """Delete user-specific memory without touching ChromaDB knowledge."""

    _require_user(memory_service, user_id)
    memory_service.delete_user_memory(user_id)
    return MemoryDeletionResponse(
        user_id=user_id,
        deleted=True,
        message="User memory deleted. Official ChromaDB knowledge was not deleted.",
    )


def _require_user(memory_service: MemoryService, user_id: str) -> None:
    if memory_service.get_user(user_id) is None:
        raise UserNotFoundError("User not found.")


def _require_owned_procedure(
    memory_service: MemoryService,
    user_id: str,
    procedure_id: str,
) -> SavedProcedure:
    procedure = memory_service.get_procedure(procedure_id)
    if procedure is None:
        raise ProcedureNotFoundError("Procedure not found.")
    if procedure.user_id != user_id:
        raise ProcedureOwnershipError("Procedure belongs to another user.")
    return procedure


def _detail_response(
    memory_service: MemoryService,
    procedure: SavedProcedure,
) -> ProcedureDetailResponse:
    interactions = memory_service.list_interactions_for_procedure(
        procedure_id=procedure.id,
        limit=10,
    )
    return ProcedureDetailResponse(
        procedure_id=procedure.id,
        user_id=procedure.user_id,
        intent=procedure.intent,
        title=procedure.title,
        status=procedure.status,
        summary=procedure.summary,
        plan=procedure.plan,
        current_step=procedure.current_step,
        recent_interaction_summaries=[
            interaction.summary for interaction in interactions
        ],
    )
