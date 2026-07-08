"""Pydantic models for retrieval results."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.models.chunk import ChunkMetadata


class RetrievedChunk(BaseModel):
    """A candidate chunk returned by one or more retrieval methods."""

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    metadata: ChunkMetadata
    score: float
    retrieval_source: str = Field(min_length=1)


class HybridRetrievalResult(BaseModel):
    """Vector, BM25, and merged retrieval candidates for one query."""

    query: str = Field(min_length=1)
    vector_results: list[RetrievedChunk]
    bm25_results: list[RetrievedChunk]
    merged_results: list[RetrievedChunk]
