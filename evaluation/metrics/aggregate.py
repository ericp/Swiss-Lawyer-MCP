"""Metric execution and aggregation."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Iterable

from evaluation.config import EvaluationConfig
from evaluation.metrics.abstention import ABSTENTION_METRICS
from evaluation.metrics.base import Metric, MetricResult, metric_error
from evaluation.metrics.citations import CITATION_METRICS
from evaluation.metrics.clarification import CLARIFICATION_METRICS
from evaluation.metrics.generation import GENERATION_METRICS
from evaluation.metrics.latency import LATENCY_METRICS
from evaluation.metrics.optional_ragas import OPTIONAL_RAGAS_METRICS
from evaluation.metrics.planning import PLANNING_METRICS
from evaluation.metrics.reranking import reranking_metric_suite
from evaluation.metrics.retrieval import retrieval_metric_suite
from evaluation.models import EvaluationCase, EvaluationCaseResult


def default_metrics(*, retrieval_k: int = 5, rerank_k: int = 5, include_optional_ragas: bool = False) -> list[Metric]:
    """Return the standard Phase 10 Part 3 metric suite."""

    metrics: list[Metric] = []
    metrics.extend(CLARIFICATION_METRICS)
    metrics.extend(retrieval_metric_suite(result_field="vector_results", prefix="vector", k=retrieval_k))
    metrics.extend(retrieval_metric_suite(result_field="bm25_results", prefix="bm25", k=retrieval_k))
    metrics.extend(retrieval_metric_suite(result_field="hybrid_results", prefix="hybrid", k=retrieval_k))
    metrics.extend(retrieval_metric_suite(result_field="reranked_results", prefix="reranked", k=rerank_k))
    metrics.extend(reranking_metric_suite(k=rerank_k))
    metrics.extend(GENERATION_METRICS)
    metrics.extend(CITATION_METRICS)
    metrics.extend(ABSTENTION_METRICS)
    metrics.extend(PLANNING_METRICS)
    metrics.extend(LATENCY_METRICS)
    if include_optional_ragas:
        metrics.extend(OPTIONAL_RAGAS_METRICS)
    return metrics


def compute_case_metrics(
    case: EvaluationCase,
    result: EvaluationCaseResult,
    metrics: Iterable[Metric],
) -> list[MetricResult]:
    """Compute all metrics for one case while isolating metric failures."""

    outputs: list[MetricResult] = []
    for metric in metrics:
        try:
            metric_result = metric.compute(case, result)
        except Exception as error:
            metric_result = metric_error(metric.metric_name, error)
        metric_result.category = getattr(metric, "category", None)
        outputs.append(metric_result)
    return outputs


def compute_run_metrics(
    cases: list[EvaluationCase],
    results: list[EvaluationCaseResult],
    *,
    config: EvaluationConfig | None = None,
    metrics: Iterable[Metric] | None = None,
) -> dict[str, Any]:
    """Compute case-level and aggregate metrics for a complete run."""

    case_by_id = {case.id: case for case in cases}
    metric_suite = list(metrics or default_metrics(
        retrieval_k=config.retrieval_top_k if config else 5,
        rerank_k=config.rerank_top_k if config else 5,
        include_optional_ragas=False,
    ))
    case_level: dict[str, list[MetricResult]] = {}
    warnings: list[str] = []
    for result in results:
        case = case_by_id.get(result.case_id)
        if case is None:
            continue
        metric_results = compute_case_metrics(case, result, metric_suite)
        case_level[result.case_id] = metric_results
        for metric_result in metric_results:
            warnings.extend(f"{result.case_id}:{metric_result.metric_name}: {warning}" for warning in metric_result.warnings)

    aggregate = aggregate_metric_results(case_level, cases=cases, results=results, config=config)
    return {
        "case_level_metrics": case_level,
        "aggregate_metrics": aggregate,
        "metric_applicability_counts": _applicability_counts(case_level),
        "metric_warnings": warnings,
        "judge_metadata": {
            "judge_model_enabled": bool(config.judge_model_enabled) if config else False,
            "judge_model": config.judge_model if config else None,
        },
        "timing_summary": _timing_summary(results),
    }


def aggregate_metric_results(
    case_metrics: dict[str, list[MetricResult]],
    *,
    cases: list[EvaluationCase] | None = None,
    results: list[EvaluationCaseResult] | None = None,
    config: EvaluationConfig | None = None,
) -> dict[str, Any]:
    """Aggregate applicable metric values without averaging non-applicable cases."""

    case_by_id = {case.id: case for case in cases or []}
    result_by_id = {result.case_id: result for result in results or []}
    aggregates: dict[str, Any] = {
        "by_metric": _aggregate_group(case_metrics, lambda metric, _case, _result: metric.metric_name),
        "by_category": _aggregate_group(case_metrics, lambda metric, _case, _result: metric.category or "unknown"),
        "by_intent": _aggregate_group(case_metrics, lambda _metric, case, _result: case.expected_intent if case and case.expected_intent else "unknown", case_by_id=case_by_id),
        "by_language": _aggregate_group(case_metrics, lambda _metric, case, _result: case.language if case and case.language else "unknown", case_by_id=case_by_id),
        "by_region": _aggregate_group(case_metrics, lambda _metric, case, _result: ",".join(case.expected_regions) if case and case.expected_regions else "unknown", case_by_id=case_by_id),
        "by_nationality_category": _aggregate_group(case_metrics, lambda _metric, case, _result: _nationality_category(case), case_by_id=case_by_id),
        "by_execution_mode": _aggregate_group(case_metrics, lambda _metric, _case, _result: str(config.execution_mode.value if config else "unknown")),
        "by_tag": _aggregate_by_tag(case_metrics, case_by_id),
    }
    if result_by_id:
        aggregates["case_count"] = len(result_by_id)
    return aggregates


def _aggregate_group(
    case_metrics: dict[str, list[MetricResult]],
    key_fn,
    *,
    case_by_id: dict[str, EvaluationCase] | None = None,
) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    applicable_counts: dict[str, int] = defaultdict(int)
    total_counts: dict[str, int] = defaultdict(int)
    for case_id, metrics in case_metrics.items():
        case = (case_by_id or {}).get(case_id)
        for metric in metrics:
            key = str(key_fn(metric, case, None))
            total_counts[key] += 1
            if metric.applicable and metric.value is not None:
                applicable_counts[key] += 1
                buckets[key].append(float(metric.value))
    return {
        key: {
            "mean": mean(values) if values else None,
            "sample_count": len(values),
            "applicable_count": applicable_counts[key],
            "total_count": total_counts[key],
        }
        for key, values in sorted(
            (key, buckets.get(key, []))
            for key in set(total_counts) | set(buckets)
        )
    }


def _aggregate_by_tag(case_metrics: dict[str, list[MetricResult]], case_by_id: dict[str, EvaluationCase]) -> dict[str, dict[str, Any]]:
    values: dict[str, list[float]] = defaultdict(list)
    total_counts: dict[str, int] = defaultdict(int)
    applicable_counts: dict[str, int] = defaultdict(int)
    for case_id, metrics in case_metrics.items():
        case = case_by_id.get(case_id)
        tags = case.tags if case and case.tags else ["untagged"]
        for tag in tags:
            for metric in metrics:
                total_counts[tag] += 1
                if metric.applicable and metric.value is not None:
                    applicable_counts[tag] += 1
                    values[tag].append(float(metric.value))
    return {
        tag: {
            "mean": mean(metric_values) if metric_values else None,
            "sample_count": len(metric_values),
            "applicable_count": applicable_counts[tag],
            "total_count": total_counts[tag],
        }
        for tag, metric_values in sorted(
            (tag, values.get(tag, []))
            for tag in set(total_counts) | set(values)
        )
    }


def _applicability_counts(case_metrics: dict[str, list[MetricResult]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"applicable": 0, "not_applicable": 0, "errors": 0})
    for metrics in case_metrics.values():
        for metric in metrics:
            bucket = counts[metric.metric_name]
            if metric.error:
                bucket["errors"] += 1
            elif metric.applicable:
                bucket["applicable"] += 1
            else:
                bucket["not_applicable"] += 1
    return dict(counts)


def _timing_summary(results: list[EvaluationCaseResult]) -> dict[str, Any]:
    timings: dict[str, list[float]] = defaultdict(list)
    for result in results:
        for key, value in result.timings.items():
            timings[key].append(float(value))
    return {
        key: {"mean": mean(values), "max": max(values), "sample_count": len(values)}
        for key, values in sorted(timings.items())
    }


def _nationality_category(case: EvaluationCase | None) -> str:
    if case is None:
        return "unknown"
    nationality = str(case.user_profile.get("nationality", "")).lower()
    if nationality in {"spain", "portugal", "france", "germany", "italy", "austria"}:
        return "eu_efta"
    if nationality in {"united kingdom", "uk"}:
        return "uk"
    if nationality:
        return "non_eu_efta_or_other"
    return "unknown"
