"""Retrieval metrics for vector, BM25, hybrid, and reranked candidates."""

from __future__ import annotations

from evaluation.metrics.base import (
    Metric,
    MetricResult,
    average_precision,
    ndcg,
    non_applicable,
    reciprocal_rank,
    region,
    result_identifier,
    source_id,
)
from evaluation.models import EvaluationCase, EvaluationCaseResult


class RetrievalMetric(Metric):
    result_field = "hybrid_results"
    prefix = "hybrid"
    k = 5

    def _results(self, result: EvaluationCaseResult) -> list:
        return list(getattr(result, self.result_field))

    def _relevant_ids(self, case: EvaluationCase) -> set[str]:
        return set(case.expected_source_ids) | set(case.expected_document_ids) | set(case.expected_chunk_ids)

    def _relevance(self, case: EvaluationCase, result: EvaluationCaseResult) -> list[bool]:
        relevant = self._relevant_ids(case)
        judgments = case.relevance_judgments
        values: list[bool] = []
        for item in self._results(result):
            identifiers = {result_identifier(item), source_id(item)}
            identifiers = {value for value in identifiers if value}
            values.append(bool(identifiers.intersection(relevant)) or any(judgments.get(identifier, 0) > 0 for identifier in identifiers))
        return values

    def _grades(self, case: EvaluationCase, result: EvaluationCaseResult) -> list[int]:
        relevant = self._relevant_ids(case)
        grades: list[int] = []
        for item in self._results(result):
            identifiers = {result_identifier(item), source_id(item)}
            identifiers = {value for value in identifiers if value}
            grade = max([case.relevance_judgments.get(identifier, 0) for identifier in identifiers] or [0])
            if grade == 0 and identifiers.intersection(relevant):
                grade = 1
            grades.append(grade)
        return grades


class RecallAtK(RetrievalMetric):
    metric_name = "recall_at_k"
    category = "retrieval"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        relevant = self._relevant_ids(case)
        if not relevant and not case.relevance_judgments:
            return non_applicable(self.metric_name, reason="No relevance expectations")
        total_relevant = max(1, len(relevant) or len([v for v in case.relevance_judgments.values() if v > 0]))
        retrieved_relevant: set[str] = set()
        for item in self._results(result)[: self.k]:
            identifiers = {result_identifier(item), source_id(item)}
            identifiers = {value for value in identifiers if value}
            retrieved_relevant.update(identifiers.intersection(relevant))
            retrieved_relevant.update(
                identifier
                for identifier in identifiers
                if case.relevance_judgments.get(identifier, 0) > 0
            )
        return MetricResult(metric_name=f"{self.prefix}_{self.metric_name}_{self.k}", value=min(1.0, len(retrieved_relevant) / total_relevant), details={"k": self.k, "retrieved_relevant": sorted(retrieved_relevant)})


class PrecisionAtK(RetrievalMetric):
    metric_name = "precision_at_k"
    category = "retrieval"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        results = self._results(result)[: self.k]
        if not results:
            return non_applicable(f"{self.prefix}_{self.metric_name}_{self.k}", reason="No results")
        relevance = self._relevance(case, result)[: self.k]
        return MetricResult(metric_name=f"{self.prefix}_{self.metric_name}_{self.k}", value=sum(relevance) / len(results), details={"k": self.k})


class MeanReciprocalRank(RetrievalMetric):
    metric_name = "mrr"
    category = "retrieval"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        relevance = self._relevance(case, result)
        if not relevance:
            return non_applicable(f"{self.prefix}_{self.metric_name}", reason="No results")
        return MetricResult(metric_name=f"{self.prefix}_{self.metric_name}", value=reciprocal_rank(relevance))


class MeanAveragePrecision(RetrievalMetric):
    metric_name = "map"
    category = "retrieval"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        relevance = self._relevance(case, result)
        if not relevance:
            return non_applicable(f"{self.prefix}_{self.metric_name}", reason="No results")
        return MetricResult(metric_name=f"{self.prefix}_{self.metric_name}", value=average_precision(relevance))


class NDCGAtK(RetrievalMetric):
    metric_name = "ndcg_at_k"
    category = "retrieval"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        grades = self._grades(case, result)
        if not grades or not case.relevance_judgments:
            return non_applicable(f"{self.prefix}_{self.metric_name}_{self.k}", reason="No graded relevance")
        return MetricResult(metric_name=f"{self.prefix}_{self.metric_name}_{self.k}", value=ndcg(grades, k=self.k), details={"grades": grades[: self.k]})


class SourceCoverage(RetrievalMetric):
    metric_name = "source_coverage"
    category = "retrieval"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        expected = set(case.expected_source_ids)
        if not expected:
            return non_applicable(f"{self.prefix}_{self.metric_name}", reason="No expected source ids")
        retrieved = {source_id(item) for item in self._results(result)}
        retrieved.discard(None)
        return MetricResult(metric_name=f"{self.prefix}_{self.metric_name}", value=len(expected.intersection(retrieved)) / len(expected), details={"expected": sorted(expected), "retrieved": sorted(retrieved)})


class RegionAccuracy(RetrievalMetric):
    metric_name = "region_accuracy"
    category = "retrieval"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        expected = set(case.expected_regions)
        if not expected:
            return non_applicable(f"{self.prefix}_{self.metric_name}", reason="No expected regions")
        retrieved = {region(item) for item in self._results(result)}
        retrieved.discard(None)
        return MetricResult(metric_name=f"{self.prefix}_{self.metric_name}", value=1.0 if expected.issubset(retrieved) else 0.0, details={"expected": sorted(expected), "retrieved": sorted(retrieved)})


class DuplicateResultRate(RetrievalMetric):
    metric_name = "duplicate_result_rate"
    category = "retrieval"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        results = self._results(result)
        if not results:
            return non_applicable(f"{self.prefix}_{self.metric_name}", reason="No results")
        identifiers = [result_identifier(item) for item in results]
        duplicate_count = len(identifiers) - len(set(identifiers))
        return MetricResult(metric_name=f"{self.prefix}_{self.metric_name}", value=duplicate_count / len(identifiers), details={"duplicates": duplicate_count})


def retrieval_metric_suite(*, result_field: str, prefix: str, k: int = 5) -> list[Metric]:
    """Create the standard retrieval metrics for a result field."""

    metrics: list[Metric] = []
    for cls in [
        RecallAtK,
        PrecisionAtK,
        MeanReciprocalRank,
        MeanAveragePrecision,
        NDCGAtK,
        SourceCoverage,
        RegionAccuracy,
        DuplicateResultRate,
    ]:
        metric = cls()
        metric.result_field = result_field
        metric.prefix = prefix
        metric.k = k
        metrics.append(metric)
    return metrics
