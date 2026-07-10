"""Conversion helpers between ORM and Pydantic memory models."""

from __future__ import annotations

from backend.memory.models import (
    ProcedureInteractionORM,
    ProcedureORM,
    UserORM,
    UserProfileFactORM,
)
from backend.models.memory import (
    ProcedureInteraction,
    ProfileFact,
    SavedProcedure,
    UserRecord,
)
from backend.models.planner import ProcedurePlan, WorkflowStatus


def user_to_record(user: UserORM) -> UserRecord:
    """Convert a user ORM row to a Pydantic record."""

    return UserRecord(
        id=user.id,
        external_user_key=user.external_user_key,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_active_at=user.last_active_at,
    )


def fact_to_model(fact: UserProfileFactORM) -> ProfileFact:
    """Convert a profile fact ORM row to a Pydantic model."""

    return ProfileFact(
        field_name=fact.field_name,
        value=fact.value_json,
        source=fact.source,
        is_confirmed=fact.is_confirmed,
        updated_at=fact.updated_at,
    )


def procedure_to_model(procedure: ProcedureORM) -> SavedProcedure:
    """Convert a procedure ORM row to a Pydantic model."""

    return SavedProcedure(
        id=procedure.id,
        user_id=procedure.user_id,
        intent=procedure.intent,
        title=procedure.title,
        status=WorkflowStatus(procedure.status),
        summary=procedure.summary,
        plan=ProcedurePlan.model_validate(procedure.plan_json),
        current_step=procedure.current_step,
        created_at=procedure.created_at,
        updated_at=procedure.updated_at,
        last_accessed_at=procedure.last_accessed_at,
    )


def interaction_to_model(interaction: ProcedureInteractionORM) -> ProcedureInteraction:
    """Convert an interaction ORM row to a Pydantic model."""

    return ProcedureInteraction(
        interaction_type=interaction.interaction_type,
        summary=interaction.summary,
        structured_payload=interaction.structured_payload_json,
        created_at=interaction.created_at,
    )
