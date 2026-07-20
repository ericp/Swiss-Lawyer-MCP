"""Citation regression checks."""

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


def test_fabricated_citation_rate_is_critical() -> None:
    thresholds = RegressionThresholdConfig(
        global_thresholds=[
            ThresholdRule(
                metric_name="fabricated_citation_rate",
                direction=MetricDirection.LOWER_IS_BETTER,
                maximum=0.0,
            )
        ]
    )

    report = RegressionChecker(
        thresholds=thresholds,
        baseline=baseline(metrics={"fabricated_citation_rate": 0.0}),
    ).check(
        run_result(metrics={"fabricated_citation_rate": 0.25}),
        current_knowledge_base_fingerprint={"fingerprint": "same"},
    )

    assert report.overall_status is RegressionStatus.FAILED
    assert report.critical_failures[0].metric_name == "fabricated_citation_rate"


def test_exact_match_metric() -> None:
    thresholds = RegressionThresholdConfig(
        global_thresholds=[
            ThresholdRule(
                metric_name="citation_presence",
                direction=MetricDirection.EXACT_MATCH,
                exact_value=1.0,
            )
        ]
    )

    report = RegressionChecker(
        thresholds=thresholds,
        baseline=baseline(metrics={"citation_presence": 1.0}),
    ).check(
        run_result(metrics={"citation_presence": 1.0}),
        current_knowledge_base_fingerprint={"fingerprint": "same"},
    )

    assert report.overall_status is RegressionStatus.PASSED
