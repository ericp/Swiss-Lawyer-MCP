"""Private routes used only by the local MCP container."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.api.dependencies import get_memory_service, get_orchestrator
from backend.api.internal_auth import require_internal_service_token
from backend.api.routes.procedures import _detail_response, patch_procedure
from backend.api.schemas import (
    MemoryDeletionResponse,
    ProcedureDetailResponse,
    ProcedureListResponse,
    ProcedurePatchRequest,
    ProcedureQueryRequest,
    ProcedureQueryResponse,
)
from backend.memory.memory_service import MemoryService
from backend.models.planner import WorkflowStatus
from backend.orchestration.procedure_orchestrator import ProcedureNotFoundError, ProcedureOrchestrator, ProcedureOwnershipError

router = APIRouter(
    prefix="/internal/mcp",
    tags=["internal-mcp"],
    dependencies=[Depends(require_internal_service_token)],
)


class InternalProcedurePatchRequest(BaseModel):
    external_user_key: str = Field(min_length=1)
    status: WorkflowStatus | None = None
    current_step: int | None = Field(default=None, ge=1)
    progress_note: str | None = None


@router.post("/procedures/query", response_model=ProcedureQueryResponse)
def query_procedure_for_external_user(
    request: ProcedureQueryRequest,
    orchestrator: ProcedureOrchestrator = Depends(get_orchestrator),
) -> ProcedureQueryResponse:
    if not request.external_user_key or request.user_id:
        raise HTTPException(
            status_code=400,
            detail="Internal MCP query requires external_user_key and must not include user_id.",
        )
    return orchestrator.handle_query(request)


@router.get("/procedures", response_model=ProcedureListResponse)
def list_procedures_for_external_user(
    external_user_key: str = Query(min_length=1),
    status: WorkflowStatus | None = None,
    intent: str | None = None,
    active_only: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ProcedureListResponse:
    user = memory_service.get_or_create_user(external_user_key=external_user_key)
    procedures = memory_service.list_procedures(
        user_id=user.id,
        intent=intent,
        status=status,
        active_only=active_only,
        limit=limit,
    )
    return ProcedureListResponse(
        procedures=[_detail_response(memory_service, procedure) for procedure in procedures]
    )


@router.get("/procedures/{procedure_id}", response_model=ProcedureDetailResponse)
def get_procedure_for_external_user(
    procedure_id: str,
    external_user_key: str = Query(min_length=1),
    memory_service: MemoryService = Depends(get_memory_service),
) -> ProcedureDetailResponse:
    user = memory_service.get_or_create_user(external_user_key=external_user_key)
    procedure = memory_service.get_procedure(procedure_id)
    if procedure is None:
        raise ProcedureNotFoundError("Procedure not found.")
    if procedure.user_id != user.id:
        raise ProcedureOwnershipError("Procedure belongs to another user.")
    return _detail_response(memory_service, procedure)


@router.patch("/procedures/{procedure_id}", response_model=ProcedureDetailResponse)
def update_procedure_for_external_user(
    procedure_id: str,
    request: InternalProcedurePatchRequest,
    memory_service: MemoryService = Depends(get_memory_service),
) -> ProcedureDetailResponse:
    user = memory_service.get_or_create_user(external_user_key=request.external_user_key)
    patch = ProcedurePatchRequest(
        user_id=user.id,
        status=request.status,
        current_step=request.current_step,
        progress_note=request.progress_note,
    )
    return patch_procedure(procedure_id, patch, memory_service)


@router.delete("/memory", response_model=MemoryDeletionResponse)
def delete_memory_for_external_user(
    external_user_key: str = Query(min_length=1),
    memory_service: MemoryService = Depends(get_memory_service),
) -> MemoryDeletionResponse:
    user = memory_service.get_or_create_user(external_user_key=external_user_key)
    memory_service.delete_user_memory(user.id)
    return MemoryDeletionResponse(
        user_id=user.id,
        deleted=True,
        message="User memory deleted. Official ChromaDB knowledge was not deleted.",
    )
