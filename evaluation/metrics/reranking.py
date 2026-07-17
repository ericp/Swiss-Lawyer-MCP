"""Reranking metrics."""

from __future__ import annotations

from evaluation.metrics.base import Metric, MetricResult, ndcg, non_applicable, reciprocal_rank, result_identifier, source_id
from evaluation.models import EvaluationCase, EvaluationCaseResult


def _ids(item: object) -> set[str]:
    return {value for value in {result_identifier(item), source_id(item)} if value}


def _relevant_ids(case: EvaluationCase) -> set[str]:
    relevant = set(case.expected_source_ids) | set(case.expected_document_ids) | set(case.expected_chunk_ids)
    relevant.update(key for key, grade in case.relevance_judgments.items() if grade > 0)
    return relevant


def _relevance(case: EvaluationCase, items: list[object]) -> list[bool]:
    relevant = _relevant_ids(case)
    return [bool(_ids(item).intersection(relevant)) for item in items]


def _grades(case: EvaluationCase, items: list[object]) -> list[int]:
    relevant = _relevant_ids(case)
    grades: list[int] = []
    for item in items:
        identifiers = _ids(item)
        grade = max([case.relevance_judgments.get(identifier, 0) for identifier in identifiers] or [0])
        if grade == 0 and identifiers.intersection(relevant):
            grade = 1
        grades.append(grade)
    return grades


class RerankRecallAtK(Metric):
    metric_name = "rerank_recall_at_k"
    category = "reranking"

    def __init__(self, k: int = 5) -> None:
        self.k = k

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        relevant = _relevant_ids(case)
        if not relevant:
            return non_applicable(f"{self.metric_name}_{self.k}", reason="No relevance expectations")
        retrieved_relevant = {
            identifier
            for item in result.reranked_results[: self.k]
            for identifier in _ids(item)
            if identifier in relevant
        }
        return MetricResult(metric_name=f"{self.metric_name}_{self.k}", value=len(retrieved_relevant) / len(relevant), details={"k": self.k, "retrieved_relevant": sorted(retrieved_relevant)})


class RerankMRR(Metric):
    metric_name = "rerank_mrr"
    category = "reranking"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        relevance = _relevance(case, result.reranked_results)
        if not relevance:
            return non_applicable(self.metric_name, reason="No reranked results")
        return MetricResult(metric_name=self.metric_name, value=reciprocal_rank(relevance))


class RerankNDCGAtK(Metric):
    metric_name = "rerank_ndcg_at_k"
    category = "reranking"

    def __init__(self, k: int = 5) -> None:
        self.k = k

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        if not case.relevance_judgments:
            return non_applicable(f"{self.metric_name}_{self.k}", reason="No graded relevance")
        grades = _grades(case, result.reranked_results)
        if not grades:
            return non_applicable(f"{self.metric_name}_{self.k}", reason="No reranked results")
        return MetricResult(metric_name=f"{self.metric_name}_{self.k}", value=ndcg(grades, k=self.k), details={"grades": grades[: self.k]})


class RankImprovement(Metric):
    metric_name = "rank_improvement"
    category = "reranking"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        relevant = _relevant_ids(case)
        if not relevant:
            return non_applicable(self.metric_name, reason="No relevance expectations")
        before_rank = _first_rank(result.hybrid_results, relevant)
        after_rank = _first_rank(result.reranked_results, relevant)
        if before_rank is None or after_rank is None:
            return non_applicable(self.metric_name, reason="Relevant result missing before or after reranking")
        return MetricResult(metric_name=self.metric_name, value=float(before_rank - after_rank), details={"before_rank": before_rank, "after_rank": after_rank})


class RelevantChunkDropRate(Metric):
    metric_name = "relevant_chunk_drop_rate"
    category = "reranking"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        relevant = _relevant_ids(case)
        if not relevant:
            return non_applicable(self.metric_name, reason="No relevance expectations")
        before = {_id for item in result.hybrid_results for _id in _ids(item) if _id in relevant}
        if not before:
            return non_applicable(self.metric_name, reason="No relevant candidates before reranking")
        after = {_id for item in result.reranked_results for _id in _ids(item) if _id in relevant}
        dropped = before - after
        return MetricResult(metric_name=self.metric_name, value=len(dropped) / len(before), details={"dropped": sorted(dropped)})


def _first_rank(items: list[object], relevant: set[str]) -> int | None:
    for index, item in enumerate(items, start=1):
        if _ids(item).intersection(relevant):
            return index
    return None


def reranking_metric_suite(k: int = 5) -> list[Metric]:
    return [
        RerankRecallAtK(k=k),
        RerankMRR(),
        RerankNDCGAtK(k=k),
        RankImprovement(),
        RelevantChunkDropRate(),
    ]
