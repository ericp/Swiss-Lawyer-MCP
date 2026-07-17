"""Base metric interfaces and shared extraction helpers."""

from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from evaluation.models import EvaluationCase, EvaluationCaseResult


class MetricResult(BaseModel):
    """Typed metric result."""

    metric_name: str
    value: float | None = None
    applicable: bool = True
    passed: bool | None = None
    category: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class Metric(ABC):
    """Common interface for evaluation metrics."""

    metric_name: str
    category: str

    @abstractmethod
    def compute(
        self,
        case: EvaluationCase,
        result: EvaluationCaseResult,
    ) -> MetricResult:
        """Compute the metric for one case/result pair."""


def non_applicable(metric_name: str, *, reason: str) -> MetricResult:
    """Return a non-applicable metric result."""

    return MetricResult(
        metric_name=metric_name,
        applicable=False,
        details={"reason": reason},
    )


def metric_error(metric_name: str, error: Exception) -> MetricResult:
    """Return a metric error without failing the evaluation run."""

    return MetricResult(
        metric_name=metric_name,
        applicable=False,
        error=str(error)[:500],
    )


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def get_field(value: Any, field: str, default: Any = None) -> Any:
    """Read a field from dict-like or object-like values."""

    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(field, default)
    return getattr(value, field, default)


def flatten_text(value: Any) -> str:
    """Turn nested Pydantic/dict/list values into searchable text."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict):
        return " ".join(flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(flatten_text(item) for item in value)
    return str(value)


def result_identifier(item: Any) -> str:
    """Return a stable result identifier for source/chunk matching."""

    for field in ["source_id", "source", "chunk_id", "id", "document_id"]:
        value = get_field(item, field)
        if value:
            return str(value)
    metadata = get_field(item, "metadata", {})
    for field in ["source_id", "source", "document_id"]:
        value = get_field(metadata, field)
        if value:
            return str(value)
    return ""


def source_id(item: Any) -> str | None:
    """Extract source id or source filename from a result/citation."""

    for field in ["source_id", "source"]:
        value = get_field(item, field)
        if value:
            return str(value)
    metadata = get_field(item, "metadata", {})
    for field in ["source_id", "source"]:
        value = get_field(metadata, field)
        if value:
            return str(value)
    return None


def region(item: Any) -> str | None:
    value = get_field(item, "region")
    if value:
        return str(value)
    metadata = get_field(item, "metadata", {})
    value = get_field(metadata, "region")
    return str(value) if value else None


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def contains_text(haystack: str, needle: str) -> bool:
    """Simple deterministic fact matching."""

    return normalize_text(needle) in normalize_text(haystack)


def reciprocal_rank(relevance: list[bool]) -> float:
    for index, relevant in enumerate(relevance, start=1):
        if relevant:
            return 1.0 / index
    return 0.0


def average_precision(relevance: list[bool]) -> float:
    relevant_count = sum(relevance)
    if relevant_count == 0:
        return 0.0
    score = 0.0
    seen = 0
    for index, relevant in enumerate(relevance, start=1):
        if relevant:
            seen += 1
            score += seen / index
    return score / relevant_count


def dcg(grades: list[int]) -> float:
    return sum(
        (2**grade - 1) / math.log2(index + 2)
        for index, grade in enumerate(grades)
    )


def ndcg(grades: list[int], *, k: int) -> float:
    selected = grades[:k]
    ideal = sorted(grades, reverse=True)[:k]
    ideal_dcg = dcg(ideal)
    if ideal_dcg == 0:
        return 0.0
    return dcg(selected) / ideal_dcg


def source_text(result: EvaluationCaseResult) -> str:
    return " ".join(flatten_text(value) for value in [result.generated_answer, result.procedure_plan])
