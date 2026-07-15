from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from backend.models.chunk import ChunkMetadata
from backend.models.clarification import ClarificationQuestion, DetectedIntent
from backend.models.generation import CitedSource, GeneratedAnswer
from backend.models.planner import ProcedurePlan, ProcedureStep, WorkflowStatus
from backend.models.reranking import RerankedChunk, RerankResult
from backend.models.retrieval import HybridRetrievalResult, RetrievedChunk
from backend.orchestration.models import ProcedureQueryResponse, ProcedureResponseState
from evaluation.adapters.clarification_adapter import ClarificationEvaluationAdapter
from evaluation.adapters.end_to_end_adapter import EndToEndEvaluationAdapter
from evaluation.adapters.generation_adapter import GenerationEvaluationAdapter
from evaluation.adapters.planner_adapter import PlannerEvaluationAdapter
from evaluation.adapters.reranking_adapter import RerankingEvaluationAdapter
from evaluation.adapters.retrieval_adapter import RetrievalEvaluationAdapter
from evaluation.config import EvaluationConfig, ExecutionMode
from evaluation.models import EvaluationCase, EvaluationCaseResult, EvaluationStatus
from evaluation.runner import EvaluationRunner


def _case(**updates: Any) -> EvaluationCase:
    data: dict[str, Any] = {
        "id": "case-1",
        "question": "Can I move to Switzerland as a Brazilian citizen?",
        "language": "en",
        "tags": ["immigration"],
        "user_profile": {"nationality": "Brazil"},
        "expected_intent": "immigration",
    }
    data.update(updates)
    return EvaluationCase.model_validate(data)


def _chunk() -> RetrievedChunk:
    return RetrievedChunk(
        id="chunk-1",
        text="Brazilian citizens need to check permit requirements.",
        metadata=ChunkMetadata(source="permit.pdf", region="federal", page=1),
        score=0.8,
        retrieval_source="vector",
    )


def _answer() -> GeneratedAnswer:
    return GeneratedAnswer(
        answer="Use the cited official source.",
        explanation="The answer is grounded in the retrieved source.",
        procedure_steps=["Check requirements"],
        important_notes=["Informational only."],
        cited_sources=[CitedSource(source="permit.pdf", page=1, region="federal")],
        confidence="Medium",
        insufficient_context=False,
    )


def _plan() -> ProcedurePlan:
    source = CitedSource(source="permit.pdf", page=1, region="federal")
    return ProcedurePlan(
        title="Immigration procedure",
        summary="Procedure summary.",
        status=WorkflowStatus.READY_TO_START,
        steps=[
            ProcedureStep(
                step_number=1,
                title="Check requirements",
                description="Check official requirements.",
                responsible_party="User",
                required_documents=[],
                estimated_time="Not specified in retrieved sources.",
                source_reference=source,
            )
        ],
        required_documents=[],
        estimated_timelines=["Not specified in retrieved sources."],
        potential_blockers=[],
        next_recommended_action="Check official requirements.",
        source_references=[source],
        missing_information=[],
    )


def test_evaluation_config_validation(tmp_path: Path) -> None:
    config = EvaluationConfig(output_directory=tmp_path)

    assert config.execution_mode is ExecutionMode.OFFLINE
    live = EvaluationConfig(output_directory=tmp_path, execution_mode="live")
    assert live.execution_mode is ExecutionMode.LIVE
    with pytest.raises(ValueError, match="judge_model_enabled"):
        EvaluationConfig(output_directory=tmp_path, judge_model_enabled=True)


def test_evaluation_case_validation_and_result_serialization() -> None:
    case = _case(expected_clarification_fields=["intended_canton"])
    result = EvaluationCaseResult(
        case_id=case.id,
        question=case.question,
        execution_status=EvaluationStatus.PASSED,
        detected_intent={"intent": "immigration"},
    )

    assert case.id == "case-1"
    assert "immigration" in result.model_dump_json()


class FakeIntentClassifier:
    def classify(self, question: str) -> DetectedIntent:
        return DetectedIntent(intent="immigration", confidence=0.9, matched_keywords=["move"])


class FakeClarificationEngine:
    def evaluate(self, *, user_question, detected_intent, user_profile):
        from backend.models.clarification import ClarificationResult

        return ClarificationResult(
            intent=detected_intent,
            needs_clarification=True,
            missing_fields=["intended_canton"],
            clarification_questions=[
                ClarificationQuestion(field="intended_canton", question="Which canton?")
            ],
            known_fields={"nationality": "Brazil"},
        )


def test_clarification_adapter_dependency_injection() -> None:
    adapter = ClarificationEvaluationAdapter(
        intent_classifier=FakeIntentClassifier(),
        clarification_engine=FakeClarificationEngine(),
    )

    result = adapter.evaluate(_case())

    assert result.detected_intent["intent"] == "immigration"
    assert result.clarification_result["missing_fields"] == ["intended_canton"]
    assert "clarification" in result.timings


class FakeVectorRetriever:
    def retrieve(self, query: str, *, top_k: int = 10):
        return [_chunk()]


class FakeBM25Retriever:
    def retrieve(self, query: str, *, top_k: int = 10):
        return [_chunk().model_copy(update={"retrieval_source": "bm25", "score": 2.0})]


class FakeHybridRetriever:
    def retrieve(self, query: str, *, top_k: int = 10):
        chunk = _chunk()
        return HybridRetrievalResult(
            query=query,
            vector_results=[chunk],
            bm25_results=[],
            merged_results=[chunk],
        )


def test_retrieval_adapter() -> None:
    adapter = RetrievalEvaluationAdapter(
        vector_retriever=FakeVectorRetriever(),
        bm25_retriever=FakeBM25Retriever(),
        hybrid_retriever=FakeHybridRetriever(),
    )

    result = adapter.evaluate(_case())

    assert result.vector_results[0]["id"] == "chunk-1"
    assert result.bm25_results[0]["retrieval_source"] == "bm25"
    assert result.hybrid_results[0]["id"] == "chunk-1"


class FakeReranker:
    def rerank(self, *, query: str, retrieved_chunks: list[RetrievedChunk], top_k: int = 5):
        chunk = retrieved_chunks[0]
        reranked = RerankedChunk(
            chunk_id=chunk.id,
            text=chunk.text,
            metadata=chunk.metadata,
            retrieval_source=chunk.retrieval_source,
            retrieval_score=chunk.score,
            rerank_score=4.0,
        )
        return RerankResult(
            query=query,
            total_candidates=1,
            selected_candidates=1,
            chunks=[reranked],
        )


def test_reranking_adapter() -> None:
    adapter = RerankingEvaluationAdapter(reranker=FakeReranker())

    result = adapter.evaluate(_case(), hybrid_candidates=[_chunk()])

    assert result.reranked_results[0]["chunk_id"] == "chunk-1"
    assert result.reranked_results[0]["rerank_score"] == 4.0


class ExplodingAnswerGenerator:
    def generate(self, **kwargs):
        raise AssertionError("external call should not happen in offline mode")


def test_generation_adapter_with_mocked_offline_output() -> None:
    case = _case(offline_outputs={"generated_answer": _answer().model_dump(mode="json")})
    adapter = GenerationEvaluationAdapter(
        answer_generator=ExplodingAnswerGenerator(),
        execution_mode=ExecutionMode.OFFLINE,
    )

    result = adapter.evaluate(case)

    assert result.generated_answer["answer"] == "Use the cited official source."


class ExplodingPlanner:
    def create_plan(self, **kwargs):
        raise AssertionError("planner should not be called in offline mode")


def test_planner_adapter_with_mocked_offline_output() -> None:
    case = _case(offline_outputs={"procedure_plan": _plan().model_dump(mode="json")})
    adapter = PlannerEvaluationAdapter(
        workflow_planner=ExplodingPlanner(),
        execution_mode=ExecutionMode.OFFLINE,
    )

    result = adapter.evaluate(case, generated_answer=_answer())

    assert result.procedure_plan["title"] == "Immigration procedure"


class FakeOrchestrator:
    def __init__(self) -> None:
        self.request_user_id: str | None = None

    def handle_query(self, request):
        self.request_user_id = request.user_id
        return ProcedureQueryResponse(
            user_id="isolated-user",
            procedure_id=None,
            intent="immigration",
            state=ProcedureResponseState.CLARIFICATION_REQUIRED,
            needs_clarification=True,
            clarification_questions=[
                ClarificationQuestion(field="intended_canton", question="Which canton?")
            ],
            missing_fields=["intended_canton"],
            answer=None,
            plan=None,
            sources=[],
            confidence=None,
            insufficient_context=False,
            saved_profile_fields=["nationality"],
            workflow_status=None,
        )


def test_end_to_end_adapter_with_isolated_persistence() -> None:
    orchestrator = FakeOrchestrator()
    adapter = EndToEndEvaluationAdapter(orchestrator=orchestrator)

    result = adapter.evaluate(_case())

    assert result.detected_intent == "immigration"
    assert result.clarification_result["needs_clarification"] is True
    assert orchestrator.request_user_id is None


class FailingClarificationAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, case: EvaluationCase):
        self.calls += 1
        if case.id == "bad":
            raise RuntimeError("case-specific failure")
        return EvaluationCaseResult(
            case_id=case.id,
            question=case.question,
            execution_status=EvaluationStatus.PASSED,
            clarification_result={"needs_clarification": True},
        )


def test_runner_case_failure_isolation_and_artifact_creation(tmp_path: Path) -> None:
    cases = [_case(id="bad"), _case(id="good")]
    runner = EvaluationRunner(
        config=EvaluationConfig(output_directory=tmp_path, run_name="unit"),
        cases=cases,
        clarification_adapter=FailingClarificationAdapter(),
    )

    result = runner.run()
    run_dir = tmp_path / result.metadata.run_id

    assert len(result.case_results) == 2
    assert result.case_results[0].execution_status is EvaluationStatus.FAILED
    assert result.case_results[1].execution_status is EvaluationStatus.PASSED
    assert (run_dir / "run_metadata.json").exists()
    assert (run_dir / "config.json").exists()
    assert (run_dir / "case_results.jsonl").exists()
    assert (run_dir / "intermediate_outputs").exists()


def test_runner_metadata_and_case_filtering(tmp_path: Path) -> None:
    cases = [
        _case(id="one", tags=["a"]),
        _case(id="two", tags=["b"]),
        _case(id="three", tags=["a", "b"]),
    ]
    config = EvaluationConfig(
        output_directory=tmp_path,
        dataset_name="mini",
        dataset_version="1",
        case_ids=["one", "three"],
        tags=["b"],
        max_cases=1,
    )
    runner = EvaluationRunner(
        config=config,
        cases=cases,
        clarification_adapter=FailingClarificationAdapter(),
    )

    result = runner.run()

    assert result.metadata.dataset_name == "mini"
    assert result.metadata.dataset_version == "1"
    assert [case.case_id for case in result.case_results] == ["three"]


def test_production_sqlite_and_chromadb_paths_remain_unchanged(tmp_path: Path) -> None:
    config = EvaluationConfig(output_directory=tmp_path)
    runner = EvaluationRunner(config=config, cases=[])

    result = runner.run()

    assert result.case_results == []
    assert config.output_directory == tmp_path
    assert not (tmp_path / "data" / "sqlite" / "memory.db").exists()
