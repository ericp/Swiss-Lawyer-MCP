from backend.generation.source_attribution import build_cited_sources, format_context
from backend.models.chunk import ChunkMetadata
from backend.models.reranking import RerankedChunk


def _chunk(chunk_id: str, source: str, page: int) -> RerankedChunk:
    return RerankedChunk(
        chunk_id=chunk_id,
        text=f"Text for {chunk_id}",
        metadata=ChunkMetadata(source=source, region="federal", page=page),
        retrieval_source="vector",
        retrieval_score=0.7,
        rerank_score=2.5,
    )


def test_build_cited_sources_deduplicates_source_page_region() -> None:
    chunks = [
        _chunk("chunk-1", "work.pdf", 1),
        _chunk("chunk-2", "work.pdf", 1),
        _chunk("chunk-3", "permit.pdf", 4),
    ]

    sources = build_cited_sources(chunks)

    assert [source.model_dump() for source in sources] == [
        {"source": "work.pdf", "page": 1, "region": "federal"},
        {"source": "permit.pdf", "page": 4, "region": "federal"},
    ]


def test_format_context_includes_source_page_and_scores() -> None:
    context = format_context([_chunk("chunk-1", "work.pdf", 1)])

    assert "Source: work.pdf" in context
    assert "Page: 1" in context
    assert "Rerank score: 2.5000" in context
    assert "Text for chunk-1" in context
