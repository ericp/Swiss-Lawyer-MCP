"""Pydantic service models for SQLite memory."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from backend.models.planner import ProcedurePlan, WorkflowStatus
from backend.models.user_profile import UserProfile


class UserRecord(BaseModel):
    """Inspectable user memory record."""

    id: str = Field(min_length=1)
    external_user_key: str | None
    created_at: datetime
    updated_at: datetime
    last_active_at: datetime


class ProfileFact(BaseModel):
    """One stored user profile fact."""

    field_name: str = Field(min_length=1)
    value: Any
    source: str = Field(min_length=1)
    is_confirmed: bool
    updated_at: datetime


class SavedProcedure(BaseModel):
    """Saved procedure with validated workflow plan."""

    id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: WorkflowStatus
    summary: str
    plan: ProcedurePlan
    current_step: int | None
    created_at: datetime
    updated_at: datetime
    last_accessed_at: datetime


class ProcedureInteraction(BaseModel):
    """Concise interaction summary."""

    interaction_type: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    structured_payload: Any | None = None
    created_at: datetime


class UserMemory(BaseModel):
    """User memory snapshot."""

    user: UserRecord
    profile: list[ProfileFact]
    active_procedures: list[SavedProcedure]
    recent_procedure_summaries: list[ProcedureInteraction]


class MemoryContext(BaseModel):
    """Memory context loaded before future clarification."""

    user_profile: UserProfile
    active_procedure: SavedProcedure | None
    relevant_previous_procedures: list[SavedProcedure]
    recent_interaction_summaries: list[ProcedureInteraction]
