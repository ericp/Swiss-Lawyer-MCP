"""Clarification and intent metrics."""

from __future__ import annotations

from evaluation.metrics.base import Metric, MetricResult, get_field, non_applicable
from evaluation.models import EvaluationCase, EvaluationCaseResult


def requested_fields(result: EvaluationCaseResult) -> set[str]:
    clarification = result.clarification_result or {}
    fields = set(get_field(clarification, "missing_fields", []) or [])
    questions = get_field(clarification, "clarification_questions", []) or []
    for question in questions:
        field = get_field(question, "field")
        if field:
            fields.add(str(field))
    return fields


class IntentAccuracy(Metric):
    metric_name = "intent_accuracy"
    category = "clarification"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        if not case.expected_intent:
            return non_applicable(self.metric_name, reason="No expected intent")
        detected = get_field(result.detected_intent, "intent", result.detected_intent)
        return MetricResult(
            metric_name=self.metric_name,
            value=1.0 if detected == case.expected_intent else 0.0,
            details={"expected": case.expected_intent, "detected": detected},
        )


class MissingFieldPrecision(Metric):
    metric_name = "missing_field_precision"
    category = "clarification"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        requested = requested_fields(result)
        if not requested:
            return non_applicable(self.metric_name, reason="No requested fields")
        expected = set(case.expected_clarification_fields)
        value = len(requested.intersection(expected)) / len(requested)
        return MetricResult(metric_name=self.metric_name, value=value, details={"requested": sorted(requested), "expected": sorted(expected)})


class MissingFieldRecall(Metric):
    metric_name = "missing_field_recall"
    category = "clarification"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        expected = set(case.expected_clarification_fields)
        if not expected:
            return non_applicable(self.metric_name, reason="No expected missing fields")
        requested = requested_fields(result)
        value = len(requested.intersection(expected)) / len(expected)
        return MetricResult(metric_name=self.metric_name, value=value, details={"requested": sorted(requested), "expected": sorted(expected)})


class MissingFieldF1(Metric):
    metric_name = "missing_field_f1"
    category = "clarification"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        precision = MissingFieldPrecision().compute(case, result)
        recall = MissingFieldRecall().compute(case, result)
        if not precision.applicable and not recall.applicable:
            return non_applicable(self.metric_name, reason="No expected or requested fields")
        p = precision.value or 0.0
        r = recall.value or 0.0
        value = 0.0 if p + r == 0 else (2 * p * r) / (p + r)
        return MetricResult(metric_name=self.metric_name, value=value, details={"precision": p, "recall": r})


class ForbiddenQuestionRate(Metric):
    metric_name = "forbidden_question_rate"
    category = "clarification"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        forbidden = set(case.forbidden_clarification_fields)
        if not forbidden:
            return non_applicable(self.metric_name, reason="No forbidden clarification fields")
        requested = requested_fields(result)
        value = len(requested.intersection(forbidden)) / max(1, len(requested))
        return MetricResult(metric_name=self.metric_name, value=value, details={"forbidden_requested": sorted(requested.intersection(forbidden))})


class ClarificationCompletionAccuracy(Metric):
    metric_name = "clarification_completion_accuracy"
    category = "clarification"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        if case.expected_clarification_fields:
            return non_applicable(self.metric_name, reason="Case expects clarification")
        clarification = result.clarification_result or {}
        needs_clarification = bool(get_field(clarification, "needs_clarification", False))
        return MetricResult(
            metric_name=self.metric_name,
            value=1.0 if not needs_clarification else 0.0,
            details={"needs_clarification": needs_clarification},
        )


CLARIFICATION_METRICS: list[Metric] = [
    IntentAccuracy(),
    MissingFieldPrecision(),
    MissingFieldRecall(),
    MissingFieldF1(),
    ForbiddenQuestionRate(),
    ClarificationCompletionAccuracy(),
]
