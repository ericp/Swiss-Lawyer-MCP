"""Hybrid retrieval service combining vector and BM25 candidates."""

from __future__ import annotations

from backend.models.retrieval import HybridRetrievalResult, RetrievedChunk
from backend.retrieval.bm25 import BM25Retriever
from backend.retrieval.vector import VectorRetriever


class HybridRetriever:
    """Run vector and BM25 retrieval, then merge without reranking."""

    def __init__(
        self,
        *,
        vector_retriever: VectorRetriever,
        bm25_retriever: BM25Retriever,
    ) -> None:
        self._vector_retriever = vector_retriever
        self._bm25_retriever = bm25_retriever

    def retrieve(self, query: str, *, top_k: int = 10) -> HybridRetrievalResult:
        """Return separate and merged retrieval candidates."""

        vector_results = self._vector_retriever.retrieve(query, top_k=top_k)
        bm25_results = self._bm25_retriever.retrieve(query, top_k=top_k)
        merged_results = merge_results(vector_results, bm25_results)

        return HybridRetrievalResult(
            query=query,
            vector_results=vector_results,
            bm25_results=bm25_results,
            merged_results=merged_results,
        )


def merge_results(
    vector_results: list[RetrievedChunk],
    bm25_results: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    """Merge vector results first, then BM25 results, removing duplicates."""

    merged_by_id: dict[str, RetrievedChunk] = {}
    for result in [*vector_results, *bm25_results]:
        existing = merged_by_id.get(result.id)
        if existing is None:
            merged_by_id[result.id] = result
            continue

        sources = existing.retrieval_source.split("+")
        if result.retrieval_source not in sources:
            merged_by_id[result.id] = existing.model_copy(
                update={
                    "retrieval_source": (
                        f"{existing.retrieval_source}+{result.retrieval_source}"
                    )
                }
            )

    return list(merged_by_id.values())
