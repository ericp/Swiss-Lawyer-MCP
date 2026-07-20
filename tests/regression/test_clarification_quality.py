"""Clarification regression checks."""

from __future__ import annotations

import pytest

from evaluation.metrics.base import MetricResult
from evaluation.regression.checker import RegressionChecker
from evaluation.regression.models import (
    CriticalCaseRequirement,
    MetricDirection,
    RegressionStatus,
    RegressionThresholdConfig,
    ThresholdRule,
)
from tests.regression.helpers import baseline, run_result


pytestmark = [pytest.mark.regression, pytest.mark.evaluation]


def test_critical_case_failure_fails_suite() -> None:
    thresholds = RegressionThresholdConfig(
        critical_cases=[
            CriticalCaseRequirement(
                case_id="critical-1",
                metric_name="missing_field_recall",
                direction=MetricDirection.HIGHER_IS_BETTER,
                minimum=1.0,
            )
        ]
    )
    current = run_result(
        case_metrics={
            "critical-1": [
                MetricResult(metric_name="missing_field_recall", value=0.5, applicable=True)
            ]
        }
    )

    report = RegressionChecker(
        thresholds=thresholds,
        baseline=baseline(),
    ).check(current, current_knowledge_base_fingerprint={"fingerprint": "same"})

    assert report.overall_status is RegressionStatus.FAILED
    assert report.critical_failures


def test_forbidden_question_rate_threshold() -> None:
    thresholds = RegressionThresholdConfig(
        global_thresholds=[
            ThresholdRule(
                metric_name="forbidden_question_rate",
                direction=MetricDirection.LOWER_IS_BETTER,
                maximum=0.0,
            )
        ]
    )

    report = RegressionChecker(
        thresholds=thresholds,
        baseline=baseline(metrics={"forbidden_question_rate": 0.0}),
    ).check(
        run_result(metrics={"forbidden_question_rate": 0.1}),
        current_knowledge_base_fingerprint={"fingerprint": "same"},
    )

    assert any(check.regression_type == "safety" for check in report.checks)
    assert report.overall_status is RegressionStatus.FAILED
