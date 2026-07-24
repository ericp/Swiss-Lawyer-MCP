"""Rerankers for retrieved chunks."""

from __future__ import annotations

import logging
from typing import Any

from backend.models.reranking import RerankedChunk, RerankResult
from backend.models.retrieval import RetrievedChunk

DEFAULT_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

logger = logging.getLogger(__name__)
CrossEncoder: Any | None = None


class CrossEncoderReranker:
    """Score query/chunk pairs with a local Sentence Transformers CrossEncoder."""

    def __init__(
        self,
        *,
        model_name: str = DEFAULT_RERANK_MODEL,
        model: Any | None = None,
    ) -> None:
        self._model_name = model_name
        self._model = model or _load_cross_encoder()(model_name)

    @property
    def model_name(self) -> str:
        """Return the loaded CrossEncoder model name."""

        return self._model_name

    def rerank(
        self,
        *,
        query: str,
        retrieved_chunks: list[RetrievedChunk],
        top_k: int = 5,
    ) -> RerankResult:
        """Score, sort, and select the most relevant retrieved chunks."""

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        if not retrieved_chunks:
            return RerankResult(
                query=query,
                total_candidates=0,
                selected_candidates=0,
                chunks=[],
            )

        pairs = [(query, chunk.text) for chunk in retrieved_chunks]
        scores = self._model.predict(pairs)

        reranked = [
            RerankedChunk(
                chunk_id=chunk.id,
                text=chunk.text,
                metadata=chunk.metadata,
                retrieval_source=chunk.retrieval_source,
                retrieval_score=chunk.score,
                rerank_score=float(score),
            )
            for chunk, score in zip(retrieved_chunks, scores, strict=False)
        ]
        reranked.sort(key=lambda chunk: chunk.rerank_score, reverse=True)
        selected = reranked[:top_k]

        return RerankResult(
            query=query,
            total_candidates=len(retrieved_chunks),
            selected_candidates=len(selected),
            chunks=selected,
        )


class DisabledReranker:
    """Preserve the reranking schema while using hybrid retrieval order only."""

    model_name = "disabled"

    def __init__(self) -> None:
        logger.info("Model-based reranking is disabled; using hybrid candidate order")

    def rerank(
        self,
        *,
        query: str,
        retrieved_chunks: list[RetrievedChunk],
        top_k: int = 5,
    ) -> RerankResult:
        """Return top candidates with retrieval scores copied as rerank scores."""

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero")
        selected_chunks = retrieved_chunks[:top_k]
        reranked = [
            RerankedChunk(
                chunk_id=chunk.id,
                text=chunk.text,
                metadata=chunk.metadata,
                retrieval_source=chunk.retrieval_source,
                retrieval_score=chunk.score,
                rerank_score=chunk.score,
            )
            for chunk in selected_chunks
        ]
        return RerankResult(
            query=query,
            total_candidates=len(retrieved_chunks),
            selected_candidates=len(reranked),
            chunks=reranked,
        )


def create_reranker(*, provider: str, model_name: str = DEFAULT_RERANK_MODEL) -> Any:
    """Create the configured reranker."""

    provider = provider.strip().lower()
    if provider == "disabled":
        return DisabledReranker()
    if provider in {"cross_encoder", "cross-encoder", "sentence_transformers"}:
        return CrossEncoderReranker(model_name=model_name)
    raise ValueError(f"Unknown reranker provider: {provider}")


def _load_cross_encoder() -> Any:
    global CrossEncoder
    if CrossEncoder is None:
        from sentence_transformers import CrossEncoder as LoadedCrossEncoder

        CrossEncoder = LoadedCrossEncoder
    return CrossEncoder
