import pytest
from pydantic import ValidationError

from backend.models.chunk import ChunkMetadata
from backend.models.retrieval import HybridRetrievalResult, RetrievedChunk


def test_retrieved_chunk_model_preserves_fields() -> None:
    metadata = ChunkMetadata(source="sample.pdf", region="federal", page=2)

    chunk = RetrievedChunk(
        id="chunk-1",
        text="A Brazilian citizen may need authorization.",
        metadata=metadata,
        score=0.82,
        retrieval_source="vector",
    )

    assert chunk.id == "chunk-1"
    assert chunk.metadata.region == "federal"
    assert chunk.score == 0.82
    assert chunk.retrieval_source == "vector"


def test_retrieved_chunk_requires_non_empty_id_text_and_source() -> None:
    with pytest.raises(ValidationError):
        RetrievedChunk(
            id="",
            text="",
            metadata=ChunkMetadata(source="sample.pdf", region="federal", page=1),
            score=0.0,
            retrieval_source="",
        )


def test_hybrid_retrieval_result_groups_result_sets() -> None:
    chunk = RetrievedChunk(
        id="chunk-1",
        text="Permit text",
        metadata=ChunkMetadata(source="sample.pdf", region="zh", page=1),
        score=1.0,
        retrieval_source="bm25",
    )

    result = HybridRetrievalResult(
        query="Can I work in Switzerland?",
        vector_results=[],
        bm25_results=[chunk],
        merged_results=[chunk],
    )

    assert result.query == "Can I work in Switzerland?"
    assert result.bm25_results == [chunk]
    assert result.merged_results == [chunk]
