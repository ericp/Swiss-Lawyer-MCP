"""Service layer for user memory and resumable procedures."""

from __future__ import annotations

from typing import Any

from backend.clarification.procedure_schemas import list_procedure_schemas
from backend.memory.database import SessionFactory
from backend.memory.repositories.converters import (
    fact_to_model,
    interaction_to_model,
    procedure_to_model,
    user_to_record,
)
from backend.memory.repositories.interaction_repository import InteractionRepository
from backend.memory.repositories.procedure_repository import ProcedureRepository
from backend.memory.repositories.profile_repository import ProfileRepository
from backend.memory.repositories.user_repository import UserRepository
from backend.models.memory import (
    MemoryContext,
    ProcedureInteraction,
    ProfileFact,
    SavedProcedure,
    UserMemory,
    UserRecord,
)
from backend.models.planner import ProcedurePlan, WorkflowStatus
from backend.models.user_profile import UserProfile


class MemoryService:
    """High-level API for SQLite user memory and procedure progress."""

    def __init__(self, *, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def create_user(self, *, external_user_key: str | None = None) -> UserRecord:
        with self._session_factory() as session, session.begin():
            user = UserRepository(session).create_user(
                external_user_key=external_user_key,
            )
            return user_to_record(user)

    def get_or_create_user(
        self,
        *,
        external_user_key: str,
    ) -> UserRecord:
        with self._session_factory() as session, session.begin():
            user = UserRepository(session).get_or_create_by_external_user_key(
                external_user_key
            )
            return user_to_record(user)

    def get_user(self, user_id: str) -> UserRecord | None:
        with self._session_factory() as session:
            user = UserRepository(session).get_user(user_id)
            return user_to_record(user) if user is not None else None

    def update_last_active_at(self, user_id: str) -> UserRecord:
        with self._session_factory() as session, session.begin():
            user = UserRepository(session).update_last_active_at(user_id)
            return user_to_record(user)

    def save_profile_fact(
        self,
        *,
        user_id: str,
        field_name: str,
        value: Any,
        source: str,
        is_confirmed: bool,
    ) -> ProfileFact:
        with self._session_factory() as session, session.begin():
            fact = ProfileRepository(session).upsert_profile_fact(
                user_id=user_id,
                field_name=field_name,
                value=value,
                source=source,
                is_confirmed=is_confirmed,
            )
            return fact_to_model(fact)

    def save_confirmed_profile_facts(
        self,
        *,
        user_id: str,
        facts: dict[str, Any],
        source: str = "user_confirmed",
    ) -> list[ProfileFact]:
        saved: list[ProfileFact] = []
        with self._session_factory() as session, session.begin():
            repository = ProfileRepository(session)
            for field_name, value in facts.items():
                saved.append(
                    fact_to_model(
                        repository.upsert_profile_fact(
                            user_id=user_id,
                            field_name=field_name,
                            value=value,
                            source=source,
                            is_confirmed=True,
                        )
                    )
                )
            return saved

    def list_profile_facts(self, user_id: str) -> list[ProfileFact]:
        with self._session_factory() as session:
            facts = ProfileRepository(session).get_all_profile_facts(user_id)
            return [fact_to_model(fact) for fact in facts]

    def build_user_profile(self, user_id: str) -> UserProfile:
        facts = self.list_profile_facts(user_id)
        allowed_fields = set(UserProfile.model_fields)
        values = {
            fact.field_name: fact.value
            for fact in facts
            if fact.field_name in allowed_fields
        }
        return UserProfile.model_validate(values)

    def delete_profile_fact(self, *, user_id: str, field_name: str) -> None:
        with self._session_factory() as session, session.begin():
            ProfileRepository(session).delete_profile_fact(
                user_id=user_id,
                field_name=field_name,
            )

    def clear_profile_facts(self, user_id: str) -> None:
        with self._session_factory() as session, session.begin():
            ProfileRepository(session).clear_profile_facts(user_id)

    def save_procedure_plan(
        self,
        *,
        user_id: str,
        intent: str,
        plan: ProcedurePlan,
        current_step: int | None = None,
    ) -> SavedProcedure:
        with self._session_factory() as session, session.begin():
            procedure = ProcedureRepository(session).create_procedure(
                user_id=user_id,
                intent=intent,
                plan=plan,
                current_step=current_step,
            )
            InteractionRepository(session).add_interaction_summary(
                procedure_id=procedure.id,
                interaction_type="procedure_created",
                summary=f"Created procedure plan: {plan.title}",
                structured_payload={"status": plan.status.value},
            )
            return procedure_to_model(procedure)

    def get_procedure(self, procedure_id: str) -> SavedProcedure | None:
        with self._session_factory() as session, session.begin():
            procedure = ProcedureRepository(session).get_procedure(procedure_id)
            return procedure_to_model(procedure) if procedure is not None else None

    def list_active_procedures(
        self,
        *,
        user_id: str,
        intent: str | None = None,
    ) -> list[SavedProcedure]:
        with self._session_factory() as session:
            procedures = ProcedureRepository(session).list_active_procedures(
                user_id,
                intent=intent,
            )
            return [procedure_to_model(procedure) for procedure in procedures]

    def update_procedure_plan(
        self,
        *,
        procedure_id: str,
        plan: ProcedurePlan,
    ) -> SavedProcedure:
        with self._session_factory() as session, session.begin():
            procedure = ProcedureRepository(session).update_procedure_plan(
                procedure_id=procedure_id,
                plan=plan,
            )
            InteractionRepository(session).add_interaction_summary(
                procedure_id=procedure_id,
                interaction_type="plan_updated",
                summary=f"Updated procedure plan: {plan.title}",
                structured_payload={"status": plan.status.value},
            )
            return procedure_to_model(procedure)

    def update_procedure_status(
        self,
        *,
        procedure_id: str,
        status: WorkflowStatus,
    ) -> SavedProcedure:
        with self._session_factory() as session, session.begin():
            procedure = ProcedureRepository(session).update_status(
                procedure_id=procedure_id,
                status=status,
            )
            interaction_type = (
                "procedure_completed"
                if status is WorkflowStatus.COMPLETED
                else "status_changed"
            )
            InteractionRepository(session).add_interaction_summary(
                procedure_id=procedure_id,
                interaction_type=interaction_type,
                summary=f"Procedure status changed to {status.value}.",
                structured_payload={"status": status.value},
            )
            return procedure_to_model(procedure)

    def update_current_step(
        self,
        *,
        procedure_id: str,
        current_step: int | None,
    ) -> SavedProcedure:
        with self._session_factory() as session, session.begin():
            procedure = ProcedureRepository(session).update_current_step(
                procedure_id=procedure_id,
                current_step=current_step,
            )
            return procedure_to_model(procedure)

    def record_interaction(
        self,
        *,
        procedure_id: str,
        interaction_type: str,
        summary: str,
        structured_payload: Any | None = None,
    ) -> ProcedureInteraction:
        with self._session_factory() as session, session.begin():
            interaction = InteractionRepository(session).add_interaction_summary(
                procedure_id=procedure_id,
                interaction_type=interaction_type,
                summary=summary,
                structured_payload=structured_payload,
            )
            return interaction_to_model(interaction)

    def list_recent_interactions(
        self,
        *,
        procedure_ids: list[str],
        limit: int = 10,
    ) -> list[ProcedureInteraction]:
        with self._session_factory() as session:
            interactions = InteractionRepository(session).list_recent_interactions(
                procedure_ids=procedure_ids,
                limit=limit,
            )
            return [interaction_to_model(interaction) for interaction in interactions]

    def build_memory_context(
        self,
        *,
        user_id: str,
        question: str | None = None,
        procedure_id: str | None = None,
        intent: str | None = None,
    ) -> MemoryContext:
        inferred_intent = intent or _infer_intent_from_question(question)
        user_profile = self.build_user_profile(user_id)

        with self._session_factory() as session, session.begin():
            procedure_repository = ProcedureRepository(session)
            active_procedure = None
            if procedure_id is not None:
                procedure = procedure_repository.get_procedure(procedure_id)
                active_procedure = (
                    procedure_to_model(procedure) if procedure is not None else None
                )

            active_rows = procedure_repository.list_active_procedures(
                user_id,
                intent=inferred_intent,
            )
            relevant_previous_procedures = [
                procedure_to_model(procedure) for procedure in active_rows
            ]
            if active_procedure is None and relevant_previous_procedures:
                active_procedure = relevant_previous_procedures[0]

            procedure_ids = [procedure.id for procedure in relevant_previous_procedures]
            if active_procedure is not None and active_procedure.id not in procedure_ids:
                procedure_ids.append(active_procedure.id)
            interactions = InteractionRepository(session).list_recent_interactions(
                procedure_ids=procedure_ids,
                limit=10,
            )

            return MemoryContext(
                user_profile=user_profile,
                active_procedure=active_procedure,
                relevant_previous_procedures=relevant_previous_procedures,
                recent_interaction_summaries=[
                    interaction_to_model(interaction) for interaction in interactions
                ],
            )

    def get_user_memory(self, user_id: str) -> UserMemory:
        with self._session_factory() as session, session.begin():
            user = UserRepository(session)._require_user(user_id)
            profile = [
                fact_to_model(fact)
                for fact in ProfileRepository(session).get_all_profile_facts(user_id)
            ]
            active_procedures = [
                procedure_to_model(procedure)
                for procedure in ProcedureRepository(session).list_active_procedures(
                    user_id
                )
            ]
            interactions = InteractionRepository(session).list_recent_interactions(
                procedure_ids=[procedure.id for procedure in active_procedures],
                limit=10,
            )
            return UserMemory(
                user=user_to_record(user),
                profile=profile,
                active_procedures=active_procedures,
                recent_procedure_summaries=[
                    interaction_to_model(interaction) for interaction in interactions
                ],
            )

    def delete_user_memory(self, user_id: str) -> None:
        with self._session_factory() as session, session.begin():
            UserRepository(session).delete_user(user_id)


def _infer_intent_from_question(question: str | None) -> str | None:
    if not question:
        return None
    normalized_question = question.lower()
    for schema in list_procedure_schemas():
        if any(keyword in normalized_question for keyword in schema.intent_keywords):
            return schema.intent
    return None
