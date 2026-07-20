"""Smoke regression checks."""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.regression.baseline_service import BaselineGenerationService
from evaluation.regression.baselines import load_baseline
from evaluation.regression.checker import RegressionChecker
from evaluation.regression.models import MetricDirection, RegressionStatus, ThresholdRule
from evaluation.regression.thresholds import load_threshold_config
from tests.regression.helpers import baseline, run_result


pytestmark = [pytest.mark.regression, pytest.mark.evaluation]


def test_threshold_loading() -> None:
    config = load_threshold_config(Path("evaluation/regression/thresholds.yaml"))

    assert config.version == 1
    assert any(rule.metric_name == "intent_accuracy" for rule in config.global_thresholds)
    assert config.critical_cases


def test_committed_smoke_baseline_schema() -> None:
    summary = load_baseline(Path("evaluation/baselines/smoke_v1.json"))

    assert summary.dataset_name == "smoke"
    assert summary.approved_notes


def test_higher_is_better_threshold_passes() -> None:
    thresholds = load_threshold_config(Path("evaluation/regression/thresholds.yaml"))
    thresholds.global_thresholds = [
        ThresholdRule(metric_name="intent_accuracy", direction=MetricDirection.HIGHER_IS_BETTER, minimum=0.8)
    ]
    report = RegressionChecker(
        thresholds=thresholds,
        baseline=baseline(metrics={"intent_accuracy": 0.9}),
    ).check(run_result(metrics={"intent_accuracy": 0.91}), current_knowledge_base_fingerprint={"fingerprint": "same"})

    assert report.overall_status is RegressionStatus.PASSED


def test_baseline_overwrite_protection(tmp_path: Path) -> None:
    output_path = tmp_path / "baseline.json"
    service = BaselineGenerationService()
    current = run_result()
    service.create_baseline(run_result=current, output_path=output_path, approval_note="approved")

    with pytest.raises(FileExistsError):
        service.create_baseline(run_result=current, output_path=output_path, approval_note="approved")


@pytest.mark.live_evaluation
def test_live_regression_suite_disabled_by_default() -> None:
    raise AssertionError("This live test should be skipped unless RUN_LIVE_EVALUATION=1")
