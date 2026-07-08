"""Vector retrieval from the ChromaDB Swiss procedures collection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb

from backend.ingestion.embeddings import OpenAIEmbedder
from backend.models.chunk import ChunkMetadata
from backend.models.retrieval import RetrievedChunk


class VectorRetriever:
    """Retrieve chunks by embedding the query and searching ChromaDB."""

    def __init__(
        self,
        *,
        path: Path,
        collection_name: str,
        embedder: OpenAIEmbedder,
        collection: Any | None = None,
    ) -> None:
        self._embedder = embedder
        if collection is not None:
            self._collection = collection
        else:
            client = chromadb.PersistentClient(path=str(path))
            self._collection = client.get_or_create_collection(name=collection_name)

    def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        """Return the top vector matches for a user query."""

        if not query.strip():
            return []

        query_embedding = self._embedder.embed_texts([query])[0]
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        ids = _first_result_list(results.get("ids"))
        documents = _first_result_list(results.get("documents"))
        metadatas = _first_result_list(results.get("metadatas"))
        distances = _first_result_list(results.get("distances"))

        retrieved: list[RetrievedChunk] = []
        for chunk_id, text, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
            strict=False,
        ):
            retrieved.append(
                RetrievedChunk(
                    id=chunk_id,
                    text=text,
                    metadata=ChunkMetadata.model_validate(metadata),
                    score=_distance_to_similarity(float(distance)),
                    retrieval_source="vector",
                )
            )
        return retrieved


def _first_result_list(value: Any) -> list[Any]:
    if not value:
        return []
    first = value[0]
    return first if isinstance(first, list) else value


def _distance_to_similarity(distance: float) -> float:
    return 1.0 - distance
