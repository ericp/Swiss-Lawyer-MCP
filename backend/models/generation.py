"""Pydantic models for grounded answer generation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CitedSource(BaseModel):
    """Official source citation used in a generated answer."""

    source: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    region: str | None = None


class GeneratedAnswer(BaseModel):
    """Structured answer generated only from retrieved evidence."""

    answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    procedure_steps: list[str]
    important_notes: list[str]
    cited_sources: list[CitedSource]
    confidence: Literal["High", "Medium", "Low"]
    insufficient_context: bool
