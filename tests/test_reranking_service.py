from backend.models.chunk import ChunkMetadata
from backend.models.reranking import RerankedChunk, RerankResult
from backend.models.retrieval import HybridRetrievalResult, RetrievedChunk
from backend.reranking.reranking_service import RerankingService


class FakeHybridRetriever:
    def __init__(self, result: HybridRetrievalResult) -> None:
        self.result = result
        self.calls: list[tuple[str, int]] = []

    def retrieve(self, query: str, *, top_k: int = 10) -> HybridRetrievalResult:
        self.calls.append((query, top_k))
        return self.result


class FakeReranker:
    def __init__(self, result: RerankResult) -> None:
        self.result = result
        self.calls: list[tuple[str, list[RetrievedChunk], int]] = []

    def rerank(
        self,
        *,
        query: str,
        retrieved_chunks: list[RetrievedChunk],
        top_k: int = 5,
    ) -> RerankResult:
        self.calls.append((query, retrieved_chunks, top_k))
        return self.result


def test_reranking_service_runs_hybrid_then_reranker() -> None:
    retrieved = RetrievedChunk(
        id="chunk-1",
        text="Permit text",
        metadata=ChunkMetadata(source="permit.pdf", region="federal", page=1),
        score=0.8,
        retrieval_source="vector",
    )
    hybrid_result = HybridRetrievalResult(
        query="Can I work?",
        vector_results=[retrieved],
        bm25_results=[],
        merged_results=[retrieved],
    )
    reranked = RerankedChunk(
        chunk_id="chunk-1",
        text="Permit text",
        metadata=retrieved.metadata,
        retrieval_source="vector",
        retrieval_score=0.8,
        rerank_score=2.5,
    )
    rerank_result = RerankResult(
        query="Can I work?",
        total_candidates=1,
        selected_candidates=1,
        chunks=[reranked],
    )
    hybrid = FakeHybridRetriever(hybrid_result)
    reranker = FakeReranker(rerank_result)
    service = RerankingService(
        hybrid_retriever=hybrid,  # type: ignore[arg-type]
        reranker=reranker,  # type: ignore[arg-type]
    )

    actual_hybrid_result, actual_rerank_result = service.retrieve_and_rerank(
        "Can I work?",
        retrieval_top_k=8,
        rerank_top_k=3,
    )

    assert hybrid.calls == [("Can I work?", 8)]
    assert reranker.calls == [("Can I work?", [retrieved], 3)]
    assert actual_hybrid_result == hybrid_result
    assert actual_rerank_result == rerank_result
