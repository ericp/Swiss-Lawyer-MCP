"""Source attribution helpers for generated answers."""

from __future__ import annotations

from backend.models.generation import CitedSource
from backend.models.reranking import RerankedChunk


def build_cited_sources(chunks: list[RerankedChunk]) -> list[CitedSource]:
    """Return unique source/page citations from reranked chunks."""

    citations: dict[tuple[str, int | None, str | None], CitedSource] = {}
    for chunk in chunks:
        key = (
            chunk.metadata.source,
            chunk.metadata.page,
            chunk.metadata.region,
        )
        citations[key] = CitedSource(
            source=chunk.metadata.source,
            page=chunk.metadata.page,
            region=chunk.metadata.region,
        )
    return list(citations.values())


def format_context(chunks: list[RerankedChunk]) -> str:
    """Format reranked chunks as source-labelled official context."""

    context_blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.metadata
        context_blocks.append(
            "\n".join(
                [
                    f"[Context {index}]",
                    f"Source: {metadata.source}",
                    f"Page: {metadata.page}",
                    f"Region: {metadata.region}",
                    f"Retrieval source: {chunk.retrieval_source}",
                    f"Retrieval score: {chunk.retrieval_score:.4f}",
                    f"Rerank score: {chunk.rerank_score:.4f}",
                    "Text:",
                    chunk.text,
                ]
            )
        )
    return "\n\n".join(context_blocks)
