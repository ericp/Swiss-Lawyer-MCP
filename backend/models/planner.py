"""Pydantic models for procedure workflow planning."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from backend.models.generation import CitedSource


class WorkflowStatus(str, Enum):
    """Workflow status values for procedure plans."""

    READY_TO_START = "ready_to_start"
    NEEDS_MORE_INFORMATION = "needs_more_information"
    BLOCKED = "blocked"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ProcedureStep(BaseModel):
    """One actionable step in a Swiss administrative procedure."""

    step_number: int = Field(ge=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    responsible_party: str = Field(min_length=1)
    required_documents: list[str]
    estimated_time: str = Field(min_length=1)
    source_reference: CitedSource | None = None


class ProcedurePlan(BaseModel):
    """Structured workflow derived from grounded evidence."""

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    status: WorkflowStatus
    steps: list[ProcedureStep]
    required_documents: list[str]
    estimated_timelines: list[str]
    potential_blockers: list[str]
    next_recommended_action: str = Field(min_length=1)
    source_references: list[CitedSource]
    missing_information: list[str]
