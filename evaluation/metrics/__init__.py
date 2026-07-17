"""Automated evaluation metrics."""

from evaluation.metrics.aggregate import aggregate_metric_results, compute_run_metrics
from evaluation.metrics.base import Metric, MetricResult

__all__ = [
    "Metric",
    "MetricResult",
    "aggregate_metric_results",
    "compute_run_metrics",
]
