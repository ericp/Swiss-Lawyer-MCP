"""Pipeline service that runs hybrid retrieval followed by reranking."""

from __future__ import annotations

from backend.models.reranking import RerankResult
from backend.models.retrieval import HybridRetrievalResult
from backend.reranking.reranker import CrossEncoderReranker
from backend.retrieval.hybrid import HybridRetriever


class RerankingService:
    """Retrieve merged candidates and select the most relevant chunks."""

    def __init__(
        self,
        *,
        hybrid_retriever: HybridRetriever,
        reranker: CrossEncoderReranker,
    ) -> None:
        self._hybrid_retriever = hybrid_retriever
        self._reranker = reranker

    def retrieve_and_rerank(
        self,
        query: str,
        *,
        retrieval_top_k: int = 10,
        rerank_top_k: int = 5,
    ) -> tuple[HybridRetrievalResult, RerankResult]:
        """Run hybrid retrieval, then rerank merged candidates."""

        retrieval_result = self._hybrid_retriever.retrieve(
            query,
            top_k=retrieval_top_k,
        )
        rerank_result = self._reranker.rerank(
            query=query,
            retrieved_chunks=retrieval_result.merged_results,
            top_k=rerank_top_k,
        )
        return retrieval_result, rerank_result
