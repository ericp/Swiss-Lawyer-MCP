"""Pydantic models for intent detection and clarification."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DetectedIntent(BaseModel):
    """A classified Swiss administrative procedure intent."""

    intent: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    matched_keywords: list[str] = Field(default_factory=list)


class ClarificationQuestion(BaseModel):
    """A question for one missing material field."""

    field: str = Field(min_length=1)
    question: str = Field(min_length=1)


class ClarificationResult(BaseModel):
    """Result of deciding whether clarification is required."""

    intent: DetectedIntent
    needs_clarification: bool
    missing_fields: list[str]
    clarification_questions: list[ClarificationQuestion]
    known_fields: dict[str, str]
