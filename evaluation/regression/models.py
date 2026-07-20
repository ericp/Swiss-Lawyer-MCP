"""Regression evaluation models."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class MetricDirection(str, Enum):
    """How to interpret metric movement."""

    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    EXACT_MATCH = "exact_match"


class RegressionStatus(str, Enum):
    """Status for one regression check."""

    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    NOT_COMPARABLE = "not_comparable"
    NOT_APPLICABLE = "not_applicable"


class RegressionSeverity(str, Enum):
    """Severity for one regression check."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RegressionType(str, Enum):
    """Kinds of regression checks."""

    THRESHOLD = "threshold"
    BASELINE = "baseline"
    CRITICAL_CASE = "critical_case"
    SAFETY = "safety"
    PERFORMANCE = "performance"
    DATASET_COMPATIBILITY = "dataset_compatibility"


class ThresholdRule(BaseModel):
    """Threshold rule for one metric."""

    metric_name: str
    direction: MetricDirection
    minimum: float | None = None
    maximum: float | None = None
    exact_value: float | str | None = None
    max_absolute_drop: float | None = None
    max_relative_drop: float | None = None
    max_absolute_increase: float | None = None
    max_relative_increase: float | None = None
    severity: RegressionSeverity = RegressionSeverity.CRITICAL
    regression_type: RegressionType = RegressionType.THRESHOLD
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_direction_fields(self) -> ThresholdRule:
        if self.direction is MetricDirection.HIGHER_IS_BETTER and self.maximum is not None:
            raise ValueError("higher_is_better rules should not define maximum")
        if self.direction is MetricDirection.LOWER_IS_BETTER and self.minimum is not None:
            raise ValueError("lower_is_better rules should not define minimum")
        if self.direction is MetricDirection.EXACT_MATCH and self.exact_value is None:
            raise ValueError("exact_match rules require exact_value")
        return self


class CriticalCaseRequirement(BaseModel):
    """Case-specific protected expectation."""

    case_id: str
    metric_name: str
    direction: MetricDirection
    minimum: float | None = None
    maximum: float | None = None
    exact_value: float | str | None = None
    severity: RegressionSeverity = RegressionSeverity.CRITICAL
    explanation: str | None = None


class RegressionThresholdConfig(BaseModel):
    """Loaded threshold configuration."""

    version: int = 1
    global_thresholds: list[ThresholdRule] = Field(default_factory=list)
    dataset_thresholds: dict[str, list[ThresholdRule]] = Field(default_factory=dict)
    metric_thresholds: dict[str, ThresholdRule] = Field(default_factory=dict)
    tag_thresholds: dict[str, list[ThresholdRule]] = Field(default_factory=dict)
    critical_cases: list[CriticalCaseRequirement] = Field(default_factory=list)


class BaselineSummary(BaseModel):
    """Committed summary baseline without raw private model outputs."""

    baseline_id: str
    dataset_name: str
    dataset_version: str
    creation_date: date
    git_commit: str | None = None
    model_configuration: dict[str, Any] = Field(default_factory=dict)
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    source_registry_version: str | None = None
    knowledge_base_fingerprint: dict[str, Any] = Field(default_factory=dict)
    aggregate_metrics: dict[str, Any] = Field(default_factory=dict)
    selected_critical_case_results: dict[str, Any] = Field(default_factory=dict)
    approved_notes: str


class RegressionCheckResult(BaseModel):
    """One regression check outcome."""

    metric_name: str
    current_value: float | str | None = None
    baseline_value: float | str | None = None
    threshold: dict[str, Any] | None = None
    absolute_change: float | None = None
    relative_change: float | None = None
    direction: MetricDirection | None = None
    status: RegressionStatus
    severity: RegressionSeverity
    regression_type: RegressionType
    explanation: str


class RegressionReport(BaseModel):
    """Full quality regression report."""

    baseline_metadata: dict[str, Any]
    current_run_metadata: dict[str, Any]
    knowledge_base_comparison: dict[str, Any]
    checks: list[RegressionCheckResult]
    passed_count: int = 0
    warning_count: int = 0
    failed_count: int = 0
    critical_failures: list[RegressionCheckResult] = Field(default_factory=list)
    overall_status: RegressionStatus = RegressionStatus.PASSED
