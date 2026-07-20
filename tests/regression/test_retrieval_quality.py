"""Retrieval regression checks."""

from __future__ import annotations

import pytest

from evaluation.regression.checker import RegressionChecker
from evaluation.regression.models import (
    MetricDirection,
    RegressionStatus,
    RegressionThresholdConfig,
    ThresholdRule,
)
from tests.regression.helpers import baseline, run_result


pytestmark = [pytest.mark.regression, pytest.mark.evaluation]


def test_absolute_degradation_for_higher_is_better_metric() -> None:
    thresholds = RegressionThresholdConfig(
        global_thresholds=[
            ThresholdRule(
                metric_name="hybrid_recall_at_k_10",
                direction=MetricDirection.HIGHER_IS_BETTER,
                minimum=0.8,
                max_absolute_drop=0.03,
            )
        ]
    )

    report = RegressionChecker(
        thresholds=thresholds,
        baseline=baseline(metrics={"hybrid_recall_at_k_10": 0.9}),
    ).check(
        run_result(metrics={"hybrid_recall_at_k_10": 0.84}),
        current_knowledge_base_fingerprint={"fingerprint": "same"},
    )

    assert any(check.regression_type == "baseline" and check.status is RegressionStatus.FAILED for check in report.checks)
    assert report.overall_status is RegressionStatus.FAILED


def test_relative_degradation_for_higher_is_better_metric() -> None:
    thresholds = RegressionThresholdConfig(
        global_thresholds=[
            ThresholdRule(
                metric_name="hybrid_recall_at_k_10",
                direction=MetricDirection.HIGHER_IS_BETTER,
                minimum=0.5,
                max_relative_drop=0.10,
            )
        ]
    )

    report = RegressionChecker(
        thresholds=thresholds,
        baseline=baseline(metrics={"hybrid_recall_at_k_10": 1.0}),
    ).check(
        run_result(metrics={"hybrid_recall_at_k_10": 0.85}),
        current_knowledge_base_fingerprint={"fingerprint": "same"},
    )

    assert report.failed_count == 1


def test_knowledge_base_fingerprint_change_marks_not_comparable() -> None:
    thresholds = RegressionThresholdConfig(
        global_thresholds=[
            ThresholdRule(metric_name="hybrid_recall_at_k_10", direction=MetricDirection.HIGHER_IS_BETTER, minimum=0.5)
        ]
    )

    report = RegressionChecker(
        thresholds=thresholds,
        baseline=baseline(metrics={"hybrid_recall_at_k_10": 0.8}, fingerprint="old"),
    ).check(
        run_result(metrics={"hybrid_recall_at_k_10": 0.8}),
        current_knowledge_base_fingerprint={"fingerprint": "new"},
    )

    assert report.knowledge_base_comparison["comparison_context"] == "limited_comparability"
    assert any(check.status is RegressionStatus.NOT_COMPARABLE for check in report.checks)
