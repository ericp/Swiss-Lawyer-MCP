"""Procedure repository for SQLite memory."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.memory.models import ProcedureORM, utc_now
from backend.models.planner import ProcedurePlan, WorkflowStatus

ACTIVE_STATUSES = {
    WorkflowStatus.READY_TO_START.value,
    WorkflowStatus.NEEDS_MORE_INFORMATION.value,
    WorkflowStatus.BLOCKED.value,
    WorkflowStatus.IN_PROGRESS.value,
}


class ProcedureRepository:
    """Persistence operations for saved procedures."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_procedure(
        self,
        *,
        user_id: str,
        intent: str,
        plan: ProcedurePlan,
        current_step: int | None = None,
    ) -> ProcedureORM:
        procedure = ProcedureORM(
            user_id=user_id,
            intent=intent,
            title=plan.title,
            status=plan.status.value,
            summary=plan.summary,
            plan_json=plan.model_dump(mode="json"),
            current_step=current_step,
        )
        self._session.add(procedure)
        self._session.flush()
        return procedure

    def get_procedure(self, procedure_id: str) -> ProcedureORM | None:
        procedure = self._session.get(ProcedureORM, procedure_id)
        if procedure is not None:
            procedure.last_accessed_at = utc_now()
            self._session.flush()
        return procedure

    def list_procedures_for_user(
        self,
        user_id: str,
        *,
        intent: str | None = None,
        limit: int | None = None,
    ) -> list[ProcedureORM]:
        statement = (
            select(ProcedureORM)
            .where(ProcedureORM.user_id == user_id)
            .order_by(ProcedureORM.last_accessed_at.desc())
        )
        if intent is not None:
            statement = statement.where(ProcedureORM.intent == intent)
        if limit is not None:
            statement = statement.limit(limit)
        return list(self._session.scalars(statement))

    def list_active_procedures(
        self,
        user_id: str,
        *,
        intent: str | None = None,
    ) -> list[ProcedureORM]:
        statement = (
            select(ProcedureORM)
            .where(ProcedureORM.user_id == user_id)
            .where(ProcedureORM.status.in_(ACTIVE_STATUSES))
            .order_by(ProcedureORM.last_accessed_at.desc())
        )
        if intent is not None:
            statement = statement.where(ProcedureORM.intent == intent)
        return list(self._session.scalars(statement))

    def update_procedure_plan(
        self,
        *,
        procedure_id: str,
        plan: ProcedurePlan,
    ) -> ProcedureORM:
        procedure = self._require_procedure(procedure_id)
        procedure.title = plan.title
        procedure.status = plan.status.value
        procedure.summary = plan.summary
        procedure.plan_json = plan.model_dump(mode="json")
        procedure.updated_at = utc_now()
        self._session.flush()
        return procedure

    def update_status(
        self,
        *,
        procedure_id: str,
        status: WorkflowStatus,
    ) -> ProcedureORM:
        procedure = self._require_procedure(procedure_id)
        procedure.status = status.value
        procedure.updated_at = utc_now()
        if status is WorkflowStatus.COMPLETED:
            procedure.completed_at = utc_now()
        self._session.flush()
        return procedure

    def update_current_step(
        self,
        *,
        procedure_id: str,
        current_step: int | None,
    ) -> ProcedureORM:
        procedure = self._require_procedure(procedure_id)
        procedure.current_step = current_step
        procedure.updated_at = utc_now()
        self._session.flush()
        return procedure

    def mark_completed(self, procedure_id: str) -> ProcedureORM:
        return self.update_status(
            procedure_id=procedure_id,
            status=WorkflowStatus.COMPLETED,
        )

    def delete_procedure(self, procedure_id: str) -> None:
        self._session.execute(
            delete(ProcedureORM).where(ProcedureORM.id == procedure_id)
        )
        self._session.flush()

    def _require_procedure(self, procedure_id: str) -> ProcedureORM:
        procedure = self._session.get(ProcedureORM, procedure_id)
        if procedure is None:
            raise ValueError(f"Procedure not found: {procedure_id}")
        return procedure
