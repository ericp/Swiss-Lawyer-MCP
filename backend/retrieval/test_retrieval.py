"""CLI smoke test for Phase 2 hybrid retrieval."""

from __future__ import annotations

import argparse

from backend.ingestion.embeddings import OpenAIEmbedder
from backend.models.retrieval import RetrievedChunk
from backend.retrieval.bm25 import BM25Retriever
from backend.retrieval.hybrid import HybridRetriever
from backend.retrieval.vector import VectorRetriever
from backend.utils.config import load_retrieval_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Run hybrid retrieval for a question.")
    parser.add_argument(
        "question",
        nargs="?",
        default="Can a Brazilian citizen work in Switzerland?",
    )
    parser.add_argument("--top-k", type=int, default=None)
    args = parser.parse_args()

    settings = load_retrieval_settings()
    top_k = args.top_k or settings.top_k

    embedder = OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )
    vector_retriever = VectorRetriever(
        path=settings.chroma_path,
        collection_name=settings.collection_name,
        embedder=embedder,
    )
    bm25_retriever = BM25Retriever(
        path=settings.chroma_path,
        collection_name=settings.collection_name,
    )
    hybrid_retriever = HybridRetriever(
        vector_retriever=vector_retriever,
        bm25_retriever=bm25_retriever,
    )

    result = hybrid_retriever.retrieve(args.question, top_k=top_k)

    print(f"Question: {result.query}")
    _print_section("Vector results", result.vector_results)
    _print_section("BM25 results", result.bm25_results)
    _print_section("Merged results", result.merged_results)


def _print_section(title: str, results: list[RetrievedChunk]) -> None:
    print(f"\n{title}")
    if not results:
        print("- No results")
        return

    for index, result in enumerate(results, start=1):
        metadata = result.metadata
        preview = result.text.replace("\n", " ")[:240]
        print(f"- {index}. id={result.id}")
        print(f"  source={result.retrieval_source} score={result.score:.4f}")
        print(
            f"  metadata=source:{metadata.source} region:{metadata.region} page:{metadata.page}"
        )
        print(f"  text={preview}")


if __name__ == "__main__":
    main()
