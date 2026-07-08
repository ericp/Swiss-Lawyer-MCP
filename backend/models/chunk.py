"""Pydantic models used by the PDF ingestion pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    """Traceability metadata for a chunk stored in ChromaDB."""

    source: str = Field(min_length=1)
    region: str = Field(min_length=1)
    page: int = Field(ge=1)


class Chunk(BaseModel):
    """A text chunk ready for embedding and vector storage."""

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    metadata: ChunkMetadata
