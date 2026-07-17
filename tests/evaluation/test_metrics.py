"""Hand-calculated metric tests."""

from __future__ import annotations

import builtins

import pytest

from evaluation.metrics.abstention import AbstentionPrecision, AbstentionRecall
from evaluation.metrics.aggregate import aggregate_metric_results, compute_run_metrics
from evaluation.metrics.base import MetricResult, ndcg
from evaluation.metrics.citations import CitationSourceAccuracy, FabricatedCitationRate
from evaluation.metrics.clarification import ForbiddenQuestionRate, MissingFieldPrecision, MissingFieldRecall
from evaluation.metrics.generation import ForbiddenFactRate, RequiredFactCoverage
from evaluation.metrics.optional_ragas import OptionalRagasAvailability
from evaluation.metrics.planning import ExpectedStepCoverage, InventedDocumentRate
from evaluation.metrics.retrieval import MeanAveragePrecision, MeanReciprocalRank, NDCGAtK, PrecisionAtK, RecallAtK
from evaluation.models import EvaluationCase, EvaluationCaseResult, EvaluationStatus


def _case(**updates) -> EvaluationCase:
    payload = {"id": "case-1", "question": "Question?", **updates}
    return EvaluationCase.model_validate(payload)


def _result(**updates) -> EvaluationCaseResult:
    payload = {
        "case_id": "case-1",
        "question": "Question?",
        "execution_status": EvaluationStatus.PASSED,
        **updates,
    }
    return EvaluationCaseResult.model_validate(payload)


def _set_retrieval_metric(metric, *, k: int = 3):
    metric.result_field = "hybrid_results"
    metric.prefix = "hybrid"
    metric.k = k
    return metric


def test_precision_recall_mrr_map_and_ndcg_hand_calculated() -> None:
    case = _case(
        expected_source_ids=["a", "c"],
        relevance_judgments={"a": 3, "c": 2},
    )
    result = _result(
        hybrid_results=[
            {"source_id": "x"},
            {"source_id": "a"},
            {"source_id": "b"},
            {"source_id": "c"},
        ]
    )

    assert _set_retrieval_metric(PrecisionAtK(), k=3).compute(case, result).value == pytest.approx(1 / 3)
    assert _set_retrieval_metric(RecallAtK(), k=3).compute(case, result).value == pytest.approx(1 / 2)
    assert _set_retrieval_metric(MeanReciprocalRank()).compute(case, result).value == pytest.approx(1 / 2)
    assert _set_retrieval_metric(MeanAveragePrecision()).compute(case, result).value == pytest.approx(0.5)
    assert _set_retrieval_metric(NDCGAtK(), k=4).compute(case, result).value == pytest.approx(
        ndcg([0, 3, 0, 2], k=4)
    )


def test_clarification_missing_precision_recall_and_forbidden_rate() -> None:
    case = _case(
        expected_clarification_fields=["a", "b", "c"],
        forbidden_clarification_fields=["z"],
    )
    result = _result(clarification_result={"needs_clarification": True, "missing_fields": ["a", "b", "z"]})

    assert MissingFieldPrecision().compute(case, result).value == pytest.approx(2 / 3)
    assert MissingFieldRecall().compute(case, result).value == pytest.approx(2 / 3)
    assert ForbiddenQuestionRate().compute(case, result).value == pytest.approx(1 / 3)


def test_required_and_forbidden_fact_metrics() -> None:
    case = _case(
        expected_answer_facts=[
            {"description": "A job offer is relevant.", "importance": "critical"},
            {"description": "The canton changes the authority.", "importance": "important"},
        ],
        forbidden_answer_facts=[{"description": "Invented two-day deadline."}],
    )
    result = _result(generated_answer={"answer": "A job offer is relevant. Invented two-day deadline."})

    assert RequiredFactCoverage().compute(case, result).value == pytest.approx(1 / 2)
    assert ForbiddenFactRate().compute(case, result).value == pytest.approx(1.0)


def test_citation_source_accuracy_and_fabricated_rate() -> None:
    case = _case(expected_source_ids=["expected-source"])
    result = _result(
        hybrid_results=[{"source_id": "retrieved-source"}],
        sources=[
            {"source_id": "retrieved-source", "region": "zh", "page": 1},
            {"source_id": "made-up-source", "region": "zh", "page": 2},
        ],
    )

    assert CitationSourceAccuracy().compute(case, result).value == pytest.approx(1 / 2)
    assert FabricatedCitationRate().compute(case, result).value == pytest.approx(1 / 2)


def test_abstention_precision_and_recall() -> None:
    case = _case(should_abstain=True)
    result = _result(generated_answer={"insufficient_context": True})

    assert AbstentionPrecision().compute(case, result).value == pytest.approx(1.0)
    assert AbstentionRecall().compute(case, result).value == pytest.approx(1.0)


def test_planner_step_coverage_and_invented_document_rate() -> None:
    case = _case(
        expected_procedure_steps=["confirm residence date", "prepare documents", "submit application"],
    )
    result = _result(
        procedure_plan={
            "steps": [
                {"description": "Confirm residence date."},
                {"description": "Prepare documents."},
            ],
            "required_documents": ["Passport", "Invented magic certificate"],
        }
    )

    assert ExpectedStepCoverage().compute(case, result).value == pytest.approx(2 / 3)
    assert InventedDocumentRate().compute(case, result).value == pytest.approx(1 / 2)


def test_non_applicable_metric_serializes() -> None:
    result = MissingFieldRecall().compute(_case(), _result())

    assert result.applicable is False
    assert "metric_name" in result.model_dump()


def test_aggregation_ignores_non_applicable_values() -> None:
    case_metrics = {
        "case-1": [
            MetricResult(metric_name="m", value=1.0, applicable=True, category="retrieval"),
            MetricResult(metric_name="m", value=None, applicable=False, category="retrieval"),
        ],
        "case-2": [MetricResult(metric_name="m", value=0.0, applicable=True, category="retrieval")],
    }

    aggregate = aggregate_metric_results(case_metrics)

    assert aggregate["by_metric"]["m"]["mean"] == pytest.approx(0.5)
    assert aggregate["by_metric"]["m"]["sample_count"] == 2


def test_optional_ragas_failure_isolated(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "ragas":
            raise ImportError("not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = OptionalRagasAvailability().compute(_case(), _result())

    assert result.applicable is False
    assert result.warnings


def test_compute_run_metrics_adds_case_and_aggregate_metrics() -> None:
    case = _case(expected_intent="immigration")
    result = _result(detected_intent={"intent": "immigration"})

    payload = compute_run_metrics([case], [result])

    assert "case-1" in payload["case_level_metrics"]
    assert "by_metric" in payload["aggregate_metrics"]
    assert payload["metric_applicability_counts"]["intent_accuracy"]["applicable"] == 1
