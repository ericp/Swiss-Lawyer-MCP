"""Planner and performance regression checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.regression.baseline_service import BaselineGenerationService
from evaluation.regression.checker import RegressionChecker
from evaluation.regression.models import (
    MetricDirection,
    RegressionStatus,
    RegressionThresholdConfig,
    ThresholdRule,
)
from tests.regression.helpers import baseline, run_result


pytestmark = [pytest.mark.regression, pytest.mark.evaluation]


def test_planner_invented_document_rate_fails() -> None:
    thresholds = RegressionThresholdConfig(
        global_thresholds=[
            ThresholdRule(
                metric_name="invented_document_rate",
                direction=MetricDirection.LOWER_IS_BETTER,
                maximum=0.0,
            )
        ]
    )

    report = RegressionChecker(
        thresholds=thresholds,
        baseline=baseline(metrics={"invented_document_rate": 0.0}),
    ).check(
        run_result(metrics={"invented_document_rate": 0.2}),
        current_knowledge_base_fingerprint={"fingerprint": "same"},
    )

    assert report.overall_status is RegressionStatus.FAILED


def test_performance_regression_type() -> None:
    thresholds = RegressionThresholdConfig(
        global_thresholds=[
            ThresholdRule(
                metric_name="total_latency",
                direction=MetricDirection.LOWER_IS_BETTER,
                maximum=5.0,
            )
        ]
    )

    report = RegressionChecker(
        thresholds=thresholds,
        baseline=baseline(metrics={"total_latency": 1.0}),
    ).check(
        run_result(metrics={"total_latency": 10.0}),
        current_knowledge_base_fingerprint={"fingerprint": "same"},
    )

    assert any(check.regression_type == "performance" for check in report.checks)


def test_baseline_generation_requires_approval_note(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        BaselineGenerationService().create_baseline(
            run_result=run_result(),
            output_path=tmp_path / "baseline.json",
            approval_note="",
        )
