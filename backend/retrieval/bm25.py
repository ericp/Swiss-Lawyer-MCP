"""BM25 keyword retrieval over chunks stored in ChromaDB."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
from rank_bm25 import BM25Okapi

from backend.models.chunk import ChunkMetadata
from backend.models.retrieval import RetrievedChunk

TOKEN_PATTERN = re.compile(r"\b\w+\b", re.UNICODE)


@dataclass(frozen=True)
class _IndexedChunk:
    id: str
    text: str
    metadata: ChunkMetadata


class BM25Retriever:
    """Build and query a BM25 index from all ChromaDB chunks."""

    def __init__(
        self,
        *,
        path: Path,
        collection_name: str,
        collection: Any | None = None,
    ) -> None:
        if collection is not None:
            self._collection = collection
        else:
            client = chromadb.PersistentClient(path=str(path))
            self._collection = client.get_or_create_collection(name=collection_name)

        self._chunks = self._load_chunks()
        tokenized_corpus = [tokenize(chunk.text) for chunk in self._chunks]
        self._bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None

    def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        """Return the top BM25 keyword matches for a user query."""

        query_tokens = tokenize(query)
        if not query_tokens or self._bm25 is None:
            return []

        scores = self._bm25.get_scores(query_tokens)
        ranked_indexes = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True,
        )[:top_k]

        return [
            RetrievedChunk(
                id=self._chunks[index].id,
                text=self._chunks[index].text,
                metadata=self._chunks[index].metadata,
                score=float(scores[index]),
                retrieval_source="bm25",
            )
            for index in ranked_indexes
        ]

    def _load_chunks(self) -> list[_IndexedChunk]:
        results = self._collection.get(include=["documents", "metadatas"])
        ids = results.get("ids", [])
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])

        chunks: list[_IndexedChunk] = []
        for chunk_id, text, metadata in zip(ids, documents, metadatas, strict=False):
            if not text:
                continue
            chunks.append(
                _IndexedChunk(
                    id=chunk_id,
                    text=text,
                    metadata=ChunkMetadata.model_validate(metadata),
                )
            )
        return chunks


def tokenize(text: str) -> list[str]:
    """Tokenize text for simple language-agnostic BM25 matching."""

    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]
