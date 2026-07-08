from pathlib import Path

from backend.retrieval.vector import VectorRetriever


class FakeEmbedder:
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        assert texts == ["Can a Brazilian citizen work in Switzerland?"]
        return [[0.1, 0.2, 0.3]]


class FakeCollection:
    def __init__(self) -> None:
        self.query_arguments = None

    def query(self, **kwargs: object) -> dict[str, object]:
        self.query_arguments = kwargs
        return {
            "ids": [["chunk-1"]],
            "documents": [["A Brazilian citizen needs the correct permit."]],
            "metadatas": [[{"source": "permit.pdf", "region": "federal", "page": 4}]],
            "distances": [[0.25]],
        }


def test_vector_retriever_embeds_query_and_queries_chromadb() -> None:
    collection = FakeCollection()
    retriever = VectorRetriever(
        path=Path("unused"),
        collection_name="swiss_procedures",
        embedder=FakeEmbedder(),  # type: ignore[arg-type]
        collection=collection,
    )

    results = retriever.retrieve(
        "Can a Brazilian citizen work in Switzerland?",
        top_k=3,
    )

    assert collection.query_arguments == {
        "query_embeddings": [[0.1, 0.2, 0.3]],
        "n_results": 3,
        "include": ["documents", "metadatas", "distances"],
    }
    assert len(results) == 1
    assert results[0].id == "chunk-1"
    assert results[0].text == "A Brazilian citizen needs the correct permit."
    assert results[0].metadata.source == "permit.pdf"
    assert results[0].metadata.region == "federal"
    assert results[0].metadata.page == 4
    assert results[0].score == 0.75
    assert results[0].retrieval_source == "vector"


def test_vector_retriever_returns_empty_list_for_blank_query() -> None:
    retriever = VectorRetriever(
        path=Path("unused"),
        collection_name="swiss_procedures",
        embedder=FakeEmbedder(),  # type: ignore[arg-type]
        collection=FakeCollection(),
    )

    assert retriever.retrieve("   ") == []
