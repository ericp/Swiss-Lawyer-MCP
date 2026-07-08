from unittest.mock import patch

import pytest

from backend.models.chunk import ChunkMetadata
from backend.models.retrieval import RetrievedChunk
from backend.reranking.reranker import (
    DEFAULT_RERANK_MODEL,
    CrossEncoderReranker,
)


class FakeCrossEncoder:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.predicted_pairs = None

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        self.predicted_pairs = pairs
        return self.scores


def _retrieved_chunk(chunk_id: str, text: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        id=chunk_id,
        text=text,
        metadata=ChunkMetadata(source="sample.pdf", region="federal", page=1),
        score=score,
        retrieval_source="vector",
    )


def test_cross_encoder_loads_default_model_once() -> None:
    with patch("backend.reranking.reranker.CrossEncoder") as cross_encoder:
        reranker = CrossEncoderReranker()

    cross_encoder.assert_called_once_with(DEFAULT_RERANK_MODEL)
    assert reranker.model_name == DEFAULT_RERANK_MODEL


def test_reranker_scores_sorts_and_selects_top_k() -> None:
    model = FakeCrossEncoder(scores=[0.2, 3.4, 1.1])
    chunks = [
        _retrieved_chunk("chunk-1", "General residence information.", 0.7),
        _retrieved_chunk("chunk-2", "Brazilian work permit information.", 0.5),
        _retrieved_chunk("chunk-3", "Family reunification information.", 0.9),
    ]
    reranker = CrossEncoderReranker(model=model)

    result = reranker.rerank(
        query="Can a Brazilian citizen work in Switzerland?",
        retrieved_chunks=chunks,
        top_k=2,
    )

    assert model.predicted_pairs == [
        ("Can a Brazilian citizen work in Switzerland?", chunks[0].text),
        ("Can a Brazilian citizen work in Switzerland?", chunks[1].text),
        ("Can a Brazilian citizen work in Switzerland?", chunks[2].text),
    ]
    assert result.total_candidates == 3
    assert result.selected_candidates == 2
    assert [chunk.chunk_id for chunk in result.chunks] == ["chunk-2", "chunk-3"]
    assert [chunk.rerank_score for chunk in result.chunks] == [3.4, 1.1]
    assert result.chunks[0].retrieval_score == 0.5


def test_reranker_returns_empty_result_for_no_candidates() -> None:
    model = FakeCrossEncoder(scores=[])
    reranker = CrossEncoderReranker(model=model)

    result = reranker.rerank(query="Question", retrieved_chunks=[])

    assert result.total_candidates == 0
    assert result.selected_candidates == 0
    assert result.chunks == []
    assert model.predicted_pairs is None


def test_reranker_rejects_invalid_top_k() -> None:
    reranker = CrossEncoderReranker(model=FakeCrossEncoder(scores=[]))

    with pytest.raises(ValueError):
        reranker.rerank(query="Question", retrieved_chunks=[], top_k=0)
