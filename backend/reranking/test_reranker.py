"""CLI smoke test for Phase 3 reranking."""

from __future__ import annotations

import argparse

from backend.ingestion.embeddings import OpenAIEmbedder
from backend.models.reranking import RerankedChunk
from backend.models.retrieval import RetrievedChunk
from backend.reranking.reranker import CrossEncoderReranker
from backend.reranking.reranking_service import RerankingService
from backend.retrieval.bm25 import BM25Retriever
from backend.retrieval.hybrid import HybridRetriever
from backend.retrieval.vector import VectorRetriever
from backend.utils.config import load_retrieval_settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run hybrid retrieval and local CrossEncoder reranking."
    )
    parser.add_argument(
        "question",
        nargs="?",
        default="Can a Brazilian citizen work in Switzerland?",
    )
    parser.add_argument("--retrieval-top-k", type=int, default=None)
    parser.add_argument("--rerank-top-k", type=int, default=None)
    args = parser.parse_args()

    settings = load_retrieval_settings()
    retrieval_top_k = args.retrieval_top_k or settings.top_k
    rerank_top_k = args.rerank_top_k or settings.rerank_top_k

    embedder = OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )
    hybrid_retriever = HybridRetriever(
        vector_retriever=VectorRetriever(
            path=settings.chroma_path,
            collection_name=settings.collection_name,
            embedder=embedder,
        ),
        bm25_retriever=BM25Retriever(
            path=settings.chroma_path,
            collection_name=settings.collection_name,
        ),
    )
    reranking_service = RerankingService(
        hybrid_retriever=hybrid_retriever,
        reranker=CrossEncoderReranker(model_name=settings.rerank_model),
    )

    retrieval_result, rerank_result = reranking_service.retrieve_and_rerank(
        args.question,
        retrieval_top_k=retrieval_top_k,
        rerank_top_k=rerank_top_k,
    )

    print(f"Question: {args.question}")
    _print_retrieved_candidates(retrieval_result.merged_results)
    _print_reranked_results(rerank_result.chunks)


def _print_retrieved_candidates(results: list[RetrievedChunk]) -> None:
    print("\n---------------------------------")
    print("Retrieved Candidates")
    print("---------------------------------")
    if not results:
        print("No candidates")
        return

    for index, result in enumerate(results, start=1):
        metadata = result.metadata
        print(f"\nCandidate {index}")
        print(f"source file: {metadata.source}")
        print(f"region: {metadata.region}")
        print(f"page: {metadata.page}")
        print(f"retrieval source: {result.retrieval_source}")
        print(f"retrieval score: {result.score:.4f}")
        print(f"text: {result.text.replace(chr(10), ' ')[:240]}")


def _print_reranked_results(results: list[RerankedChunk]) -> None:
    print("\n---------------------------------")
    print("Reranked Results")
    print("---------------------------------")
    if not results:
        print("No reranked results")
        return

    for index, result in enumerate(results, start=1):
        metadata = result.metadata
        print(f"\nRank {index}")
        print(f"source file: {metadata.source}")
        print(f"region: {metadata.region}")
        print(f"page: {metadata.page}")
        print(f"retrieval source: {result.retrieval_source}")
        print(f"retrieval score: {result.retrieval_score:.4f}")
        print(f"rerank score: {result.rerank_score:.4f}")
        print(f"text: {result.text.replace(chr(10), ' ')[:240]}")


if __name__ == "__main__":
    main()
