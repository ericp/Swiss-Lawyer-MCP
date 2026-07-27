"""Strict MCP tool schemas."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.models.planner import WorkflowStatus

PROCEDURE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
PROCEDURE_ID_DESCRIPTION = (
    "Identifier of an existing saved Swiss Lawyer procedure. Provide this only "
    "when continuing or answering clarification questions for a previously "
    "created procedure. Obtain it from a prior consult_swiss_procedure response "
    "or get_my_procedures result. Do not invent this value. Current local "
    "procedure IDs are opaque strings up to 128 characters using letters, "
    "numbers, dots, underscores, colons, or hyphens."
)
LANGUAGE_PATTERN = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")
ProfileFieldName = Literal[
    "nationality",
    "current_country",
    "destination_canton",
    "destination_municipality",
    "purpose_of_stay",
    "employment_status",
    "has_job_offer",
    "eu_efta_citizen",
    "marital_status",
    "family_members",
    "planned_arrival_date",
    "current_permit",
    "age",
    "studies_status",
    "additional_context",
]
ConfirmedProfileFieldName = Annotated[
    ProfileFieldName,
    Field(description="One supported ProfileUpdates field name explicitly confirmed by the user."),
]
FamilyMember = Annotated[
    str,
    Field(
        min_length=1,
        max_length=80,
        description="Family member involved in the procedure, such as spouse, registered partner, or child.",
    ),
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileUpdates(StrictModel):
    """Explicit user facts ChatGPT may pass to consult_swiss_procedure."""

    nationality: str | None = Field(
        default=None,
        max_length=120,
        description="User's nationality or citizenship, for example 'Spanish' or 'Brazilian'.",
    )
    current_country: str | None = Field(
        default=None,
        max_length=120,
        description="Country where the user currently lives.",
    )
    destination_canton: str | None = Field(
        default=None,
        max_length=120,
        description="Swiss canton relevant to the procedure, for example 'Zurich'.",
    )
    destination_municipality: str | None = Field(
        default=None,
        max_length=120,
        description="Swiss municipality or city relevant to the procedure, for example 'Zurich'.",
    )
    purpose_of_stay: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Main reason for the Swiss procedure, such as employment, studies, "
            "family reunification, or residence without gainful activity."
        ),
    )
    employment_status: str | None = Field(
        default=None,
        max_length=200,
        description=(
            "Relevant employment situation, such as job offer received, employed, "
            "self-employed, job seeking, or not working."
        ),
    )
    has_job_offer: bool | None = Field(
        default=None,
        description="Whether the user already has a Swiss job offer.",
    )
    eu_efta_citizen: bool | None = Field(
        default=None,
        description="Whether the user is a citizen of an EU or EFTA country.",
    )
    marital_status: str | None = Field(
        default=None,
        max_length=120,
        description="Marital or registered-partnership status when relevant to the procedure.",
    )
    family_members: list[FamilyMember] | None = Field(
        default=None,
        max_length=20,
        description=(
            "Family members involved in the procedure, such as spouse, "
            "registered partner, or children."
        ),
    )
    planned_arrival_date: str | None = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Planned arrival date in Switzerland in YYYY-MM-DD format, when known.",
    )
    current_permit: str | None = Field(
        default=None,
        max_length=120,
        description="Current Swiss permit or immigration status, when applicable.",
    )
    age: int | None = Field(
        default=None,
        ge=0,
        le=120,
        description="User's age when legally relevant.",
    )
    studies_status: str | None = Field(
        default=None,
        max_length=200,
        description="Relevant studies or education status.",
    )
    additional_context: str | None = Field(
        default=None,
        max_length=5_000,
        description="Other facts materially relevant to the Swiss administrative procedure.",
    )


class ConsultSwissProcedureInput(StrictModel):
    question: str = Field(
        min_length=1,
        max_length=10_000,
        description=(
            "The user's current Swiss administrative or immigration question, "
            "follow-up answer, or clarification response."
        ),
    )
    procedure_id: str | None = Field(
        default=None,
        max_length=128,
        pattern=PROCEDURE_ID_PATTERN.pattern,
        description=PROCEDURE_ID_DESCRIPTION,
    )
    profile_updates: ProfileUpdates | None = Field(
        default=None,
        description=(
            "Explicitly provided user profile facts for this turn. Include only "
            "facts the user actually stated or confirmed."
        ),
    )
    confirmed_profile_fields: list[ConfirmedProfileFieldName] = Field(
        default_factory=list,
        max_length=50,
        description=(
            "Exact profile field names that the user has explicitly confirmed "
            "as correct in this turn. Values must be supported ProfileUpdates fields."
        ),
    )
    language: str | None = Field(
        default=None,
        max_length=12,
        description="Preferred ISO language code for the response, such as en, de, fr, or it.",
    )

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


class GetMyProceduresInput(StrictModel):
    procedure_id: str | None = Field(
        default=None,
        max_length=128,
        pattern=PROCEDURE_ID_PATTERN.pattern,
        description=PROCEDURE_ID_DESCRIPTION,
    )
    status: WorkflowStatus | None = Field(
        default=None,
        description=(
            "Optional workflow status filter. Allowed values are ready_to_start, "
            "needs_more_information, blocked, in_progress, and completed."
        ),
    )
    intent: str | None = Field(
        default=None,
        max_length=80,
        description="Optional procedure intent filter, such as immigration or driving_licence_exchange.",
    )
    active_only: bool = Field(
        default=False,
        description="When true, return only procedures that are not completed.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of procedures to return.",
    )

    @field_validator("procedure_id")
    @classmethod
    def validate_procedure_id(cls, value: str | None) -> str | None:
        if value is not None and not PROCEDURE_ID_PATTERN.match(value):
            raise ValueError("procedure_id has an invalid format")
        return value


class UpdateMyProcedureInput(StrictModel):
    procedure_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=PROCEDURE_ID_PATTERN.pattern,
        description=PROCEDURE_ID_DESCRIPTION,
    )
    status: WorkflowStatus | None = Field(
        default=None,
        description=(
            "New workflow status. Allowed values are ready_to_start, "
            "needs_more_information, blocked, in_progress, and completed."
        ),
    )
    current_step: int | None = Field(
        default=None,
        ge=1,
        description="Current step number in the saved procedure plan, starting at 1.",
    )
    progress_note: str | None = Field(
        default=None,
        max_length=5_000,
        description="Short user-provided note describing progress or a status change.",
    )

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
    confirmation: bool = Field(
        description=(
            "Must be true only after the user explicitly asks to delete all locally "
            "stored Swiss Lawyer memory."
        ),
    )

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
