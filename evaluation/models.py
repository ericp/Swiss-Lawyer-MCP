"""Pydantic models for evaluation cases, results, and metadata."""

from __future__ import annotations

import platform
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from evaluation.config import EvaluationConfig, ExecutionMode


class EvaluationStatus(str, Enum):
    """Per-case execution status."""

    PASSED = "passed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    SKIPPED = "skipped"


class EvaluationCase(BaseModel):
    """One evaluation case."""

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    language: str | None = None
    tags: list[str] = Field(default_factory=list)
    user_profile: dict[str, Any] = Field(default_factory=dict)
    expected_intent: str | None = None
    expected_clarification_fields: list[str] = Field(default_factory=list)
    expected_clarification_questions: list[str] = Field(default_factory=list)
    forbidden_clarification_fields: list[str] = Field(default_factory=list)
    expected_document_ids: list[str] = Field(default_factory=list)
    expected_source_ids: list[str] = Field(default_factory=list)
    expected_regions: list[str] = Field(default_factory=list)
    expected_chunk_ids: list[str] = Field(default_factory=list)
    relevance_judgments: dict[str, int] = Field(default_factory=dict)
    expected_answer_facts: list[dict[str, Any]] = Field(default_factory=list)
    forbidden_answer_facts: list[dict[str, Any]] = Field(default_factory=list)
    expected_procedure_steps: list[str] = Field(default_factory=list)
    expected_required_document_concepts: list[str] = Field(default_factory=list)
    expected_status: str | None = None
    forbidden_procedure_steps: list[str] = Field(default_factory=list)
    expected_missing_information: list[str] = Field(default_factory=list)
    coverage_status: str = "supported"
    retrieved_context_fixture: str | None = None
    grounded_answer_fixture: str | None = None
    memory_context_fixture: str | None = None
    should_abstain: bool = False
    notes: str | None = None
    offline_outputs: dict[str, Any] = Field(default_factory=dict)


class EvaluationCaseResult(BaseModel):
    """Normalized result for one evaluation case."""

    case_id: str
    question: str
    execution_status: EvaluationStatus
    detected_intent: Any | None = None
    clarification_result: Any | None = None
    vector_results: list[Any] = Field(default_factory=list)
    bm25_results: list[Any] = Field(default_factory=list)
    hybrid_results: list[Any] = Field(default_factory=list)
    reranked_results: list[Any] = Field(default_factory=list)
    generated_answer: Any | None = None
    procedure_plan: Any | None = None
    sources: list[Any] = Field(default_factory=list)
    error: str | None = None
    timings: dict[str, float] = Field(default_factory=dict)
    model_metadata: dict[str, Any] = Field(default_factory=dict)
    intermediate_outputs: dict[str, Any] = Field(default_factory=dict)


class EvaluationRunMetadata(BaseModel):
    """Metadata captured for an evaluation run."""

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    run_name: str
    dataset_name: str
    dataset_version: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    execution_mode: ExecutionMode
    git_commit: str | None = None
    python_version: str = Field(default_factory=platform.python_version)
    dependency_information: dict[str, str] = Field(default_factory=dict)
    embedding_model: str | None = None
    generation_model: str | None = None
    reranker_model: str | None = None
    evaluation_configuration: EvaluationConfig


class EvaluationRunResult(BaseModel):
    """Complete evaluation run result."""

    metadata: EvaluationRunMetadata
    case_results: list[EvaluationCaseResult]
    aggregate_metrics: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
