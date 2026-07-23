"""Strict MCP tool schemas."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.models.planner import WorkflowStatus

PROCEDURE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
LANGUAGE_PATTERN = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConsultSwissProcedureInput(StrictModel):
    question: str = Field(min_length=1, max_length=10_000)
    procedure_id: str | None = Field(default=None, max_length=128)
    profile_updates: dict[str, Any] = Field(default_factory=dict)
    confirmed_profile_fields: list[str] = Field(default_factory=list, max_length=50)
    language: str | None = Field(default=None, max_length=12)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped

    @field_validator("procedure_id")
    @classmethod
    def validate_procedure_id(cls, value: str | None) -> str | None:
        if value is not None and not PROCEDURE_ID_PATTERN.match(value):
            raise ValueError("procedure_id has an invalid format")
        return value

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str | None) -> str | None:
        if value is not None and not LANGUAGE_PATTERN.match(value):
            raise ValueError("language must look like en or en-US")
        return value

    @field_validator("profile_updates")
    @classmethod
    def validate_profile_updates(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 50:
            raise ValueError("too many profile fields")
        for field_name, field_value in value.items():
            if len(str(field_name)) > 80:
                raise ValueError("profile field name is too long")
            if len(str(field_value)) > 5_000:
                raise ValueError("profile field value is too long")
        return value


class GetMyProceduresInput(StrictModel):
    procedure_id: str | None = Field(default=None, max_length=128)
    status: WorkflowStatus | None = None
    intent: str | None = Field(default=None, max_length=80)
    active_only: bool = False
    limit: int = Field(default=20, ge=1, le=100)

    @field_validator("procedure_id")
    @classmethod
    def validate_procedure_id(cls, value: str | None) -> str | None:
        if value is not None and not PROCEDURE_ID_PATTERN.match(value):
            raise ValueError("procedure_id has an invalid format")
        return value


class UpdateMyProcedureInput(StrictModel):
    procedure_id: str = Field(min_length=1, max_length=128)
    status: WorkflowStatus | None = None
    current_step: int | None = Field(default=None, ge=1)
    progress_note: str | None = Field(default=None, max_length=5_000)

    @field_validator("procedure_id")
    @classmethod
    def validate_procedure_id(cls, value: str) -> str:
        if not PROCEDURE_ID_PATTERN.match(value):
            raise ValueError("procedure_id has an invalid format")
        return value

    @model_validator(mode="after")
    def require_update(self) -> UpdateMyProcedureInput:
        if self.status is None and self.current_step is None and not self.progress_note:
            raise ValueError("At least one update field is required")
        return self


class DeleteMySwissLawyerDataInput(StrictModel):
    confirmation: bool

    @model_validator(mode="after")
    def require_confirmation(self) -> DeleteMySwissLawyerDataInput:
        if self.confirmation is not True:
            raise ValueError("confirmation must be true")
        return self


class MCPToolResult(StrictModel):
    state: str | None = None
    procedure_id: str | None = None
    intent: str | None = None
    needs_clarification: bool | None = None
    clarification_questions: list[Any] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    answer: Any | None = None
    plan: Any | None = None
    sources: list[Any] = Field(default_factory=list)
    confidence: str | None = None
    insufficient_context: bool | None = None
    saved_profile_fields: list[str] = Field(default_factory=list)
    workflow_status: str | None = None
    disclaimer: str | None = None
    procedures: list[Any] = Field(default_factory=list)
    current_step: int | None = None
    recent_interaction_summaries: list[str] = Field(default_factory=list)
    deleted: bool | None = None
    message: str | None = None
