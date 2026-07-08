import pytest
from pydantic import ValidationError

from backend.models.chunk import ChunkMetadata
from backend.models.reranking import RerankedChunk, RerankResult


def test_reranked_chunk_model_preserves_scores_and_metadata() -> None:
    chunk = RerankedChunk(
        chunk_id="chunk-1",
        text="Brazilian citizens may require authorization.",
        metadata=ChunkMetadata(source="work.pdf", region="federal", page=2),
        retrieval_source="vector+bm25",
        retrieval_score=0.74,
        rerank_score=8.2,
    )

    assert chunk.chunk_id == "chunk-1"
    assert chunk.metadata.source == "work.pdf"
    assert chunk.retrieval_source == "vector+bm25"
    assert chunk.retrieval_score == 0.74
    assert chunk.rerank_score == 8.2


def test_reranked_chunk_requires_non_empty_fields() -> None:
    with pytest.raises(ValidationError):
        RerankedChunk(
            chunk_id="",
            text="",
            metadata=ChunkMetadata(source="work.pdf", region="federal", page=1),
            retrieval_source="",
            retrieval_score=0.0,
            rerank_score=0.0,
        )


def test_rerank_result_model_tracks_candidate_counts() -> None:
    chunk = RerankedChunk(
        chunk_id="chunk-1",
        text="Permit text",
        metadata=ChunkMetadata(source="permit.pdf", region="federal", page=1),
        retrieval_source="vector",
        retrieval_score=0.5,
        rerank_score=1.4,
    )

    result = RerankResult(
        query="Can I work?",
        total_candidates=8,
        selected_candidates=1,
        chunks=[chunk],
    )

    assert result.total_candidates == 8
    assert result.selected_candidates == 1
    assert result.chunks == [chunk]
