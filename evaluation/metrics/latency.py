"""Operational performance metrics."""

from __future__ import annotations

from evaluation.metrics.base import Metric, MetricResult, get_field, non_applicable
from evaluation.models import EvaluationCase, EvaluationCaseResult, EvaluationStatus


class TimingMetric(Metric):
    category = "latency"

    def __init__(self, metric_name: str, timing_key: str) -> None:
        self.metric_name = metric_name
        self.timing_key = timing_key

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        value = result.timings.get(self.timing_key)
        if value is None:
            return non_applicable(self.metric_name, reason=f"Missing timing key: {self.timing_key}")
        return MetricResult(metric_name=self.metric_name, value=float(value), details={"unit": "seconds"})


class TotalLatency(Metric):
    metric_name = "total_latency"
    category = "latency"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        if not result.timings:
            return non_applicable(self.metric_name, reason="No timing data")
        return MetricResult(metric_name=self.metric_name, value=sum(float(value) for value in result.timings.values()), details={"unit": "seconds"})


class MetadataCountMetric(Metric):
    category = "latency"

    def __init__(self, metric_name: str, metadata_key: str) -> None:
        self.metric_name = metric_name
        self.metadata_key = metadata_key

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        value = get_field(result.model_metadata, self.metadata_key)
        if value is None:
            return non_applicable(self.metric_name, reason=f"Missing model metadata key: {self.metadata_key}")
        return MetricResult(metric_name=self.metric_name, value=float(value))


class ErrorRate(Metric):
    metric_name = "error_rate"
    category = "latency"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        return MetricResult(metric_name=self.metric_name, value=1.0 if result.error else 0.0)


class CompletionRate(Metric):
    metric_name = "completion_rate"
    category = "latency"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        return MetricResult(metric_name=self.metric_name, value=0.0 if result.execution_status is EvaluationStatus.FAILED else 1.0)


LATENCY_METRICS: list[Metric] = [
    TotalLatency(),
    TimingMetric("clarification_latency", "clarification"),
    TimingMetric("retrieval_latency", "retrieval"),
    TimingMetric("reranking_latency", "reranking"),
    TimingMetric("generation_latency", "generation"),
    TimingMetric("planner_latency", "planner"),
    MetadataCountMetric("embedding_call_count", "embedding_calls"),
    MetadataCountMetric("generation_call_count", "generation_calls"),
    MetadataCountMetric("judge_model_call_count", "judge_model_calls"),
    MetadataCountMetric("estimated_token_usage", "estimated_token_usage"),
    ErrorRate(),
    CompletionRate(),
]
