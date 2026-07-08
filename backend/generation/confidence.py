"""Deterministic confidence estimation for generated answers."""

from __future__ import annotations

from typing import Literal

from backend.models.reranking import RerankedChunk

Confidence = Literal["High", "Medium", "Low"]


def estimate_confidence(chunks: list[RerankedChunk]) -> Confidence:
    """Estimate confidence from retrieved evidence quality, not GPT output."""

    if not chunks:
        return "Low"

    average_score = sum(chunk.rerank_score for chunk in chunks) / len(chunks)
    unique_sources = {chunk.metadata.source for chunk in chunks}

    if len(chunks) >= 3 and len(unique_sources) >= 2 and average_score >= 2.0:
        return "High"
    if len(chunks) >= 2 and average_score >= 0.5:
        return "Medium"
    return "Low"
