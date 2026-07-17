"""Procedure-plan quality metrics."""

from __future__ import annotations

from evaluation.metrics.base import Metric, MetricResult, contains_text, flatten_text, get_field, non_applicable
from evaluation.models import EvaluationCase, EvaluationCaseResult


def _plan_text(result: EvaluationCaseResult) -> str:
    return flatten_text(result.procedure_plan)


def _steps(result: EvaluationCaseResult) -> list[object]:
    return list(get_field(result.procedure_plan, "steps", []) or [])


def _documents(result: EvaluationCaseResult) -> list[object]:
    return list(get_field(result.procedure_plan, "required_documents", []) or [])


class ExpectedStepCoverage(Metric):
    metric_name = "expected_step_coverage"
    category = "planning"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        expected = case.expected_procedure_steps
        if not expected:
            return non_applicable(self.metric_name, reason="No expected procedure steps")
        text = _plan_text(result)
        matched = [step for step in expected if contains_text(text, step)]
        return MetricResult(metric_name=self.metric_name, value=len(matched) / len(expected), details={"matched": matched})


class InventedStepRate(Metric):
    metric_name = "invented_step_rate"
    category = "planning"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        steps = _steps(result)
        if not steps:
            return non_applicable(self.metric_name, reason="No generated procedure steps")
        forbidden = case.forbidden_procedure_steps
        if not forbidden:
            return MetricResult(metric_name=self.metric_name, value=0.0, details={"reason": "No forbidden steps supplied"})
        text = _plan_text(result)
        found = [step for step in forbidden if contains_text(text, step)]
        return MetricResult(metric_name=self.metric_name, value=len(found) / len(steps), details={"found": found})


class RequiredDocumentCoverage(Metric):
    metric_name = "required_document_coverage"
    category = "planning"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        expected = case.expected_required_document_concepts
        if not expected:
            return non_applicable(self.metric_name, reason="No expected required document concepts")
        text = flatten_text(_documents(result))
        matched = [document for document in expected if contains_text(text, document)]
        return MetricResult(metric_name=self.metric_name, value=len(matched) / len(expected), details={"matched": matched})


class InventedDocumentRate(Metric):
    metric_name = "invented_document_rate"
    category = "planning"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        documents = _documents(result)
        if not documents:
            return non_applicable(self.metric_name, reason="No generated required documents")
        forbidden = case.offline_outputs.get("forbidden_required_documents", [])
        unsupported = [document for document in documents if _is_forbidden_document(document, forbidden)]
        return MetricResult(metric_name=self.metric_name, value=len(unsupported) / len(documents), details={"unsupported": unsupported})


class WorkflowStatusAccuracy(Metric):
    metric_name = "workflow_status_accuracy"
    category = "planning"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        if not case.expected_status:
            return non_applicable(self.metric_name, reason="No expected workflow status")
        status = get_field(result.procedure_plan, "status")
        return MetricResult(metric_name=self.metric_name, value=1.0 if str(status) == case.expected_status else 0.0, details={"expected": case.expected_status, "actual": status})


class UnknownFallbackAccuracy(Metric):
    metric_name = "unknown_fallback_accuracy"
    category = "planning"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        expected = case.expected_missing_information
        if not expected:
            return non_applicable(self.metric_name, reason="No expected missing-information fallback")
        text = _plan_text(result)
        fallback = "not specified in retrieved sources"
        matched = [item for item in expected if contains_text(text, item) or contains_text(text, fallback)]
        return MetricResult(metric_name=self.metric_name, value=len(matched) / len(expected), details={"matched": matched})


def _is_forbidden_document(document: object, forbidden: list[str]) -> bool:
    text = flatten_text(document)
    if "invented" in text.lower():
        return True
    return any(contains_text(text, item) for item in forbidden)


PLANNING_METRICS: list[Metric] = [
    ExpectedStepCoverage(),
    InventedStepRate(),
    RequiredDocumentCoverage(),
    InventedDocumentRate(),
    WorkflowStatusAccuracy(),
    UnknownFallbackAccuracy(),
]
