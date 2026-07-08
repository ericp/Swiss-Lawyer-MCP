"""Pydantic models for reranked retrieval results."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.models.chunk import ChunkMetadata


class RerankedChunk(BaseModel):
    """A retrieved chunk after CrossEncoder relevance scoring."""

    chunk_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    metadata: ChunkMetadata
    retrieval_source: str = Field(min_length=1)
    retrieval_score: float
    rerank_score: float


class RerankResult(BaseModel):
    """Top reranked chunks for a query."""

    query: str = Field(min_length=1)
    total_candidates: int = Field(ge=0)
    selected_candidates: int = Field(ge=0)
    chunks: list[RerankedChunk]
