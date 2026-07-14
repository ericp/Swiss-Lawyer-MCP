"""ChromaDB persistence for embedded chunks."""

from __future__ import annotations

from pathlib import Path

import chromadb

from backend.models.chunk import Chunk


class ChromaChunkStore:
    """Persist chunks in the Swiss procedures Chroma collection."""

    def __init__(self, *, path: Path, collection_name: str, collection: object | None = None) -> None:
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection = (
            collection
            if collection is not None
            else self._client.get_or_create_collection(name=collection_name)
        )

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

    def replace_document(
        self,
        *,
        document_id: str,
        chunks: list[Chunk],
        embeddings: list[list[float]],
    ) -> int:
        """Replace active chunks for one document after new chunks are ready."""

        if not document_id:
            raise ValueError("document_id is required")
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        if not chunks:
            raise ValueError("replacement chunks must not be empty")
        for chunk in chunks:
            if chunk.metadata.model_dump().get("document_id") != document_id:
                raise ValueError("all replacement chunks must match document_id")

        existing = self._collection.get(where={"document_id": document_id})
        old_ids = existing.get("ids", []) if existing else []

        self.add_chunks(chunks, embeddings)
        if old_ids:
            self._collection.delete(ids=old_ids)
        return len(old_ids)
