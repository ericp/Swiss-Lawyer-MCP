"""Optional RAGAS integration.

The project-specific deterministic metrics remain primary. This module only
reports optional availability and isolates import/runtime failures.
"""

from __future__ import annotations

from evaluation.metrics.base import Metric, MetricResult
from evaluation.models import EvaluationCase, EvaluationCaseResult


class OptionalRagasAvailability(Metric):
    metric_name = "optional_ragas_available"
    category = "optional_ragas"

    def compute(self, case: EvaluationCase, result: EvaluationCaseResult) -> MetricResult:
        try:
            import ragas  # type: ignore  # noqa: F401
        except Exception as error:
            return MetricResult(
                metric_name=self.metric_name,
                value=None,
                applicable=False,
                warnings=[f"RAGAS unavailable or incompatible: {error.__class__.__name__}"],
                details={"reason": "optional_dependency_unavailable"},
            )
        return MetricResult(metric_name=self.metric_name, value=1.0, details={"available": True})


OPTIONAL_RAGAS_METRICS: list[Metric] = [OptionalRagasAvailability()]
