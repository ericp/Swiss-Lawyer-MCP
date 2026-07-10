from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

from backend.memory.database import create_memory_engine, create_session_factory
from backend.memory.memory_service import MemoryService
from backend.memory.models import UserORM, UserProfileFactORM
from backend.memory.repositories.profile_repository import ProfileRepository
from backend.memory.repositories.user_repository import UserRepository
from backend.models.generation import CitedSource
from backend.models.planner import ProcedurePlan, ProcedureStep, WorkflowStatus


@pytest.fixture()
def memory_service(tmp_path: Path) -> MemoryService:
    database_url = _migrate_temp_database(tmp_path)
    engine = create_memory_engine(database_url)
    return MemoryService(session_factory=create_session_factory(engine))


def _migrate_temp_database(tmp_path: Path) -> str:
    database_path = tmp_path / "memory.db"
    database_url = f"sqlite:///{database_path}"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return database_url


def _example_plan(status: WorkflowStatus = WorkflowStatus.READY_TO_START) -> ProcedurePlan:
    source = CitedSource(source="permit.pdf", page=2, region="federal")
    return ProcedurePlan(
        title="Work permit procedure",
        summary="A saved work permit workflow.",
        status=status,
        steps=[
            ProcedureStep(
                step_number=1,
                title="Prepare documents",
                description="Prepare supported documents.",
                responsible_party="User",
                required_documents=["Passport copy"],
                estimated_time="Not specified in retrieved sources.",
                source_reference=source,
            )
        ],
        required_documents=["Passport copy"],
        estimated_timelines=["Not specified in retrieved sources."],
        potential_blockers=["Missing job offer"],
        next_recommended_action="Confirm the job offer details.",
        source_references=[source],
        missing_information=[],
    )


def test_database_initialization_through_migrations(tmp_path: Path) -> None:
    database_url = _migrate_temp_database(tmp_path)
    engine = create_memory_engine(database_url)
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) >= {
        "users",
        "user_profile_facts",
        "procedures",
        "procedure_interactions",
        "alembic_version",
    }
    unique_constraints = inspector.get_unique_constraints("user_profile_facts")
    assert any(
        constraint["name"] == "uq_user_profile_facts_user_field"
        for constraint in unique_constraints
    )


def test_user_creation_and_get_or_create_behavior(memory_service: MemoryService) -> None:
    created = memory_service.create_user(external_user_key="user-a")
    fetched = memory_service.get_user(created.id)
    same = memory_service.get_or_create_user(external_user_key="user-a")

    assert fetched is not None
    assert fetched.id == created.id
    assert same.id == created.id


def test_profile_fact_insert_update_and_confirmed_overwrite_protection(
    memory_service: MemoryService,
) -> None:
    user = memory_service.get_or_create_user(external_user_key="profile-user")

    inserted = memory_service.save_profile_fact(
        user_id=user.id,
        field_name="nationality",
        value="Brazil",
        source="user_confirmed",
        is_confirmed=True,
    )
    blocked = memory_service.save_profile_fact(
        user_id=user.id,
        field_name="nationality",
        value="Portugal",
        source="imported",
        is_confirmed=False,
    )
    corrected = memory_service.save_profile_fact(
        user_id=user.id,
        field_name="nationality",
        value="Portugal",
        source="user_confirmed",
        is_confirmed=True,
    )

    assert inserted.value == "Brazil"
    assert blocked.value == "Brazil"
    assert corrected.value == "Portugal"
    assert corrected.is_confirmed is True


def test_user_profile_reconstruction(memory_service: MemoryService) -> None:
    user = memory_service.get_or_create_user(external_user_key="profile-build-user")
    memory_service.save_confirmed_profile_facts(
        user_id=user.id,
        facts={
            "nationality": "Brazil",
            "intended_canton": "Zurich",
            "unsupported_field": "ignored",
        },
    )

    profile = memory_service.build_user_profile(user.id)

    assert profile.nationality == "Brazil"
    assert profile.intended_canton == "Zurich"
    assert not hasattr(profile, "unsupported_field")


def test_procedure_plan_serialization_creation_updates_and_active_retrieval(
    memory_service: MemoryService,
) -> None:
    user = memory_service.get_or_create_user(external_user_key="procedure-user")
    saved = memory_service.save_procedure_plan(
        user_id=user.id,
        intent="work_permit",
        plan=_example_plan(),
        current_step=1,
    )

    reloaded = memory_service.get_procedure(saved.id)
    assert reloaded is not None
    assert reloaded.plan == _example_plan()
    assert reloaded.current_step == 1

    updated_step = memory_service.update_current_step(
        procedure_id=saved.id,
        current_step=2,
    )
    assert updated_step.current_step == 2

    updated_status = memory_service.update_procedure_status(
        procedure_id=saved.id,
        status=WorkflowStatus.IN_PROGRESS,
    )
    assert updated_status.status is WorkflowStatus.IN_PROGRESS

    active = memory_service.list_active_procedures(
        user_id=user.id,
        intent="work_permit",
    )
    assert [procedure.id for procedure in active] == [saved.id]


def test_interaction_summary_storage_and_memory_context(
    memory_service: MemoryService,
) -> None:
    user = memory_service.get_or_create_user(external_user_key="context-user")
    memory_service.save_confirmed_profile_facts(
        user_id=user.id,
        facts={"nationality": "Brazil", "intended_canton": "Zurich"},
    )
    procedure = memory_service.save_procedure_plan(
        user_id=user.id,
        intent="work_permit",
        plan=_example_plan(),
        current_step=1,
    )
    interaction = memory_service.record_interaction(
        procedure_id=procedure.id,
        interaction_type="procedure_resumed",
        summary="User resumed the work permit workflow.",
        structured_payload={"current_step": 1},
    )

    context = memory_service.build_memory_context(
        user_id=user.id,
        question="Can I work in Switzerland?",
        procedure_id=procedure.id,
    )

    assert interaction.summary == "User resumed the work permit workflow."
    assert context.user_profile.nationality == "Brazil"
    assert context.active_procedure is not None
    assert context.active_procedure.id == procedure.id
    assert context.active_procedure.current_step == 1
    assert any(
        item.summary == "User resumed the work permit workflow."
        for item in context.recent_interaction_summaries
    )


def test_user_memory_deletion_cascades(memory_service: MemoryService) -> None:
    user = memory_service.get_or_create_user(external_user_key="delete-user")
    memory_service.save_confirmed_profile_facts(
        user_id=user.id,
        facts={"nationality": "Brazil"},
    )
    procedure = memory_service.save_procedure_plan(
        user_id=user.id,
        intent="work_permit",
        plan=_example_plan(),
    )
    memory_service.record_interaction(
        procedure_id=procedure.id,
        interaction_type="procedure_resumed",
        summary="Resume summary.",
    )

    memory_service.delete_user_memory(user.id)

    assert memory_service.get_user(user.id) is None
    assert memory_service.get_procedure(procedure.id) is None


def test_foreign_key_and_unique_constraints(tmp_path: Path) -> None:
    database_url = _migrate_temp_database(tmp_path)
    engine = create_memory_engine(database_url)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        with pytest.raises(IntegrityError):
            with session.begin():
                session.add(
                    UserProfileFactORM(
                        user_id="missing-user",
                        field_name="nationality",
                        value_json="Brazil",
                        source="user_confirmed",
                        is_confirmed=True,
                    )
                )

    with session_factory() as session, session.begin():
        user = UserRepository(session).create_user(external_user_key="unique-user")
        ProfileRepository(session).upsert_profile_fact(
            user_id=user.id,
            field_name="nationality",
            value="Brazil",
            source="user_confirmed",
            is_confirmed=True,
        )
        session.add(
            UserProfileFactORM(
                user_id=user.id,
                field_name="nationality",
                value_json="Portugal",
                source="user_confirmed",
                is_confirmed=True,
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_transaction_rollback_on_failure(tmp_path: Path) -> None:
    database_url = _migrate_temp_database(tmp_path)
    engine = create_memory_engine(database_url)
    session_factory = create_session_factory(engine)

    with session_factory() as session, session.begin():
        UserRepository(session).create_user(external_user_key="rollback-user")

    with pytest.raises(IntegrityError):
        with session_factory() as session, session.begin():
            session.add(UserORM(external_user_key="rollback-user"))
            session.add(UserORM(external_user_key="should-rollback"))

    with session_factory() as session:
        count = session.scalar(select(func.count()).select_from(UserORM))
        keys = list(session.scalars(select(UserORM.external_user_key)))

    assert count == 1
    assert keys == ["rollback-user"]
