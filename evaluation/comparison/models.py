"""Comparison report models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from evaluation.regression.models import MetricDirection, RegressionStatus


class ComparisonInputType(str, Enum):
    """Comparison input type."""

    RUN = "run"
    BASELINE = "baseline"


class MetricDelta(BaseModel):
    """Before/after metric delta."""

    metric_name: str
    category: str | None = None
    before_value: float | None = None
    after_value: float | None = None
    absolute_change: float | None = None
    relative_change: float | None = None
    direction: MetricDirection
    regression_status: RegressionStatus
    threshold_status: RegressionStatus | None = None
    explanation: str


class CaseDelta(BaseModel):
    """Case-level comparison summary."""

    case_id: str
    before_status: str | None = None
    after_status: str | None = None
    status_changed: bool = False
    regressed_metrics: list[str] = Field(default_factory=list)


class ComparisonReport(BaseModel):
    """Machine-readable before/after comparison."""

    comparison_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    before_type: ComparisonInputType
    after_type: ComparisonInputType = ComparisonInputType.RUN
    before_metadata: dict[str, Any]
    after_metadata: dict[str, Any]
    model_configuration_diff: dict[str, Any] = Field(default_factory=dict)
    prompt_hash_diff: dict[str, Any] = Field(default_factory=dict)
    knowledge_base_comparison: dict[str, Any] = Field(default_factory=dict)
    metric_deltas: list[MetricDelta] = Field(default_factory=list)
    case_deltas: list[CaseDelta] = Field(default_factory=list)
    critical_failures: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    improved_metrics: list[str] = Field(default_factory=list)
    regressed_metrics: list[str] = Field(default_factory=list)
    latency_changes: dict[str, MetricDelta] = Field(default_factory=dict)
    passed_count: int = 0
    warning_count: int = 0
    failed_count: int = 0
    overall_status: RegressionStatus = RegressionStatus.PASSED
