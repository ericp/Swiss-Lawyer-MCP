"""Regression checks for evaluation runs."""

from __future__ import annotations

from typing import Any

from evaluation.models import EvaluationRunResult
from evaluation.regression.fingerprint import compare_fingerprints
from evaluation.regression.models import (
    BaselineSummary,
    CriticalCaseRequirement,
    MetricDirection,
    RegressionCheckResult,
    RegressionReport,
    RegressionSeverity,
    RegressionStatus,
    RegressionThresholdConfig,
    RegressionType,
    ThresholdRule,
)


SAFETY_METRICS = {
    "unsupported_claim_rate",
    "fabricated_citation_rate",
    "unsafe_answer_rate",
    "forbidden_question_rate",
    "invented_step_rate",
    "invented_document_rate",
}

PERFORMANCE_METRICS = {
    "total_latency",
    "error_rate",
    "completion_rate",
    "generation_latency",
    "planner_latency",
    "retrieval_latency",
    "reranking_latency",
}


class RegressionChecker:
    """Compare current evaluation metrics against thresholds and a baseline."""

    def __init__(
        self,
        *,
        thresholds: RegressionThresholdConfig,
        baseline: BaselineSummary,
    ) -> None:
        self.thresholds = thresholds
        self.baseline = baseline

    def check(
        self,
        current_run: EvaluationRunResult,
        *,
        current_knowledge_base_fingerprint: dict[str, Any] | None = None,
    ) -> RegressionReport:
        """Run all configured regression checks."""

        checks: list[RegressionCheckResult] = []
        knowledge_comparison = compare_fingerprints(
            self.baseline.knowledge_base_fingerprint,
            current_knowledge_base_fingerprint,
        )
        if not knowledge_comparison["comparable"]:
            checks.append(
                RegressionCheckResult(
                    metric_name="knowledge_base_fingerprint",
                    current_value=knowledge_comparison.get("current_fingerprint"),
                    baseline_value=knowledge_comparison.get("baseline_fingerprint"),
                    status=RegressionStatus.NOT_COMPARABLE,
                    severity=RegressionSeverity.WARNING,
                    regression_type=RegressionType.DATASET_COMPATIBILITY,
                    explanation="Knowledge-base fingerprint changed; baseline metric comparisons have limited comparability.",
                )
            )

        rules = self._rules_for_dataset(current_run.metadata.dataset_name)
        for rule in rules:
            checks.extend(self._check_rule(rule, current_run))

        for requirement in self.thresholds.critical_cases:
            checks.append(self._check_critical_case(requirement, current_run))

        return _build_report(
            baseline=self.baseline,
            current_run=current_run,
            knowledge_comparison=knowledge_comparison,
            checks=checks,
        )

    def _rules_for_dataset(self, dataset_name: str) -> list[ThresholdRule]:
        rules = list(self.thresholds.global_thresholds)
        rules.extend(self.thresholds.dataset_thresholds.get(dataset_name, []))
        rules.extend(self.thresholds.metric_thresholds.values())
        return rules

    def _check_rule(
        self,
        rule: ThresholdRule,
        current_run: EvaluationRunResult,
    ) -> list[RegressionCheckResult]:
        current_value = _aggregate_metric_value(current_run.aggregate_metrics, rule.metric_name)
        baseline_value = _aggregate_metric_value(self.baseline.aggregate_metrics, rule.metric_name)
        regression_type = _regression_type_for_metric(rule)
        checks = [
            _absolute_threshold_check(rule, current_value, regression_type=regression_type)
        ]
        if baseline_value is None or current_value is None:
            checks.append(
                RegressionCheckResult(
                    metric_name=rule.metric_name,
                    current_value=current_value,
                    baseline_value=baseline_value,
                    threshold=rule.model_dump(mode="json"),
                    direction=rule.direction,
                    status=RegressionStatus.NOT_APPLICABLE,
                    severity=RegressionSeverity.INFO,
                    regression_type=RegressionType.BASELINE,
                    explanation="Baseline comparison skipped because current or baseline metric is unavailable.",
                )
            )
        else:
            checks.append(_baseline_check(rule, current_value, baseline_value))
        return checks

    def _check_critical_case(
        self,
        requirement: CriticalCaseRequirement,
        current_run: EvaluationRunResult,
    ) -> RegressionCheckResult:
        current_value = _case_metric_value(
            current_run.case_level_metrics,
            requirement.case_id,
            requirement.metric_name,
        )
        status = _value_status(
            direction=requirement.direction,
            value=current_value,
            minimum=requirement.minimum,
            maximum=requirement.maximum,
            exact_value=requirement.exact_value,
        )
        return RegressionCheckResult(
            metric_name=f"{requirement.case_id}:{requirement.metric_name}",
            current_value=current_value,
            threshold=requirement.model_dump(mode="json"),
            direction=requirement.direction,
            status=status,
            severity=requirement.severity if status is RegressionStatus.FAILED else RegressionSeverity.INFO,
            regression_type=RegressionType.CRITICAL_CASE,
            explanation=requirement.explanation or f"Critical case {requirement.case_id} must satisfy {requirement.metric_name}.",
        )


def _absolute_threshold_check(
    rule: ThresholdRule,
    current_value: float | None,
    *,
    regression_type: RegressionType,
) -> RegressionCheckResult:
    status = _value_status(
        direction=rule.direction,
        value=current_value,
        minimum=rule.minimum,
        maximum=rule.maximum,
        exact_value=rule.exact_value,
    )
    return RegressionCheckResult(
        metric_name=rule.metric_name,
        current_value=current_value,
        threshold=rule.model_dump(mode="json"),
        direction=rule.direction,
        status=status,
        severity=rule.severity if status is RegressionStatus.FAILED else RegressionSeverity.INFO,
        regression_type=regression_type,
        explanation=_threshold_explanation(rule, current_value, status),
    )


def _baseline_check(
    rule: ThresholdRule,
    current_value: float,
    baseline_value: float,
) -> RegressionCheckResult:
    absolute_change = current_value - baseline_value
    relative_change = absolute_change / abs(baseline_value) if baseline_value else None
    failed = False
    explanation = "Metric is within allowed baseline movement."
    if rule.direction is MetricDirection.HIGHER_IS_BETTER:
        drop = baseline_value - current_value
        relative_drop = drop / abs(baseline_value) if baseline_value else None
        failed = (
            (rule.max_absolute_drop is not None and drop > rule.max_absolute_drop)
            or (rule.max_relative_drop is not None and relative_drop is not None and relative_drop > rule.max_relative_drop)
        )
        if failed:
            explanation = "Metric dropped beyond allowed baseline degradation."
    elif rule.direction is MetricDirection.LOWER_IS_BETTER:
        increase = current_value - baseline_value
        relative_increase = increase / abs(baseline_value) if baseline_value else None
        failed = (
            (rule.max_absolute_increase is not None and increase > rule.max_absolute_increase)
            or (rule.max_relative_increase is not None and relative_increase is not None and relative_increase > rule.max_relative_increase)
        )
        if failed:
            explanation = "Metric increased beyond allowed baseline degradation."
    elif rule.direction is MetricDirection.EXACT_MATCH:
        failed = current_value != baseline_value
        if failed:
            explanation = "Metric no longer exactly matches the baseline."

    return RegressionCheckResult(
        metric_name=rule.metric_name,
        current_value=current_value,
        baseline_value=baseline_value,
        threshold=rule.model_dump(mode="json"),
        absolute_change=absolute_change,
        relative_change=relative_change,
        direction=rule.direction,
        status=RegressionStatus.FAILED if failed else RegressionStatus.PASSED,
        severity=rule.severity if failed else RegressionSeverity.INFO,
        regression_type=RegressionType.BASELINE,
        explanation=explanation,
    )


def _value_status(
    *,
    direction: MetricDirection,
    value: float | str | None,
    minimum: float | None = None,
    maximum: float | None = None,
    exact_value: float | str | None = None,
) -> RegressionStatus:
    if value is None:
        return RegressionStatus.NOT_APPLICABLE
    if direction is MetricDirection.HIGHER_IS_BETTER and minimum is not None:
        return RegressionStatus.PASSED if float(value) >= minimum else RegressionStatus.FAILED
    if direction is MetricDirection.LOWER_IS_BETTER and maximum is not None:
        return RegressionStatus.PASSED if float(value) <= maximum else RegressionStatus.FAILED
    if direction is MetricDirection.EXACT_MATCH:
        return RegressionStatus.PASSED if value == exact_value else RegressionStatus.FAILED
    return RegressionStatus.PASSED


def _threshold_explanation(
    rule: ThresholdRule,
    current_value: float | None,
    status: RegressionStatus,
) -> str:
    if status is RegressionStatus.NOT_APPLICABLE:
        return f"Metric {rule.metric_name} is unavailable in the current run."
    if status is RegressionStatus.FAILED:
        return f"Metric {rule.metric_name} violates its configured threshold."
    return f"Metric {rule.metric_name} satisfies its configured threshold."


def _aggregate_metric_value(aggregate_metrics: dict[str, Any], metric_name: str) -> float | None:
    metric_payload = aggregate_metrics.get("by_metric", {}).get(metric_name)
    if isinstance(metric_payload, dict):
        value = metric_payload.get("mean")
        return float(value) if value is not None else None
    value = aggregate_metrics.get(metric_name)
    return float(value) if value is not None else None


def _case_metric_value(
    case_level_metrics: dict[str, list[Any]],
    case_id: str,
    metric_name: str,
) -> float | None:
    for metric in case_level_metrics.get(case_id, []):
        payload = metric.model_dump() if hasattr(metric, "model_dump") else metric
        if payload.get("metric_name") == metric_name and payload.get("applicable", True):
            value = payload.get("value")
            return float(value) if value is not None else None
    return None


def _regression_type_for_metric(rule: ThresholdRule) -> RegressionType:
    if rule.metric_name in SAFETY_METRICS:
        return RegressionType.SAFETY
    if rule.metric_name in PERFORMANCE_METRICS:
        return RegressionType.PERFORMANCE
    return rule.regression_type


def _build_report(
    *,
    baseline: BaselineSummary,
    current_run: EvaluationRunResult,
    knowledge_comparison: dict[str, Any],
    checks: list[RegressionCheckResult],
) -> RegressionReport:
    passed_count = sum(check.status is RegressionStatus.PASSED for check in checks)
    warning_count = sum(
        check.status in {RegressionStatus.WARNING, RegressionStatus.NOT_COMPARABLE}
        for check in checks
    )
    failed_count = sum(check.status is RegressionStatus.FAILED for check in checks)
    critical_failures = [
        check
        for check in checks
        if check.status is RegressionStatus.FAILED and check.severity is RegressionSeverity.CRITICAL
    ]
    if critical_failures:
        overall_status = RegressionStatus.FAILED
    elif failed_count:
        overall_status = RegressionStatus.FAILED
    elif warning_count:
        overall_status = RegressionStatus.WARNING
    else:
        overall_status = RegressionStatus.PASSED

    return RegressionReport(
        baseline_metadata={
            "baseline_id": baseline.baseline_id,
            "dataset_name": baseline.dataset_name,
            "dataset_version": baseline.dataset_version,
            "creation_date": baseline.creation_date.isoformat(),
            "git_commit": baseline.git_commit,
        },
        current_run_metadata=current_run.metadata.model_dump(mode="json"),
        knowledge_base_comparison=knowledge_comparison,
        checks=checks,
        passed_count=passed_count,
        warning_count=warning_count,
        failed_count=failed_count,
        critical_failures=critical_failures,
        overall_status=overall_status,
    )
