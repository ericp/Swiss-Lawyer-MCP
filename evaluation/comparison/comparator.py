"""Before/after comparison services."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluation.models import EvaluationCaseResult, EvaluationRunMetadata, EvaluationRunResult
from evaluation.regression.baselines import load_baseline
from evaluation.regression.fingerprint import compare_fingerprints
from evaluation.regression.models import BaselineSummary, MetricDirection, RegressionStatus, RegressionThresholdConfig
from evaluation.comparison.models import CaseDelta, ComparisonInputType, ComparisonReport, MetricDelta


LATENCY_METRICS = {
    "total_latency",
    "clarification_latency",
    "retrieval_latency",
    "reranking_latency",
    "generation_latency",
    "planner_latency",
}

LOWER_IS_BETTER_HINTS = (
    "rate",
    "latency",
    "error",
    "unsupported",
    "fabricated",
    "unsafe",
    "invented",
    "duplicate",
)


class EvaluationComparator:
    """Compare evaluation runs or a baseline against a run."""

    def __init__(
        self,
        *,
        thresholds: RegressionThresholdConfig | None = None,
    ) -> None:
        self.thresholds = thresholds

    def compare_runs(
        self,
        *,
        before: EvaluationRunResult,
        after: EvaluationRunResult,
    ) -> ComparisonReport:
        """Compare two persisted evaluation runs."""

        return self._compare(
            before_type=ComparisonInputType.RUN,
            before_metadata=before.metadata.model_dump(mode="json"),
            before_metrics=before.aggregate_metrics,
            before_case_results=before.case_results,
            before_case_metrics=before.case_level_metrics,
            after=after,
            before_model_configuration=_model_config_from_run(before),
            before_prompt_hashes={},
            before_fingerprint=_fingerprint_from_run(before),
        )

    def compare_baseline(
        self,
        *,
        baseline: BaselineSummary,
        after: EvaluationRunResult,
    ) -> ComparisonReport:
        """Compare a committed baseline summary against a run."""

        return self._compare(
            before_type=ComparisonInputType.BASELINE,
            before_metadata=baseline.model_dump(mode="json", exclude={"aggregate_metrics", "selected_critical_case_results"}),
            before_metrics=baseline.aggregate_metrics,
            before_case_results=[],
            before_case_metrics=baseline.selected_critical_case_results,
            after=after,
            before_model_configuration=baseline.model_configuration,
            before_prompt_hashes=baseline.prompt_hashes,
            before_fingerprint=baseline.knowledge_base_fingerprint,
        )

    def _compare(
        self,
        *,
        before_type: ComparisonInputType,
        before_metadata: dict[str, Any],
        before_metrics: dict[str, Any],
        before_case_results: list[EvaluationCaseResult],
        before_case_metrics: dict[str, Any],
        before_model_configuration: dict[str, Any],
        before_prompt_hashes: dict[str, str],
        before_fingerprint: dict[str, Any] | None,
        after: EvaluationRunResult,
    ) -> ComparisonReport:
        before_by_metric = _metric_table(before_metrics)
        after_by_metric = _metric_table(after.aggregate_metrics)
        metric_names = sorted(set(before_by_metric) | set(after_by_metric))
        deltas = [
            self._metric_delta(metric_name, before_by_metric.get(metric_name), after_by_metric.get(metric_name))
            for metric_name in metric_names
        ]
        case_deltas = _case_deltas(before_case_results, after.case_results, before_case_metrics, after.case_level_metrics)
        knowledge_base_comparison = compare_fingerprints(before_fingerprint, _fingerprint_from_run(after))
        warnings = []
        if not knowledge_base_comparison["comparable"]:
            warnings.append("Knowledge-base fingerprint changed; comparison has limited comparability.")
        critical_failures = [
            delta.model_dump(mode="json")
            for delta in deltas
            if delta.regression_status is RegressionStatus.FAILED and _is_safety_metric(delta.metric_name)
        ]
        recommendations = _recommendations(deltas, knowledge_base_comparison)
        failed_count = sum(delta.regression_status is RegressionStatus.FAILED for delta in deltas) + len(
            [case for case in case_deltas if case.regressed_metrics]
        )
        warning_count = len(warnings)
        overall_status = RegressionStatus.FAILED if failed_count else RegressionStatus.WARNING if warning_count else RegressionStatus.PASSED
        improved = [delta.metric_name for delta in deltas if _is_improvement(delta)]
        regressed = [delta.metric_name for delta in deltas if delta.regression_status is RegressionStatus.FAILED]
        latency_changes = {delta.metric_name: delta for delta in deltas if delta.metric_name in LATENCY_METRICS}

        return ComparisonReport(
            before_type=before_type,
            before_metadata=before_metadata,
            after_metadata=after.metadata.model_dump(mode="json"),
            model_configuration_diff=_dict_diff(before_model_configuration, _model_config_from_run(after)),
            prompt_hash_diff=_dict_diff(before_prompt_hashes, {}),
            knowledge_base_comparison=knowledge_base_comparison,
            metric_deltas=deltas,
            case_deltas=case_deltas,
            critical_failures=critical_failures,
            warnings=warnings,
            recommendations=recommendations,
            improved_metrics=improved,
            regressed_metrics=regressed,
            latency_changes=latency_changes,
            passed_count=sum(delta.regression_status is RegressionStatus.PASSED for delta in deltas),
            warning_count=warning_count,
            failed_count=failed_count,
            overall_status=overall_status,
        )

    def _metric_delta(
        self,
        metric_name: str,
        before_payload: dict[str, Any] | None,
        after_payload: dict[str, Any] | None,
    ) -> MetricDelta:
        before_value = _metric_mean(before_payload)
        after_value = _metric_mean(after_payload)
        direction = _direction_for_metric(metric_name, self.thresholds)
        absolute_change = after_value - before_value if before_value is not None and after_value is not None else None
        relative_change = absolute_change / abs(before_value) if absolute_change is not None and before_value else None
        threshold_status = _threshold_status(metric_name, after_value, self.thresholds)
        regression_status = _regression_status(direction, before_value, after_value, threshold_status)
        category = _category_for_metric(metric_name)
        explanation = _metric_explanation(metric_name, direction, before_value, after_value, regression_status)
        return MetricDelta(
            metric_name=metric_name,
            category=category,
            before_value=before_value,
            after_value=after_value,
            absolute_change=absolute_change,
            relative_change=relative_change,
            direction=direction,
            regression_status=regression_status,
            threshold_status=threshold_status,
            explanation=explanation,
        )


def load_run_result(run_id_or_path: str, *, output_dir: Path = Path("evaluation/artifacts")) -> EvaluationRunResult:
    """Load an EvaluationRunResult from a run id or artifact path."""

    run_path = Path(run_id_or_path)
    if not run_path.exists():
        run_path = output_dir / run_id_or_path
    if not run_path.exists():
        raise FileNotFoundError(f"Evaluation run not found: {run_id_or_path}")
    metadata = EvaluationRunMetadata.model_validate(json.loads((run_path / "run_metadata.json").read_text(encoding="utf-8")))
    case_results = [
        EvaluationCaseResult.model_validate(json.loads(line))
        for line in (run_path / "case_results.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    metrics_path = run_path / "metrics.json"
    metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    case_level_metrics = _load_case_metrics(run_path / "case_metrics.jsonl")
    aggregate_path = run_path / "aggregate_metrics.json"
    aggregate_metrics = json.loads(aggregate_path.read_text(encoding="utf-8")) if aggregate_path.exists() else metrics_payload.get("aggregate_metrics", {})
    for result in case_results:
        result.metrics = case_level_metrics.get(result.case_id, [])
    return EvaluationRunResult(
        metadata=metadata,
        case_results=case_results,
        case_level_metrics=case_level_metrics,
        aggregate_metrics=aggregate_metrics,
        metric_applicability_counts=metrics_payload.get("metric_applicability_counts", {}),
        metric_warnings=metrics_payload.get("metric_warnings", []),
        judge_metadata=metrics_payload.get("judge_metadata", {}),
        timing_summary=metrics_payload.get("timing_summary", {}),
        warnings=json.loads((run_path / "warnings.json").read_text(encoding="utf-8")) if (run_path / "warnings.json").exists() else [],
        errors=json.loads((run_path / "errors.json").read_text(encoding="utf-8")) if (run_path / "errors.json").exists() else [],
    )


def load_baseline_by_name(name: str, *, baseline_dir: Path = Path("evaluation/baselines")) -> BaselineSummary:
    """Load a baseline by name such as smoke_v1 or by explicit path."""

    path = Path(name)
    if not path.exists():
        path = baseline_dir / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Baseline not found: {name}")
    return load_baseline(path)


def _load_case_metrics(path: Path) -> dict[str, list[dict[str, Any]]]:
    if not path.exists():
        return {}
    output: dict[str, list[dict[str, Any]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        output[payload["case_id"]] = payload.get("metrics", [])
    return output


def _metric_table(metrics: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_metric = metrics.get("by_metric", {})
    return by_metric if isinstance(by_metric, dict) else {}


def _metric_mean(payload: dict[str, Any] | None) -> float | None:
    if not payload:
        return None
    value = payload.get("mean", payload.get("value"))
    return float(value) if value is not None else None


def _direction_for_metric(metric_name: str, thresholds: RegressionThresholdConfig | None) -> MetricDirection:
    rule = _rule_for_metric(metric_name, thresholds)
    if rule is not None:
        return rule.direction
    return MetricDirection.LOWER_IS_BETTER if any(hint in metric_name for hint in LOWER_IS_BETTER_HINTS) else MetricDirection.HIGHER_IS_BETTER


def _rule_for_metric(metric_name: str, thresholds: RegressionThresholdConfig | None):
    if thresholds is None:
        return None
    for rule in thresholds.global_thresholds:
        if rule.metric_name == metric_name:
            return rule
    if metric_name in thresholds.metric_thresholds:
        return thresholds.metric_thresholds[metric_name]
    for rules in thresholds.dataset_thresholds.values():
        for rule in rules:
            if rule.metric_name == metric_name:
                return rule
    return None


def _threshold_status(metric_name: str, value: float | None, thresholds: RegressionThresholdConfig | None) -> RegressionStatus | None:
    rule = _rule_for_metric(metric_name, thresholds)
    if rule is None or value is None:
        return None
    if rule.direction is MetricDirection.HIGHER_IS_BETTER and rule.minimum is not None:
        return RegressionStatus.PASSED if value >= rule.minimum else RegressionStatus.FAILED
    if rule.direction is MetricDirection.LOWER_IS_BETTER and rule.maximum is not None:
        return RegressionStatus.PASSED if value <= rule.maximum else RegressionStatus.FAILED
    if rule.direction is MetricDirection.EXACT_MATCH:
        return RegressionStatus.PASSED if value == rule.exact_value else RegressionStatus.FAILED
    return RegressionStatus.PASSED


def _regression_status(
    direction: MetricDirection,
    before_value: float | None,
    after_value: float | None,
    threshold_status: RegressionStatus | None,
) -> RegressionStatus:
    if threshold_status is RegressionStatus.FAILED:
        return RegressionStatus.FAILED
    if before_value is None or after_value is None:
        return RegressionStatus.NOT_APPLICABLE
    if direction is MetricDirection.HIGHER_IS_BETTER:
        return RegressionStatus.FAILED if after_value < before_value else RegressionStatus.PASSED
    if direction is MetricDirection.LOWER_IS_BETTER:
        return RegressionStatus.FAILED if after_value > before_value else RegressionStatus.PASSED
    return RegressionStatus.FAILED if after_value != before_value else RegressionStatus.PASSED


def _metric_explanation(
    metric_name: str,
    direction: MetricDirection,
    before_value: float | None,
    after_value: float | None,
    status: RegressionStatus,
) -> str:
    if before_value is None or after_value is None:
        return f"Metric {metric_name} is missing in one side of the comparison."
    movement = "improved" if _is_improvement_value(direction, before_value, after_value) else "regressed" if status is RegressionStatus.FAILED else "unchanged or acceptable"
    return f"{metric_name} {movement}: before={before_value}, after={after_value}."


def _case_deltas(
    before_results: list[EvaluationCaseResult],
    after_results: list[EvaluationCaseResult],
    before_case_metrics: dict[str, Any],
    after_case_metrics: dict[str, Any],
) -> list[CaseDelta]:
    before_status = {result.case_id: result.execution_status.value for result in before_results}
    after_status = {result.case_id: result.execution_status.value for result in after_results}
    case_ids = sorted(set(before_status) | set(after_status) | set(before_case_metrics) | set(after_case_metrics))
    deltas: list[CaseDelta] = []
    for case_id in case_ids:
        before_metrics = _case_metric_table(before_case_metrics.get(case_id, []))
        after_metrics = _case_metric_table(after_case_metrics.get(case_id, []))
        regressed = []
        for metric_name in sorted(set(before_metrics) & set(after_metrics)):
            direction = _direction_for_metric(metric_name, None)
            if _regression_status(direction, before_metrics[metric_name], after_metrics[metric_name], None) is RegressionStatus.FAILED:
                regressed.append(metric_name)
        deltas.append(CaseDelta(
            case_id=case_id,
            before_status=before_status.get(case_id),
            after_status=after_status.get(case_id),
            status_changed=before_status.get(case_id) != after_status.get(case_id),
            regressed_metrics=regressed,
        ))
    return deltas


def _case_metric_table(metrics: list[Any] | dict[str, Any]) -> dict[str, float]:
    if isinstance(metrics, dict):
        return {key: float(value) for key, value in metrics.items() if isinstance(value, (int, float))}
    table = {}
    for metric in metrics:
        payload = metric.model_dump() if hasattr(metric, "model_dump") else metric
        value = payload.get("value")
        if value is not None:
            table[payload.get("metric_name")] = float(value)
    return table


def _model_config_from_run(run: EvaluationRunResult) -> dict[str, Any]:
    return {
        "embedding_model": run.metadata.embedding_model,
        "generation_model": run.metadata.generation_model,
        "reranker_model": run.metadata.reranker_model,
        "execution_mode": run.metadata.execution_mode.value,
    }


def _fingerprint_from_run(run: EvaluationRunResult) -> dict[str, Any] | None:
    config = run.metadata.evaluation_configuration
    notes = config.notes or ""
    if notes.startswith("knowledge_base_fingerprint="):
        try:
            return json.loads(notes.split("=", 1)[1])
        except json.JSONDecodeError:
            return None
    return None


def _dict_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(before) | set(after))
    return {
        key: {"before": before.get(key), "after": after.get(key)}
        for key in keys
        if before.get(key) != after.get(key)
    }


def _category_for_metric(metric_name: str) -> str:
    if "latency" in metric_name:
        return "latency"
    if any(term in metric_name for term in ["abstention", "unsafe", "unnecessary"]):
        return "abstention"
    if any(term in metric_name for term in ["citation", "fabricated"]):
        return "citations"
    if any(term in metric_name for term in ["claim", "fact", "context"]):
        return "generation"
    if any(term in metric_name for term in ["step", "document", "workflow"]):
        return "planning"
    if any(term in metric_name for term in ["field", "question", "intent"]):
        return "clarification"
    if any(prefix in metric_name for prefix in ["recall", "precision", "mrr", "map", "ndcg", "coverage"]):
        return "retrieval"
    return "general"


def _is_safety_metric(metric_name: str) -> bool:
    return any(term in metric_name for term in ["unsupported", "fabricated", "unsafe", "forbidden", "invented"])


def _is_improvement(delta: MetricDelta) -> bool:
    if delta.before_value is None or delta.after_value is None:
        return False
    return _is_improvement_value(delta.direction, delta.before_value, delta.after_value)


def _is_improvement_value(direction: MetricDirection, before_value: float, after_value: float) -> bool:
    if direction is MetricDirection.HIGHER_IS_BETTER:
        return after_value > before_value
    if direction is MetricDirection.LOWER_IS_BETTER:
        return after_value < before_value
    return after_value == before_value


def _recommendations(deltas: list[MetricDelta], knowledge_base_comparison: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    names = {delta.metric_name: delta for delta in deltas}
    if _failed(names, "hybrid_recall_at_k_10") and not _failed(names, "bm25_recall_at_k_10"):
        recommendations.append("Hybrid Recall@10 decreased while BM25 stayed stable: inspect vector embeddings, metadata filters, or ChromaDB document replacement.")
    if _failed(names, "citation_support_accuracy") or _failed(names, "fabricated_citation_rate"):
        recommendations.append("Citation quality decreased: inspect source serialization, cited source IDs, and the grounded generation prompt.")
    if _failed(names, "unsafe_answer_rate"):
        recommendations.append("Unsafe-answer rate increased: inspect insufficient-context handling and abstention logic.")
    if _failed(names, "reranking_latency"):
        recommendations.append("Reranking latency increased: inspect CrossEncoder loading, batching, and candidate count.")
    if _failed(names, "missing_field_recall"):
        recommendations.append("Clarification recall decreased: inspect deterministic procedure schemas and required-field definitions.")
    if knowledge_base_comparison.get("comparison_context") == "limited_comparability":
        recommendations.append("Knowledge base changed: review source-registry updates and document fingerprints before attributing metric changes to code.")
    return recommendations


def _failed(metrics: dict[str, MetricDelta], metric_name: str) -> bool:
    delta = metrics.get(metric_name)
    return bool(delta and delta.regression_status is RegressionStatus.FAILED)
