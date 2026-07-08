"""ChromaDB persistence for embedded chunks."""

from __future__ import annotations

from pathlib import Path

import chromadb

from backend.models.chunk import Chunk


class ChromaChunkStore:
    """Persist chunks in the Swiss procedures Chroma collection."""

    def __init__(self, *, path: Path, collection_name: str) -> None:
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection = self._client.get_or_create_collection(name=collection_name)

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Insert chunks with their embeddings and metadata."""

        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            return

        self._collection.add(
            ids=[chunk.id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=embeddings,
            metadatas=[chunk.metadata.model_dump() for chunk in chunks],
        )
