"""Evaluation configuration."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class ExecutionMode(str, Enum):
    """Evaluation execution modes."""

    OFFLINE = "offline"
    LIVE = "live"


class EvaluationConfig(BaseModel):
    """Configuration for one reproducible evaluation run."""

    dataset_path: Path | None = None
    dataset_name: str = "ad_hoc"
    dataset_version: str = "0"
    run_name: str = "evaluation"
    execution_mode: ExecutionMode = ExecutionMode.OFFLINE
    output_directory: Path = Path("evaluation/artifacts")
    random_seed: int = 0
    retrieval_top_k: int = Field(default=10, ge=1)
    bm25_top_k: int = Field(default=10, ge=1)
    rerank_top_k: int = Field(default=5, ge=1)
    generation_enabled: bool = False
    planner_enabled: bool = False
    judge_model_enabled: bool = False
    judge_model: str | None = None
    max_cases: int | None = Field(default=None, ge=1)
    case_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    fail_fast: bool = False
    save_intermediate_outputs: bool = True
    overwrite_existing_run: bool = False
    notes: str | None = None

    @model_validator(mode="after")
    def validate_live_mode(self) -> EvaluationConfig:
        """Require deliberate live mode selection before model/API-backed work."""

        if self.execution_mode is ExecutionMode.OFFLINE and self.judge_model_enabled:
            raise ValueError("judge_model_enabled requires live execution mode")
        if self.judge_model_enabled and not self.judge_model:
            raise ValueError("judge_model is required when judge_model_enabled is true")
        return self
