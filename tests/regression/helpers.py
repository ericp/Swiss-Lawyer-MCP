"""Regression test fixtures."""

from __future__ import annotations

from datetime import date

from evaluation.config import EvaluationConfig, ExecutionMode
from evaluation.metrics.base import MetricResult
from evaluation.models import EvaluationRunMetadata, EvaluationRunResult
from evaluation.regression.models import BaselineSummary


def run_result(
    *,
    dataset_name: str = "smoke",
    metrics: dict[str, float] | None = None,
    case_metrics: dict[str, list[MetricResult]] | None = None,
) -> EvaluationRunResult:
    metrics = metrics or {"intent_accuracy": 0.95}
    return EvaluationRunResult(
        metadata=EvaluationRunMetadata(
            run_name="test-run",
            dataset_name=dataset_name,
            dataset_version="v1",
            execution_mode=ExecutionMode.OFFLINE,
            evaluation_configuration=EvaluationConfig(dataset_name=dataset_name, dataset_version="v1"),
        ),
        case_results=[],
        case_level_metrics=case_metrics or {},
        aggregate_metrics={
            "by_metric": {
                name: {"mean": value, "sample_count": 1}
                for name, value in metrics.items()
            }
        },
    )


def baseline(
    *,
    dataset_name: str = "smoke",
    metrics: dict[str, float] | None = None,
    fingerprint: str = "same",
) -> BaselineSummary:
    metrics = metrics or {"intent_accuracy": 0.95}
    return BaselineSummary(
        baseline_id=f"{dataset_name}_v1_test",
        dataset_name=dataset_name,
        dataset_version="v1",
        creation_date=date(2026, 7, 20),
        knowledge_base_fingerprint={"fingerprint": fingerprint, "source_registry_version": "1"},
        aggregate_metrics={
            "by_metric": {
                name: {"mean": value, "sample_count": 1}
                for name, value in metrics.items()
            }
        },
        approved_notes="test approval",
    )
