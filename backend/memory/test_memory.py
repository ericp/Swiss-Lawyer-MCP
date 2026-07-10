"""CLI demonstration for Phase 7 SQLite memory."""

from __future__ import annotations

from backend.memory.database import DEFAULT_DATABASE_URL, create_memory_engine, create_session_factory
from backend.memory.memory_service import MemoryService
from backend.models.generation import CitedSource
from backend.models.planner import ProcedurePlan, ProcedureStep, WorkflowStatus


def main() -> None:
    engine = create_memory_engine(DEFAULT_DATABASE_URL)
    service = MemoryService(session_factory=create_session_factory(engine))

    user = service.get_or_create_user(external_user_key="demo-user")
    print(f"Demo user: {user.id}")

    service.save_confirmed_profile_facts(
        user_id=user.id,
        facts={
            "nationality": "Brazil",
            "intended_city": "Zurich",
            "intended_canton": "Zurich",
        },
        source="user_confirmed",
    )

    profile = service.build_user_profile(user.id)
    print(f"Loaded UserProfile: {profile.model_dump(exclude_none=True)}")

    procedure = service.save_procedure_plan(
        user_id=user.id,
        intent="driving_licence_exchange",
        plan=_example_plan(),
        current_step=1,
    )
    service.record_interaction(
        procedure_id=procedure.id,
        interaction_type="answer_generated",
        summary="Generated grounded driving licence exchange guidance.",
        structured_payload={"confidence": "Medium"},
    )
    service.update_procedure_status(
        procedure_id=procedure.id,
        status=WorkflowStatus.IN_PROGRESS,
    )
    reloaded = service.get_procedure(procedure.id)
    print(f"Reloaded procedure status: {reloaded.status.value if reloaded else 'missing'}")

    context = service.build_memory_context(
        user_id=user.id,
        procedure_id=procedure.id,
    )
    print("MemoryContext:")
    print(context.model_dump(mode="json", exclude_none=True))

    deletion_demo = service.get_or_create_user(external_user_key="demo-delete-user")
    service.delete_user_memory(deletion_demo.id)
    print("Deleted separate demo-delete-user memory.")


def _example_plan() -> ProcedurePlan:
    source = CitedSource(
        source="driving_licence_exchange_zh.pdf",
        page=1,
        region="zh",
    )
    return ProcedurePlan(
        title="Foreign driving licence exchange in Zurich",
        summary="Example saved workflow for demonstrating memory persistence.",
        status=WorkflowStatus.READY_TO_START,
        steps=[
            ProcedureStep(
                step_number=1,
                title="Confirm residence start date",
                description="Confirm the date Swiss residence started before proceeding.",
                responsible_party="User",
                required_documents=["Not specified in retrieved sources."],
                estimated_time="Not specified in retrieved sources.",
                source_reference=source,
            )
        ],
        required_documents=["Not specified in retrieved sources."],
        estimated_timelines=["Not specified in retrieved sources."],
        potential_blockers=["Missing residence start date"],
        next_recommended_action="Confirm the Swiss residence start date.",
        source_references=[source],
        missing_information=["Swiss residence start date"],
    )


if __name__ == "__main__":
    main()
