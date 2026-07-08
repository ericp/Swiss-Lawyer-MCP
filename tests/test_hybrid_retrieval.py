from backend.models.chunk import ChunkMetadata
from backend.models.retrieval import RetrievedChunk
from backend.retrieval.hybrid import HybridRetriever, merge_results


def _chunk(
    chunk_id: str,
    *,
    score: float,
    retrieval_source: str,
) -> RetrievedChunk:
    return RetrievedChunk(
        id=chunk_id,
        text=f"text for {chunk_id}",
        metadata=ChunkMetadata(source="sample.pdf", region="federal", page=1),
        score=score,
        retrieval_source=retrieval_source,
    )


def test_merge_results_removes_duplicates_and_preserves_source_information() -> None:
    vector_chunk = _chunk("chunk-1", score=0.9, retrieval_source="vector")
    bm25_duplicate = _chunk("chunk-1", score=3.4, retrieval_source="bm25")
    bm25_only = _chunk("chunk-2", score=2.1, retrieval_source="bm25")

    merged = merge_results([vector_chunk], [bm25_duplicate, bm25_only])

    assert [chunk.id for chunk in merged] == ["chunk-1", "chunk-2"]
    assert merged[0].score == 0.9
    assert merged[0].retrieval_source == "vector+bm25"
    assert merged[1].retrieval_source == "bm25"


class FakeRetriever:
    def __init__(self, results: list[RetrievedChunk]) -> None:
        self.results = results
        self.calls: list[tuple[str, int]] = []

    def retrieve(self, query: str, *, top_k: int = 10) -> list[RetrievedChunk]:
        self.calls.append((query, top_k))
        return self.results


def test_hybrid_retriever_runs_both_retrievers_and_returns_grouped_results() -> None:
    vector_results = [_chunk("chunk-1", score=0.7, retrieval_source="vector")]
    bm25_results = [_chunk("chunk-2", score=1.2, retrieval_source="bm25")]
    vector = FakeRetriever(vector_results)
    bm25 = FakeRetriever(bm25_results)
    retriever = HybridRetriever(
        vector_retriever=vector,  # type: ignore[arg-type]
        bm25_retriever=bm25,  # type: ignore[arg-type]
    )

    result = retriever.retrieve("Can I work?", top_k=5)

    assert vector.calls == [("Can I work?", 5)]
    assert bm25.calls == [("Can I work?", 5)]
    assert result.vector_results == vector_results
    assert result.bm25_results == bm25_results
    assert [chunk.id for chunk in result.merged_results] == ["chunk-1", "chunk-2"]
