"""Generation and safety regression checks."""

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


def test_lower_is_better_metric_fails_when_too_high() -> None:
    thresholds = RegressionThresholdConfig(
        global_thresholds=[
            ThresholdRule(
                metric_name="unsupported_claim_rate",
                direction=MetricDirection.LOWER_IS_BETTER,
                maximum=0.05,
            )
        ]
    )

    report = RegressionChecker(
        thresholds=thresholds,
        baseline=baseline(metrics={"unsupported_claim_rate": 0.01}),
    ).check(
        run_result(metrics={"unsupported_claim_rate": 0.10}),
        current_knowledge_base_fingerprint={"fingerprint": "same"},
    )

    assert report.overall_status is RegressionStatus.FAILED
    assert report.critical_failures


def test_safety_regression_type_is_applied() -> None:
    thresholds = RegressionThresholdConfig(
        global_thresholds=[
            ThresholdRule(
                metric_name="unsafe_answer_rate",
                direction=MetricDirection.LOWER_IS_BETTER,
                maximum=0.0,
            )
        ]
    )

    report = RegressionChecker(
        thresholds=thresholds,
        baseline=baseline(metrics={"unsafe_answer_rate": 0.0}),
    ).check(
        run_result(metrics={"unsafe_answer_rate": 1.0}),
        current_knowledge_base_fingerprint={"fingerprint": "same"},
    )

    assert any(check.regression_type == "safety" and check.status is RegressionStatus.FAILED for check in report.checks)


def test_lower_is_better_baseline_increase_fails() -> None:
    thresholds = RegressionThresholdConfig(
        global_thresholds=[
            ThresholdRule(
                metric_name="unsupported_claim_rate",
                direction=MetricDirection.LOWER_IS_BETTER,
                maximum=0.5,
                max_absolute_increase=0.02,
            )
        ]
    )

    report = RegressionChecker(
        thresholds=thresholds,
        baseline=baseline(metrics={"unsupported_claim_rate": 0.01}),
    ).check(
        run_result(metrics={"unsupported_claim_rate": 0.04}),
        current_knowledge_base_fingerprint={"fingerprint": "same"},
    )

    assert any(check.regression_type == "baseline" and check.status is RegressionStatus.FAILED for check in report.checks)
