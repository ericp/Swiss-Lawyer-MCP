from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from backend.api import dependencies
from backend.api.app import create_app
from backend.api.routes import health as health_route
from backend.clarification.clarification_engine import ClarificationEngine
from backend.clarification.intent_classifier import IntentClassifier
from backend.location.canton_resolver import CantonResolver
from backend.memory.database import create_memory_engine, create_session_factory
from backend.memory.memory_service import MemoryService
from backend.models.chunk import ChunkMetadata
from backend.models.clarification import DetectedIntent
from backend.models.generation import CitedSource, GeneratedAnswer
from backend.models.planner import ProcedurePlan, ProcedureStep, WorkflowStatus
from backend.models.reranking import RerankedChunk, RerankResult
from backend.models.retrieval import HybridRetrievalResult, RetrievedChunk
from backend.orchestration.models import (
    ProcedureQueryRequest,
    ProcedureQueryResponse,
    ProcedureResponseState,
)
from backend.orchestration.procedure_orchestrator import ProcedureOrchestrator


@pytest.fixture()
def memory_service(tmp_path: Path) -> MemoryService:
    database_path = tmp_path / "memory.db"
    database_url = f"sqlite:///{database_path}"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    engine = create_memory_engine(database_url)
    return MemoryService(session_factory=create_session_factory(engine))


def _example_plan(status: WorkflowStatus = WorkflowStatus.READY_TO_START) -> ProcedurePlan:
    source = CitedSource(source="permit.pdf", page=2, region="ZH")
    return ProcedurePlan(
        title="Immigration procedure in Zurich",
        summary="A grounded procedure workflow.",
        status=status,
        steps=[
            ProcedureStep(
                step_number=1,
                title="Prepare the application",
                description="Prepare the supported application materials.",
                responsible_party="User",
                required_documents=["Passport"],
                estimated_time="Not specified in retrieved sources.",
                source_reference=source,
            )
        ],
        required_documents=["Passport"],
        estimated_timelines=["Not specified in retrieved sources."],
        potential_blockers=[],
        next_recommended_action="Confirm the competent authority.",
        source_references=[source],
        missing_information=[],
    )


def _answer(insufficient: bool = False) -> GeneratedAnswer:
    return GeneratedAnswer(
        answer=(
            "The retrieved official documentation does not contain enough information "
            "to answer this question completely."
            if insufficient
            else "A Brazilian citizen may need a permit before moving for work."
        ),
        explanation="This is based on the supplied official context.",
        procedure_steps=["Check permit requirements"] if not insufficient else [],
        important_notes=["Procedural guidance only."],
        cited_sources=[CitedSource(source="permit.pdf", page=2, region="ZH")],
        confidence="Medium",
        insufficient_context=insufficient,
    )


def _retrieved_chunk() -> RetrievedChunk:
    return RetrievedChunk(
        id="chunk-1",
        text="Brazilian citizens may require a permit before working in Switzerland.",
        metadata=ChunkMetadata(source="permit.pdf", page=2, region="ZH"),
        score=0.8,
        retrieval_source="vector",
    )


def _reranked_chunks(*, duplicate_source: bool = False) -> list[RerankedChunk]:
    first = RerankedChunk(
        chunk_id="chunk-1",
        text="Brazilian citizens may require a permit.",
        metadata=ChunkMetadata(source="permit.pdf", page=2, region="ZH"),
        retrieval_source="vector",
        retrieval_score=0.8,
        rerank_score=4.2,
    )
    if not duplicate_source:
        return [first]
    second = first.model_copy(update={"chunk_id": "chunk-2", "rerank_score": 3.9})
    return [first, second]


class FakeHybridRetriever:
    def __init__(self) -> None:
        self.called = False

    def retrieve(self, query: str, *, top_k: int = 10) -> HybridRetrievalResult:
        self.called = True
        chunk = _retrieved_chunk()
        return HybridRetrievalResult(
            query=query,
            vector_results=[chunk],
            bm25_results=[],
            merged_results=[chunk],
        )


class FakeReranker:
    def __init__(self, *, duplicate_source: bool = False) -> None:
        self.called = False
        self.duplicate_source = duplicate_source

    def rerank(
        self,
        *,
        query: str,
        retrieved_chunks: list[RetrievedChunk],
        top_k: int = 5,
    ) -> RerankResult:
        self.called = True
        chunks = _reranked_chunks(duplicate_source=self.duplicate_source)[:top_k]
        return RerankResult(
            query=query,
            total_candidates=len(retrieved_chunks),
            selected_candidates=len(chunks),
            chunks=chunks,
        )


class FakeAnswerGenerator:
    def __init__(self, *, insufficient: bool = False) -> None:
        self.insufficient = insufficient
        self.called = False

    def generate(self, **kwargs: Any) -> GeneratedAnswer:
        self.called = True
        return _answer(insufficient=self.insufficient)


class FakeWorkflowPlanner:
    def __init__(self) -> None:
        self.called = False

    def create_plan(self, **kwargs: Any) -> ProcedurePlan:
        self.called = True
        return _example_plan()


def _orchestrator(
    memory_service: MemoryService,
    *,
    hybrid: FakeHybridRetriever | None = None,
    reranker: FakeReranker | None = None,
    answer_generator: FakeAnswerGenerator | None = None,
    planner: FakeWorkflowPlanner | None = None,
) -> ProcedureOrchestrator:
    return ProcedureOrchestrator(
        memory_service=memory_service,
        intent_classifier=IntentClassifier(),
        clarification_engine=ClarificationEngine(),
        hybrid_retriever=hybrid or FakeHybridRetriever(),
        reranker=reranker or FakeReranker(),
        answer_generator=answer_generator or FakeAnswerGenerator(),
        workflow_planner=planner or FakeWorkflowPlanner(),
        canton_resolver=CantonResolver(),
    )


def test_city_to_canton_resolution_and_unknown_city_handling() -> None:
    resolver = CantonResolver()

    zurich = resolver.resolve("Zurich")
    unknown = resolver.resolve("Atlantis")
    ambiguous = resolver.resolve("Baden")

    assert zurich.is_resolved is True
    assert zurich.canton == "ZH"
    assert unknown.needs_clarification is True
    assert ambiguous.needs_clarification is True


def test_clarification_required_stops_before_retrieval(
    memory_service: MemoryService,
) -> None:
    hybrid = FakeHybridRetriever()
    orchestrator = _orchestrator(memory_service, hybrid=hybrid)

    response = orchestrator.handle_query(
        ProcedureQueryRequest(
            external_user_key="clarify-user",
            question="Can I move to Switzerland as a Brazilian citizen?",
            profile_updates={"nationality": "Brazil"},
            confirmed_profile_fields=["nationality"],
        )
    )

    assert response.state is ProcedureResponseState.CLARIFICATION_REQUIRED
    assert response.needs_clarification is True
    assert "purpose_of_stay" in response.missing_fields
    assert hybrid.called is False


def test_confirmed_profile_updates_persist_and_unconfirmed_updates_do_not(
    memory_service: MemoryService,
) -> None:
    orchestrator = _orchestrator(memory_service)

    unconfirmed = orchestrator.handle_query(
        ProcedureQueryRequest(
            external_user_key="profile-user",
            question="Can I move to Switzerland?",
            profile_updates={"nationality": "Brazil"},
            confirmed_profile_fields=[],
        )
    )
    assert memory_service.list_profile_facts(unconfirmed.user_id) == []

    confirmed = orchestrator.handle_query(
        ProcedureQueryRequest(
            user_id=unconfirmed.user_id,
            question="Can I move to Switzerland?",
            profile_updates={"nationality": "Brazil"},
            confirmed_profile_fields=["nationality"],
        )
    )

    facts = memory_service.list_profile_facts(confirmed.user_id)
    assert {fact.field_name: fact.value for fact in facts} == {"nationality": "Brazil"}


def test_successful_pipeline_creates_procedure_and_deduplicates_sources(
    memory_service: MemoryService,
) -> None:
    reranker = FakeReranker(duplicate_source=True)
    planner = FakeWorkflowPlanner()
    orchestrator = _orchestrator(memory_service, reranker=reranker, planner=planner)

    response = orchestrator.handle_query(
        ProcedureQueryRequest(
            external_user_key="success-user",
            question="Can I move to Switzerland for work?",
            profile_updates={
                "nationality": "Brazil",
                "intended_city": "Zurich",
                "purpose_of_stay": "employment",
                "employment_status": "has Swiss job offer",
            },
            confirmed_profile_fields=[
                "nationality",
                "intended_city",
                "purpose_of_stay",
                "employment_status",
            ],
        )
    )

    assert response.state is ProcedureResponseState.ANSWERED
    assert response.procedure_id is not None
    assert response.workflow_status is WorkflowStatus.READY_TO_START
    assert len(response.sources) == 1
    assert planner.called is True
    profile = memory_service.build_user_profile(response.user_id)
    assert profile.intended_city == "Zurich"
    assert profile.intended_canton == "ZH"


def test_insufficient_context_does_not_create_plan(
    memory_service: MemoryService,
) -> None:
    planner = FakeWorkflowPlanner()
    orchestrator = _orchestrator(
        memory_service,
        answer_generator=FakeAnswerGenerator(insufficient=True),
        planner=planner,
    )

    response = orchestrator.handle_query(
        ProcedureQueryRequest(
            external_user_key="insufficient-user",
            question="Can I move to Switzerland for work?",
            profile_updates={
                "nationality": "Brazil",
                "intended_canton": "ZH",
                "purpose_of_stay": "employment",
                "employment_status": "has Swiss job offer",
            },
            confirmed_profile_fields=[
                "nationality",
                "intended_canton",
                "purpose_of_stay",
                "employment_status",
            ],
        )
    )

    assert response.state is ProcedureResponseState.INSUFFICIENT_CONTEXT
    assert response.procedure_id is None
    assert response.plan is None
    assert planner.called is False


class FakeAPIOrchestrator:
    def __init__(self, response: ProcedureQueryResponse | None = None) -> None:
        self.response = response
        self.request: ProcedureQueryRequest | None = None

    def handle_query(self, request: ProcedureQueryRequest) -> ProcedureQueryResponse:
        self.request = request
        if self.response is not None:
            return self.response
        return ProcedureQueryResponse(
            user_id="anonymous-user",
            procedure_id=None,
            intent="immigration",
            state=ProcedureResponseState.CLARIFICATION_REQUIRED,
            needs_clarification=True,
            clarification_questions=[],
            missing_fields=["intended_canton"],
            sources=[],
            confidence=None,
            insufficient_context=False,
            saved_profile_fields=[],
            workflow_status=None,
        )


@pytest.fixture()
def client(memory_service: MemoryService) -> TestClient:
    app = create_app()
    app.dependency_overrides[dependencies.get_memory_service] = lambda: memory_service
    app.dependency_overrides[dependencies.get_orchestrator] = lambda: FakeAPIOrchestrator()
    return TestClient(app, raise_server_exceptions=False)


def test_health_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        health_route,
        "check_health_components",
        lambda: {
            "application": "healthy",
            "sqlite": "healthy",
            "chromadb": "healthy",
            "openai_configuration": "available",
        },
    )
    app = create_app()
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_query_endpoint_accepts_anonymous_user(client: TestClient) -> None:
    response = client.post(
        "/v1/procedures/query",
        json={"question": "Can I move to Switzerland?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "anonymous-user"
    assert payload["state"] == "clarification_required"


def test_procedure_read_list_patch_and_delete_routes(
    client: TestClient,
    memory_service: MemoryService,
) -> None:
    user = memory_service.get_or_create_user(external_user_key="route-user")
    procedure = memory_service.save_procedure_plan(
        user_id=user.id,
        intent="immigration",
        plan=_example_plan(),
        current_step=1,
    )

    listed = client.get(f"/v1/users/{user.id}/procedures")
    detail = client.get(f"/v1/procedures/{procedure.id}", params={"user_id": user.id})
    patched = client.patch(
        f"/v1/procedures/{procedure.id}",
        json={
            "user_id": user.id,
            "status": "in_progress",
            "current_step": 1,
            "confirmed_profile_facts": {"nationality": "Brazil"},
            "progress_note": "User started preparing documents.",
        },
    )

    assert listed.status_code == 200
    assert listed.json()["procedures"][0]["procedure_id"] == procedure.id
    assert detail.status_code == 200
    assert detail.json()["procedure_id"] == procedure.id
    assert patched.status_code == 200
    assert patched.json()["status"] == "in_progress"
    assert memory_service.build_user_profile(user.id).nationality == "Brazil"

    deleted = client.delete(f"/v1/users/{user.id}/memory")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert memory_service.get_user(user.id) is None


def test_procedure_ownership_enforced(
    client: TestClient,
    memory_service: MemoryService,
) -> None:
    owner = memory_service.get_or_create_user(external_user_key="owner")
    other = memory_service.get_or_create_user(external_user_key="other")
    procedure = memory_service.save_procedure_plan(
        user_id=owner.id,
        intent="immigration",
        plan=_example_plan(),
    )

    response = client.get(
        f"/v1/procedures/{procedure.id}",
        params={"user_id": other.id},
    )

    assert response.status_code == 403


def test_dependency_failure_is_returned_as_structured_error(
    memory_service: MemoryService,
) -> None:
    class FailingOrchestrator:
        def handle_query(self, request: ProcedureQueryRequest) -> ProcedureQueryResponse:
            raise RuntimeError("secret stack detail")

    app = create_app()
    app.dependency_overrides[dependencies.get_memory_service] = lambda: memory_service
    app.dependency_overrides[dependencies.get_orchestrator] = lambda: FailingOrchestrator()
    response = TestClient(app, raise_server_exceptions=False).post(
        "/v1/procedures/query",
        json={"question": "Can I move to Switzerland?"},
    )

    assert response.status_code == 500
    payload = response.json()
    assert payload["error"]["code"] == "internal_error"
    assert "secret" not in payload["error"]["message"]
