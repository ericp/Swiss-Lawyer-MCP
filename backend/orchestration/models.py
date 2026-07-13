"""Shared orchestration models for Phase 8."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from backend.models.clarification import ClarificationQuestion
from backend.models.generation import GeneratedAnswer
from backend.models.planner import ProcedurePlan, WorkflowStatus

DISCLAIMER = (
    "This information is based on retrieved official Swiss sources and is provided "
    "for informational purposes only. It does not constitute legal advice."
)


class ProcedureResponseState(str, Enum):
    """High-level API response state."""

    CLARIFICATION_REQUIRED = "clarification_required"
    ANSWERED = "answered"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    FAILED = "failed"


class SourceReference(BaseModel):
    """Source reference returned by the API."""

    chunk_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    page: int | None = None
    region: str | None = None
    retrieval_source: str = Field(min_length=1)
    rerank_score: float
    source_url: str | None = None
    document_title: str | None = None


class ProcedureQueryRequest(BaseModel):
    """Request body for querying a Swiss procedure."""

    external_user_key: str | None = None
    user_id: str | None = None
    procedure_id: str | None = None
    question: str = Field(min_length=1)
    profile_updates: dict[str, object] = Field(default_factory=dict)
    confirmed_profile_fields: list[str] = Field(default_factory=list)
    language: str | None = None
    retrieval_top_k: int | None = Field(default=None, ge=1, le=50)
    rerank_top_k: int | None = Field(default=None, ge=1, le=20)

    @model_validator(mode="after")
    def validate_user_identifier(self) -> ProcedureQueryRequest:
        if self.user_id and self.external_user_key:
            raise ValueError("Provide either user_id or external_user_key, not both.")
        return self


class ProcedureQueryResponse(BaseModel):
    """Structured response for the main procedure query endpoint."""

    user_id: str
    procedure_id: str | None = None
    intent: str
    state: ProcedureResponseState
    needs_clarification: bool
    clarification_questions: list[ClarificationQuestion]
    missing_fields: list[str]
    answer: GeneratedAnswer | None = None
    plan: ProcedurePlan | None = None
    sources: list[SourceReference]
    confidence: str | None = None
    insufficient_context: bool
    saved_profile_fields: list[str]
    workflow_status: WorkflowStatus | None = None
    disclaimer: str = DISCLAIMER


class ProcedurePatchRequest(BaseModel):
    """Controlled procedure update request."""

    user_id: str = Field(min_length=1)
    status: WorkflowStatus | None = None
    current_step: int | None = Field(default=None, ge=1)
    confirmed_profile_facts: dict[str, object] = Field(default_factory=dict)
    progress_note: str | None = None


class ProcedureDetailResponse(BaseModel):
    """Procedure detail response."""

    procedure_id: str
    user_id: str
    intent: str
    title: str
    status: WorkflowStatus
    summary: str
    plan: ProcedurePlan
    current_step: int | None
    recent_interaction_summaries: list[str]


class ProcedureListResponse(BaseModel):
    """Procedure list response."""

    procedures: list[ProcedureDetailResponse]


class MemoryDeletionResponse(BaseModel):
    """Memory deletion confirmation."""

    user_id: str
    deleted: bool
    message: str
