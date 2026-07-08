from pathlib import Path

from backend.retrieval.bm25 import BM25Retriever, tokenize


class FakeCollection:
    def get(self, include: list[str]) -> dict[str, object]:
        assert include == ["documents", "metadatas"]
        return {
            "ids": ["chunk-1", "chunk-2", "chunk-3"],
            "documents": [
                "Brazilian citizens need authorization for employment in Switzerland.",
                "Driving licence exchange is handled by the canton.",
                "Family reunification depends on residence status.",
            ],
            "metadatas": [
                {"source": "work.pdf", "region": "federal", "page": 1},
                {"source": "licence.pdf", "region": "zh", "page": 2},
                {"source": "family.pdf", "region": "federal", "page": 3},
            ],
        }


def test_tokenize_lowercases_and_extracts_words() -> None:
    assert tokenize("Can a Brazilian citizen work?") == [
        "can",
        "a",
        "brazilian",
        "citizen",
        "work",
    ]


def test_bm25_retriever_builds_index_from_chromadb_chunks() -> None:
    retriever = BM25Retriever(
        path=Path("unused"),
        collection_name="swiss_procedures",
        collection=FakeCollection(),
    )

    results = retriever.retrieve("Brazilian employment", top_k=2)

    assert len(results) == 2
    assert results[0].id == "chunk-1"
    assert results[0].metadata.source == "work.pdf"
    assert results[0].retrieval_source == "bm25"
    assert results[0].score >= results[1].score


def test_bm25_retriever_returns_empty_list_for_blank_query() -> None:
    retriever = BM25Retriever(
        path=Path("unused"),
        collection_name="swiss_procedures",
        collection=FakeCollection(),
    )

    assert retriever.retrieve("   ") == []
