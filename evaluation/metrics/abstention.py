"""Insufficient-context and abstention metrics."""

from __future__ import annotations

from evaluation.metrics.base import Metric, MetricResult, non_applicable
from evaluation.metrics.generation import _is_insufficient
from evaluation.models import EvaluationCase, EvaluationCaseResult


class AbstentionPrecision(Metric):
    metric_name = "abstention_precision"
    category = "abstention"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        abstained = _is_insufficient(result)
        if not abstained:
            return non_applicable(self.metric_name, reason="System did not abstain")
        return MetricResult(metric_name=self.metric_name, value=1.0 if case.should_abstain else 0.0)


class AbstentionRecall(Metric):
    metric_name = "abstention_recall"
    category = "abstention"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        if not case.should_abstain:
            return non_applicable(self.metric_name, reason="Case should not abstain")
        return MetricResult(metric_name=self.metric_name, value=1.0 if _is_insufficient(result) else 0.0)


class UnsafeAnswerRate(Metric):
    metric_name = "unsafe_answer_rate"
    category = "abstention"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        if not case.should_abstain:
            return non_applicable(self.metric_name, reason="Case has sufficient context")
        return MetricResult(metric_name=self.metric_name, value=0.0 if _is_insufficient(result) else 1.0)


class UnnecessaryAbstentionRate(Metric):
    metric_name = "unnecessary_abstention_rate"
    category = "abstention"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        if case.should_abstain:
            return non_applicable(self.metric_name, reason="Case should abstain")
        return MetricResult(metric_name=self.metric_name, value=1.0 if _is_insufficient(result) else 0.0)


ABSTENTION_METRICS: list[Metric] = [
    AbstentionPrecision(),
    AbstentionRecall(),
    UnsafeAnswerRate(),
    UnnecessaryAbstentionRate(),
]
