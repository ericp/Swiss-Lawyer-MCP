"""Procedure interaction repository for SQLite memory."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.memory.models import ProcedureInteractionORM


class InteractionRepository:
    """Persistence operations for concise procedure interaction summaries."""

    SUPPORTED_INTERACTION_TYPES = {
        "procedure_created",
        "clarification_requested",
        "user_information_added",
        "answer_generated",
        "plan_updated",
        "status_changed",
        "procedure_resumed",
        "procedure_completed",
    }

    def __init__(self, session: Session) -> None:
        self._session = session

    def add_interaction_summary(
        self,
        *,
        procedure_id: str,
        interaction_type: str,
        summary: str,
        structured_payload: Any | None = None,
    ) -> ProcedureInteractionORM:
        if interaction_type not in self.SUPPORTED_INTERACTION_TYPES:
            raise ValueError(f"Unsupported interaction type: {interaction_type}")
        interaction = ProcedureInteractionORM(
            procedure_id=procedure_id,
            interaction_type=interaction_type,
            summary=summary,
            structured_payload_json=structured_payload,
        )
        self._session.add(interaction)
        self._session.flush()
        return interaction

    def list_recent_interactions(
        self,
        *,
        procedure_ids: list[str],
        limit: int = 10,
    ) -> list[ProcedureInteractionORM]:
        if not procedure_ids:
            return []
        return list(
            self._session.scalars(
                select(ProcedureInteractionORM)
                .where(ProcedureInteractionORM.procedure_id.in_(procedure_ids))
                .order_by(ProcedureInteractionORM.created_at.desc())
                .limit(limit)
            )
        )

    def list_interactions_for_procedure(
        self,
        *,
        procedure_id: str,
        limit: int | None = None,
    ) -> list[ProcedureInteractionORM]:
        statement = (
            select(ProcedureInteractionORM)
            .where(ProcedureInteractionORM.procedure_id == procedure_id)
            .order_by(ProcedureInteractionORM.created_at.desc())
        )
        if limit is not None:
            statement = statement.limit(limit)
        return list(self._session.scalars(statement))
